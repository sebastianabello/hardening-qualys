from fastapi import FastAPI, UploadFile, File, Form, Body, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from typing import List, Dict, Optional
from pathlib import Path
from uuid import uuid4
import asyncio
import json
import shutil
import time
import zipfile
import logging
import traceback
from datetime import datetime
from pydantic import BaseModel
from .settings import settings

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from .models import RunInfo, ProcessResponse, Artifact, IngestResult
from .parser import parse_csv_file
from .excel_outputs import guardar_cuatro_excels
from .excel_stream import ExcelAggregator
from .ingest import ingest_run_folder
from .parser_stream import stream_tables
from .csv_stream import CsvAggregator
from .models import JobStatus, ProcessJob

# Job storage en memoria (en producción usar Redis o DB)
active_jobs: Dict[str, ProcessJob] = {}

app = FastAPI(title="Qualys Hardening Backend", default_response_class=JSONResponse)

# Middleware de logging para capturar errores
@app.middleware("http")
async def log_requests(request, call_next):
    start_time = time.time()
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        if process_time > 30:  # Log si toma más de 30 segundos
            logger.warning(f"⏰ Request lento: {request.method} {request.url} - {process_time:.2f}s")
        
        return response
    except Exception as e:
        logger.error(f"❌ Error en request: {request.method} {request.url} - {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

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

async def process_files_background(job_id: str, files_data: List[tuple], client: str, empresas_list: List[str], nombre_defecto: str):
    """Procesa archivos en background y actualiza el job status"""
    job = active_jobs[job_id]
    
    try:
        job.status = JobStatus.PROCESSING
        job.start_time = datetime.now()
        
        run_id = uuid4().hex
        run_dir = RUNS_DIR / run_id
        run_dir_upload = run_dir / "uploads"  
        run_dir_output = run_dir / "output"
        run_dir_upload.mkdir(parents=True, exist_ok=True)
        run_dir_output.mkdir(parents=True, exist_ok=True)

        run = RunInfo(run_id=run_id, client=client, source_files=[], counts={})
        
        # Guardar archivos subidos
        saved_csvs: List[Path] = []
        job.total_files = len(files_data)
        
        for i, (filename, content) in enumerate(files_data):
            job.current_file = filename
            job.files_processed = i
            job.progress = f"Guardando archivo {i+1}/{len(files_data)}: {filename}"
            
            run.source_files.append(filename)
            dest = run_dir_upload / filename
            
            # Guardar contenido del archivo
            with dest.open("wb") as f:
                f.write(content)
            
            if filename.lower().endswith(".zip"):
                try:
                    csvs = _collect_csvs_from_zip(dest, run_dir_upload)
                    saved_csvs.extend(csvs)
                except zipfile.BadZipFile:
                    pass
            elif filename.lower().endswith(".csv"):
                saved_csvs.append(dest)

        # Procesar CSVs
        agg = CsvAggregator(cliente=client, out_dir=run_dir_output)
        warnings = []
        
        total_csvs = len(saved_csvs)
        
        for i, csv_path in enumerate(saved_csvs):
            job.current_file = csv_path.name
            job.files_processed = len(files_data) + i
            job.total_files = len(files_data) + total_csvs
            job.progress = f"Procesando CSV {i+1}/{total_csvs}: {csv_path.name}"
            
            try:
                saw_t1 = saw_t2 = False
                rows_processed = 0
                
                for table, es_aj, row, cols, os_name in stream_tables(csv_path, empresas_list, nombre_defecto or client):
                    if table == "t1": saw_t1 = True
                    if table == "t2": saw_t2 = True
                    agg.add_row(table, es_aj, row, cols, os_name)
                    rows_processed += 1
                    
                    # Actualizar progreso cada 5000 filas
                    if rows_processed % 5000 == 0:
                        job.progress = f"Procesando {csv_path.name}: {rows_processed:,} filas"
                
                if not saw_t1:
                    warnings.append(f"{csv_path.name}: 'Control Statistics' no encontrada o vacía")
                if not saw_t2:
                    warnings.append(f"{csv_path.name}: 'RESULTS' no encontrada o vacía")
                    
            except Exception as ex:
                logger.error(f"❌ Error procesando {csv_path.name}: {ex}")
                warnings.append(f"{csv_path.name}: error de parseo: {ex}")

        # Finalizar
        job.progress = "Generando archivos finales..."
        nombres = agg.close()
        
        artifacts = []
        for n in nombres:
            p = run_dir_output / n
            artifacts.append(Artifact(name=n, size=p.stat().st_size if p.exists() else 0,
                                      download_url=f"/api/runs/{run_id}/artifact/{n}"))
        
        run.counts = agg.counts
        preview = agg.preview

        # Guardar manifest
        (run_dir / "manifest.json").write_text(json.dumps({
            "run": run.model_dump(),
            "artifacts": [a.model_dump() for a in artifacts],
            "warnings": warnings
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        # Completar job
        result = ProcessResponse(run=run, artifacts=artifacts, preview=preview, warnings=warnings)
        job.result = result
        job.status = JobStatus.COMPLETED
        job.end_time = datetime.now()
        job.progress = f"✅ Completado: {len(artifacts)} archivos generados"
        
    except Exception as e:
        logger.error(f"❌ Error en job {job_id}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        job.status = JobStatus.FAILED
        job.error = str(e)
        job.end_time = datetime.now()

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

@app.post("/api/process-async")
async def process_files_async(
    files: List[UploadFile],
    client: str = Form(...),
    empresas: Optional[str] = Form(None),
    nombre_defecto: Optional[str] = Form(None)
):
    """Inicia procesamiento asíncrono y retorna job_id inmediatamente"""
    start_time = time.time()
    logger.info(f"🚀 Iniciando procesamiento asíncrono de {len(files)} archivos para cliente '{client}'")
    
    # Crear job_id único
    job_id = uuid4().hex
    
    # Leer archivos en memoria
    files_data = []
    for file in files:
        content = await file.read()
        files_data.append((file.filename, content))
        logger.info(f"📁 Archivo leído: {file.filename} ({len(content):,} bytes)")
    
    empresas_list = [e.strip() for e in (empresas or "").split(",")] if empresas else []
    
    # Crear job entry
    job = ProcessJob(
        job_id=job_id,
        status=JobStatus.PENDING,
        client=client,
        empresas=empresas_list,
        nombre_defecto=nombre_defecto,
        total_files=len(files),
        files_processed=0,
        progress="Iniciando procesamiento...",
        current_file="",
        created_at=datetime.now()
    )
    
    active_jobs[job_id] = job
    
    # Lanzar procesamiento en background
    asyncio.create_task(process_files_background(job_id, files_data, client, empresas_list, nombre_defecto))
    
    setup_time = time.time() - start_time
    logger.info(f"✅ Job {job_id} iniciado en {setup_time:.2f}s")
    
    return {"job_id": job_id, "status": "started", "message": "Procesamiento iniciado"}

@app.get("/api/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    """Obtiene el estado actual de un job"""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    job = active_jobs[job_id]
    
    response = {
        "job_id": job_id,
        "status": job.status.value,
        "progress": job.progress,
        "files_processed": job.files_processed,
        "total_files": job.total_files,
        "current_file": job.current_file,
        "created_at": job.created_at.isoformat(),
        "start_time": job.start_time.isoformat() if job.start_time else None,
        "end_time": job.end_time.isoformat() if job.end_time else None,
    }
    
    if job.status == JobStatus.COMPLETED and job.result:
        response["result"] = job.result.model_dump()
    elif job.status == JobStatus.FAILED and job.error:
        response["error"] = job.error
    
    return response

@app.post("/api/process", response_model=ProcessResponse)
async def process_files(
    files: List[UploadFile],
    client: str = Form(...),
    empresas: Optional[str] = Form(None),
    nombre_defecto: Optional[str] = Form(None)
):
    logger.info(f"🚀 Iniciando procesamiento: {len(files)} archivos para cliente '{client}'")
    
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
    logger.info(f"📁 Procesando {len(files)} archivos...")
    saved_csvs: List[Path] = []
    for f in files:
        filename = Path(f.filename).name
        logger.info(f"📄 Procesando: {filename}")
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

    agg = CsvAggregator(cliente=client, out_dir=run_dir_output)
    warnings: List[str] = []

    # Procesar CSVs con logging mejorado
    total_csvs = len(saved_csvs)
    logger.info(f"📊 Procesando {total_csvs} archivos CSV...")
    
    for i, csv_path in enumerate(saved_csvs, 1):
        logger.info(f"📄 [{i}/{total_csvs}] Procesando: {csv_path.name} ({csv_path.stat().st_size / 1024 / 1024:.1f} MB)")
        try:
            saw_t1 = saw_t2 = False
            rows_processed = 0
            
            for table, es_aj, row, cols, os_name in stream_tables(csv_path, empresas_list, nombre_defecto or client):
                if table == "t1": saw_t1 = True
                if table == "t2": saw_t2 = True
                agg.add_row(table, es_aj, row, cols, os_name)
                rows_processed += 1
                
                # Log progreso cada 10,000 filas
                if rows_processed % 10000 == 0:
                    logger.info(f"   ⚡ {rows_processed:,} filas procesadas...")
            
            logger.info(f"   ✅ {csv_path.name}: {rows_processed:,} filas procesadas")
            
            if not saw_t1:
                warnings.append(f"{csv_path.name}: 'Control Statistics' no encontrada o vacía")
            if not saw_t2:
                warnings.append(f"{csv_path.name}: 'RESULTS' no encontrada o vacía")
                
        except Exception as ex:
            logger.error(f"❌ Error procesando {csv_path.name}: {ex}")
            warnings.append(f"{csv_path.name}: error de parseo: {ex}")

    nombres = agg.close()
    artifacts = []
    for n in nombres:
        p = run_dir_output / n
        artifacts.append(Artifact(name=n, size=p.stat().st_size if p.exists() else 0,
                                  download_url=f"/api/runs/{run_id}/artifact/{n}"))
    run.counts = agg.counts
    preview = agg.preview

    # Persistir un pequeño manifest para depuración (no se expone como archivo final)
    (run_dir / "manifest.json").write_text(json.dumps({
        "run": run.model_dump(),
        "artifacts": [a.model_dump() for a in artifacts],
        "warnings": warnings
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(f"✅ Procesamiento completado: {len(artifacts)} archivos generados")
    return ProcessResponse(run=run, artifacts=artifacts, preview=preview, warnings=warnings)

@app.get("/api/runs/{run_id}/artifact/{filename}")
def download_artifact(run_id: str, filename: str):
    p = RUNS_DIR / run_id / "output" / filename
    if not p.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    mime = "text/csv" if filename.lower().endswith(".csv") \
           else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return FileResponse(p, filename=filename, media_type=mime)

@app.get("/api/elasticsearch/status")
async def elasticsearch_status():
    """Verifica el estado de la conexión con Elasticsearch."""
    if not settings.ES_BASE_URL:
        return {"ok": False, "error": "ES_BASE_URL no configurado"}
    
    try:
        from .ingest import _create_elasticsearch_client
        es = _create_elasticsearch_client()
        
        try:
            info = es.info()
            es.close()
            
            return {
                "ok": True, 
                "elasticsearch": {
                    "version": info.get("version", {}).get("number", "unknown"),
                    "cluster_name": info.get("cluster_name", "unknown"),
                    "url": settings.ES_BASE_URL,
                    "auth_method": "api_key"
                }
            }
        except Exception as e:
            es.close()
            raise e
            
    except Exception as ex:
        return {"ok": False, "error": f"No se pudo conectar a Elasticsearch: {ex}"}

@app.post("/api/runs/{run_id}/ingest", response_model=IngestResult)
async def ingest_run(run_id: str):
    logger.info(f"🚀 Iniciando ingesta para run: {run_id}")
    out_dir = RUNS_DIR / run_id / "output"
    if not out_dir.exists():
        logger.error(f"❌ Directorio no encontrado: {out_dir}")
        raise HTTPException(status_code=404, detail="Run no encontrado o sin salida")

    try:
        counts = await ingest_run_folder(out_dir)
        logger.info(f"✅ Ingesta completada: {counts}")
        return IngestResult(ok=True, errors=False, indexed=counts)
    except Exception as ex:
        logger.error(f"❌ Error en ingesta: {str(ex)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return IngestResult(ok=False, errors=True, indexed={}, details={"error": str(ex)})
