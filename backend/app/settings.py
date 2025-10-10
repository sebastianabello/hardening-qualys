from __future__ import annotations
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    APP_NAME: str = "qualys-csv-processor"
    DATA_DIR: Path = Path("./data").resolve()
    UPLOADS_DIRNAME: str = "uploads"
    OUTPUTS_DIRNAME: str = "outputs"

    # Configuración adicional
    OUTPUT_BASE_DIR: str = "./data"
    CORS_ALLOW_ALL: bool = True
    ALLOWED_ORIGINS: list[str] = []
    CSV_PART_MAX_ROWS: int = 1000000
    CSV_GZIP: bool = False
    BATCH_SIZE: int = 1000

    # Configuración de Elasticsearch
    ES_BASE_URL: str | None = None      # URL del cluster de Elasticsearch
    ES_API_KEY: str | None = None       # API Key de Elasticsearch
    ES_VERIFY_CERTS: bool = False       # Verificar certificados SSL

    # Nombres de índices por defecto
    ES_INDEX_CONTROL: str = "qualys-control-stats"
    ES_INDEX_RESULTS: str = "qualys-results" 
    ES_INDEX_MANIFEST: str = "qualys-manifest"
    ES_INDEX_ERRORS: str = "qualys-errors"

    class Config:
        env_file = ".env"

settings = Settings()

# Crear carpetas al cargar settings
(settings.DATA_DIR / settings.UPLOADS_DIRNAME).mkdir(parents=True, exist_ok=True)
(settings.DATA_DIR / settings.OUTPUTS_DIRNAME).mkdir(parents=True, exist_ok=True)
