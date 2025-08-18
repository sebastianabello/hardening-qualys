from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class Artifact(BaseModel):
    name: str
    size: int
    download_url: str

class RunInfo(BaseModel):
    run_id: str
    client: str
    source_files: List[str] = Field(default_factory=list)
    counts: Dict[str, int] = Field(default_factory=dict)

class ProcessResponse(BaseModel):
    run: RunInfo
    artifacts: List[Artifact]
    preview: Optional[Dict[str, List[Dict[str, Any]]]] = None
    warnings: List[str] = Field(default_factory=list)

class IngestResult(BaseModel):
    ok: bool
    errors: bool
    indexed: Dict[str, int] = Field(default_factory=dict)  # por índice
    details: Optional[Dict[str, Any]] = None
