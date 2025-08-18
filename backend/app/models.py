from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal, Any
from datetime import datetime

class RunInfo(BaseModel):
    run_id: str
    client: str
    created_at: datetime
    source_files: list[str] = []
    counts: dict[str, int] = Field(default_factory=lambda: {
        "control_stats": 0,
        "results": 0,
        "errors": 0
    })

class IngestRequest(BaseModel):
    es_base_url: str | None = None
    es_api_key: str | None = None
    index_overrides: dict[str, str] | None = None  # keys: control_stats, results, manifest, errors

class ProcessResponse(BaseModel):
    run: RunInfo
    artifacts: list[dict[str, Any]]  # name, path, size
    preview: dict[str, list[dict[str, Any]]] | None = None  # primeras N filas por tabla

ArtifactName = Literal[
    "control_stats.ndjson",
    "results.ndjson",
    "manifest.ndjson",
    "errors.ndjson",
]
