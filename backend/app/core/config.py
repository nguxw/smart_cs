from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "local")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")
    llm_model: str = os.getenv("LLM_MODEL") or os.getenv("MODEL_NAME") or "gpt-4o-mini"
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = (
        os.getenv("OPENAI_BASE_URL")
        or os.getenv("OPENAI_API_BASE")
        or "https://api.openai.com/v1"
    )
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "local")
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "smartcs_kb")
    qdrant_vector_size: int = int(os.getenv("QDRANT_VECTOR_SIZE", "384"))

    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://smartcs:smartcs@localhost:5432/smartcs"
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    data_backend: str = os.getenv("DATA_BACKEND", "auto")
    kb_backend: str = os.getenv("KB_BACKEND", "auto")
    redis_backend: str = os.getenv("REDIS_BACKEND", "auto")
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))

    otel_service_name: str = os.getenv("OTEL_SERVICE_NAME", "smartcs-agent-desk")
    otel_exporter_otlp_endpoint: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")

    mock_mode: bool = _truthy(os.getenv("MOCK_MODE"), default=True)


settings = Settings()
