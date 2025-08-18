from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    ES_BASE_URL: str = "http://localhost:9200"
    ES_API_KEY: str | None = None
    ES_INDEX_CONTROL: str = "qualys-control-stats"
    ES_INDEX_RESULTS: str = "qualys-results"

    OUTPUT_BASE_DIR: str = "./data"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173"]
    CORS_ALLOW_ALL: bool = False

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

settings = Settings()
