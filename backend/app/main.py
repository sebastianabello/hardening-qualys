from __future__ import annotations
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from typing import List

from .settings import settings
from .models import RunInfo, ProcessResponse, IngestRequest
from .parser import QualysParser
from .utils import write_ndjson, write_json
from .ingest import BulkIngestor
import json

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helpers de rutas del FS
DATA = settings.DATA_DIR
UPLOADS = DATA / settings.UPLOADS_DIRNAME
OUTPUTS = DATA / settings.OUTPUTS_DIRNAME

ARTIFACT_NAMES = [
    "control_stats.ndjson",
    "results.ndjson",
    "manifest.ndjson",
    "errors.ndjson",
]

@app.post("/api/process", response_model=ProcessResponse)
async def process_files(
    files: List[UploadFile] = File(...),
    client: str = Form("DEFAULT"),
):
    run_id = uuid4().hex
    run_dir_upload = UPLOADS / run_id
    run_dir_output = OUTPUTS / run_id
    run_dir_upload.mkdir(parents=True, exist_ok=True)
    run_dir_output.mkdir(parents=True, exist_ok=True)

    run = RunInfo(
        run_id=run_id,
        client=client or "DEFAULT",
        created_at=datetime.utcnow(),
        source_files=[],
    )

    parser = QualysParser(client=run.client, run_id=run_id)

    # Acumuladores globales por run
    all_control: list[dict] = []
    all_results: list[dict] = []

    for f in files:
        dest = run_dir_upload / f.filename
        run.source_files.append(f.filename)
        content = await f.read()
        dest.write_bytes(content)
        c, r = parser.parse_input(dest)
        all_control.extend(c)
        all_results.extend(r)

    # Construir manifest (incluye resumen por run)
    manifest = parser.manifest_docs + [{
        "type": "run",
        "run_id": run_id,
        "Cliente": run.client,
        "created_at": run.created_at.isoformat() + "Z",
        "num_source_files": len(run.source_files),
        "counts": {
            "control_stats": len(all_control),
            "results": len(all_results),
            "errors": len(parser.error_docs),
        },
    }]

    # Escribir artefactos (exactamente 4)
    paths = {
        "control_stats": run_dir_output / "control_stats.ndjson",
        "results": run_dir_output / "results.ndjson",
        "manifest": run_dir_output / "manifest.ndjson",
        "errors": run_dir_output / "errors.ndjson",
    }

    write_ndjson(paths["control_stats"], all_control)
    write_ndjson(paths["results"], all_results)
    write_ndjson(paths["manifest"], manifest)
    write_ndjson(paths["errors"], parser.error_docs)

    # Guardar metadatos del run
    run.counts = {
        "control_stats": len(all_control),
        "results": len(all_results),
        "errors": len(parser.error_docs),
    }
    write_json(run_dir_output / "run.json", json.loads(run.model_dump_json()))

    # Vista previa (primeras 50 filas por tabla)
    preview = {
        "control_stats": all_control[:50],
        "results": all_results[:50],
    }

    artifacts = []
    for name in ARTIFACT_NAMES:
        p = run_dir_output / name
        artifacts.append({
            "name": name,
            "size": p.stat().st_size if p.exists() else 0,
            "download_url": f"/api/runs/{run_id}/artifact/{name}",
        })

    return ProcessResponse(run=run, artifacts=artifacts, preview=preview)

@app.get("/api/runs/{run_id}/artifact/{name}")
def download_artifact(run_id: str, name: str):
    if name not in ARTIFACT_NAMES:
        raise HTTPException(status_code=404, detail="Artifact not found")
    path = OUTPUTS / run_id / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=name, media_type="application/x-ndjson")

@app.get("/api/runs/{run_id}/artifacts")
def list_artifacts(run_id: str):
    run_dir_output = OUTPUTS / run_id
    if not run_dir_output.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    out = []
    for name in ARTIFACT_NAMES:
        p = run_dir_output / name
        out.append({
            "name": name,
            "size": p.stat().st_size if p.exists() else 0,
            "download_url": f"/api/runs/{run_id}/artifact/{name}",
        })
    return out

@app.post("/api/runs/{run_id}/ingest")
def ingest_run(run_id: str, req: IngestRequest):
    run_dir_output = OUTPUTS / run_id
    if not run_dir_output.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    base = (req.es_base_url or settings.ES_BASE_URL)
    key = (req.es_api_key or settings.ES_API_KEY)
    if not base or not key:
        raise HTTPException(status_code=400, detail="Elasticsearch URL y API key requeridos")

    # Índices (permitir overrides)
    idx = {
        "control_stats": settings.ES_INDEX_CONTROL_STATS,
        "results": settings.ES_INDEX_RESULTS,
        "manifest": settings.ES_INDEX_MANIFEST,
        "errors": settings.ES_INDEX_ERRORS,
    }
    idx.update(req.index_overrides or {})

    ingestor = BulkIngestor(base, key)

    def read_ndjson(path: Path):
        with path.open("rb") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)

    results = {
        "control_stats": ingestor.bulk_ndjson(idx["control_stats"], read_ndjson(run_dir_output / "control_stats.ndjson")),
        "results": ingestor.bulk_ndjson(idx["results"], read_ndjson(run_dir_output / "results.ndjson")),
        "manifest": ingestor.bulk_ndjson(idx["manifest"], read_ndjson(run_dir_output / "manifest.ndjson")),
        "errors": ingestor.bulk_ndjson(idx["errors"], read_ndjson(run_dir_output / "errors.ndjson")),
    }

    return {"ok": True, "indices": idx, "bulk_results": results}
