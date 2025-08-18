from __future__ import annotations
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    APP_NAME: str = "qualys-csv-processor"
    DATA_DIR: Path = Path("./data").resolve()
    UPLOADS_DIRNAME: str = "uploads"
    OUTPUTS_DIRNAME: str = "outputs"

    # Defaults para ES (pueden sobreescribirse en el POST /ingest)
    ES_BASE_URL: str | None = None  # ej: https://es.example.com
    ES_API_KEY: str | None = None   # apiKey Base64

    # Nombres de índices por defecto
    ES_INDEX_CONTROL_STATS: str = "qualys-control-stats"
    ES_INDEX_RESULTS: str = "qualys-results"
    ES_INDEX_MANIFEST: str = "qualys-manifest"
    ES_INDEX_ERRORS: str = "qualys-errors"

    class Config:
        env_file = ".env"

settings = Settings()

# Crear carpetas al cargar settings
(settings.DATA_DIR / settings.UPLOADS_DIRNAME).mkdir(parents=True, exist_ok=True)
(settings.DATA_DIR / settings.OUTPUTS_DIRNAME).mkdir(parents=True, exist_ok=True)
