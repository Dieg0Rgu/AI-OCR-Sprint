import os
from pathlib import Path
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server Configuration
    ENVIRONMENT: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # Base Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    STORAGE_DIR: str = "storage"
    MAX_UPLOAD_SIZE_MB: int = 50

    # Vector Database (Qdrant)
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "pdf_multimodal_rag"
    QDRANT_PREFER_GRPC: bool = False

    # Ollama Local Inference
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = "qwen2.5:7b"
    OLLAMA_VISION_MODEL: str = "moondream"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    OLLAMA_TIMEOUT_SECONDS: float = 60.0
    OLLAMA_MAX_RETRIES: int = 3

    # Vision Specific Tuning (Moondream lightweight multimodal model)
    VISION_MODEL: str = "moondream"
    VISION_TIMEOUT_SECONDS: float = 30.0
    VISION_MAX_RETRIES: int = 1

    # Fallbacks & Provider Preferences
    FALLBACK_EMBEDDINGS: bool = True

    @property
    def active_vision_model(self) -> str:
        return os.getenv("VISION_MODEL") or self.VISION_MODEL or self.OLLAMA_VISION_MODEL or "moondream"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @property
    def storage_path(self) -> Path:
        resolved = (self.BASE_DIR.parent / self.STORAGE_DIR).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    @property
    def documents_dir(self) -> Path:
        path = self.storage_path / "documents"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def temp_dir(self) -> Path:
        path = self.storage_path / "temp"
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
