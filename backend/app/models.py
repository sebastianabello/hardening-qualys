from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

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

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ProcessJob(BaseModel):
    job_id: str
    status: JobStatus
    client: str
    empresas: List[str] = Field(default_factory=list)
    nombre_defecto: Optional[str] = None
    progress: Optional[str] = None
    current_file: Optional[str] = None
    files_processed: int = 0
    total_files: int = 0
    created_at: datetime
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    result: Optional[ProcessResponse] = None
    error: Optional[str] = None
