from fastapi import FastAPI, UploadFile, File, Form, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from typing import List
from pathlib import Path
from uuid import uuid4
import json
import shutil
import zipfile
from .config import settings
from .models import RunInfo, ProcessResponse, Artifact, IngestResult
from .parser import parse_csv_file
from .excel_outputs import guardar_cuatro_excels
from .parser_stream import stream_tables
from .excel_stream import ExcelAggregator
from .ingest import ingest_run_folder

app = FastAPI(title="Qualys Hardening Backend", default_response_class=JSONResponse)

allow_origin_regex = ".*" if settings.CORS_ALLOW_ALL else None
allow_origins = [] if settings.CORS_ALLOW_ALL else settings.ALLOWED_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=allow_origin_regex,  # 👈 habilita cualquier host
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(settings.OUTPUT_BASE_DIR).resolve()
RUNS_DIR = BASE_DIR / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/")
def root():
    return {"ok": True, "app": "Qualys Hardening Backend"}

@app.get("/health")
def health():
    return {"ok": True}

def _save_upload(u: UploadFile, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        shutil.copyfileobj(u.file, f)

def _collect_csvs_from_zip(zip_path: Path, dst_dir: Path) -> List[Path]:
    paths = []
    with zipfile.ZipFile(zip_path, "r") as z:
        for name in z.namelist():
            if name.lower().endswith(".csv") and not name.endswith("/"):
                out = dst_dir / Path(name).name
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(name) as src, out.open("wb") as f:
                    shutil.copyfileobj(src, f)
                paths.append(out)
    return paths

@app.post("/api/process", response_model=ProcessResponse)
async def process_files(
    files: List[UploadFile] = File(...),
    client: str = Form("DEFAULT"),
    empresas: str = Form("[]"),          # JSON array string: ["EMPRESA1","EMPRESA2",...]
    nombre_defecto: str = Form("DEFAULT")
):
    run_id = uuid4().hex
    run_dir = RUNS_DIR / run_id
    run_dir_upload = run_dir / "uploads"
    run_dir_output = run_dir / "output"
    run_dir_upload.mkdir(parents=True, exist_ok=True)
    run_dir_output.mkdir(parents=True, exist_ok=True)

    try:
        empresas_list = json.loads(empresas) if empresas else []
        if not isinstance(empresas_list, list):
            empresas_list = []
    except Exception:
        empresas_list = []

    run = RunInfo(run_id=run_id, client=client, source_files=[], counts={})

    # Acumuladores
    t1_normal_rows: List[dict] = []
    t1_ajustada_rows: List[dict] = []
    t2_normal_rows: List[dict] = []
    t2_ajustada_rows: List[dict] = []
    t1_cols_master: List[str] = []
    t2_cols_master: List[str] = []
    warnings: List[str] = []

    # Guardar y expandir archivos
    saved_csvs: List[Path] = []
    for f in files:
        filename = Path(f.filename).name
        run.source_files.append(filename)
        dest = run_dir_upload / filename
        _save_upload(f, dest)

        if filename.lower().endswith(".zip"):
            try:
                csvs = _collect_csvs_from_zip(dest, run_dir_upload)
                saved_csvs.extend(csvs)
            except zipfile.BadZipFile:
                warnings.append(f"{filename}: ZIP inválido")
        elif filename.lower().endswith(".csv"):
            saved_csvs.append(dest)

    # Procesar CSVs
    for csv_path in saved_csvs:
        try:
            es_aj, cliente_arch, t1_rows, t1_cols, t2_rows, t2_cols, os_name = parse_csv_file(
                csv_path, empresas_list, nombre_defecto or client
            )
            # columnas maestras: preserva orden del primer archivo que traiga columnas
            if os_name:
                for r in t1_rows: r.setdefault("os", os_name)
                for r in t2_rows: r.setdefault("os", os_name)
            if t1_rows and not t1_cols_master:
                t1_cols_master = t1_cols
            if t2_rows and not t2_cols_master:
                t2_cols_master = t2_cols

            if t1_rows:
                (t1_ajustada_rows if es_aj else t1_normal_rows).extend(t1_rows)
            else:
                warnings.append(f"{csv_path.name}: 'Control Statistics' no encontrada o vacía")

            if t2_rows:
                (t2_ajustada_rows if es_aj else t2_normal_rows).extend(t2_rows)
            else:
                warnings.append(f"{csv_path.name}: 'RESULTS' no encontrada o vacía")
        except Exception as ex:
            warnings.append(f"{csv_path.name}: error de parseo: {ex}")

    # Generar 4 Excel
    nombres = guardar_cuatro_excels(
        t1_normal=t1_normal_rows, t1_cols=t1_cols_master or ["Cliente"],
        t1_ajustada=t1_ajustada_rows,
        t2_normal=t2_normal_rows, t2_cols=t2_cols_master or ["Cliente"],
        t2_ajustada=t2_ajustada_rows,
        cliente_padre=client, carpeta=run_dir_output
    )

    artifacts: List[Artifact] = []
    for n in nombres:
        p = run_dir_output / n
        artifacts.append(Artifact(
            name=n, size=p.stat().st_size,
            download_url=f"/api/runs/{run_id}/artifact/{n}"
        ))

    # Conteos
    run.counts = {
        "t1_normal": len(t1_normal_rows),
        "t1_ajustada": len(t1_ajustada_rows),
        "t2_normal": len(t2_normal_rows),
        "t2_ajustada": len(t2_ajustada_rows),
    }

    # Previews (solo primeras 50)
    preview = {
        "t1_normal":   t1_normal_rows[:50],
        "t1_ajustada": t1_ajustada_rows[:50],
        "t2_normal":   t2_normal_rows[:50],
        "t2_ajustada": t2_ajustada_rows[:50],
    }

    # Persistir un pequeño manifest para depuración (no se expone como archivo final)
    (run_dir / "manifest.json").write_text(json.dumps({
        "run": run.model_dump(),
        "artifacts": [a.model_dump() for a in artifacts],
        "warnings": warnings
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    return ProcessResponse(run=run, artifacts=artifacts, preview=preview, warnings=warnings)

@app.get("/api/runs/{run_id}/artifact/{filename}")
def download_artifact(run_id: str, filename: str):
    p = RUNS_DIR / run_id / "output" / filename
    if not p.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    mime = "text/csv" if filename.lower().endswith(".csv") \
           else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return FileResponse(p, filename=filename, media_type=mime)

@app.post("/api/runs/{run_id}/ingest", response_model=IngestResult)
async def ingest_run(run_id: str):
    out_dir = RUNS_DIR / run_id / "output"
    if not out_dir.exists():
        raise HTTPException(status_code=404, detail="Run no encontrado o sin salida")

    try:
        counts = await ingest_run_folder(out_dir)
        return IngestResult(ok=True, errors=False, indexed=counts)
    except Exception as ex:
        return IngestResult(ok=False, errors=True, indexed={}, details={"error": str(ex)})
