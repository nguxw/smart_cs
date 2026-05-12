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


def _csv(value: str | None, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    if value is None:
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "local")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    cors_origins: tuple[str, ...] = _csv(
        os.getenv("CORS_ORIGINS"),
        ("http://127.0.0.1:5173", "http://localhost:5173"),
    )
    cors_allow_credentials: bool = _truthy(os.getenv("CORS_ALLOW_CREDENTIALS"), default=True)
    _local_env = os.getenv("APP_ENV", "local").strip().lower()
    demo_header_auth_enabled: bool = _truthy(
        os.getenv("DEMO_HEADER_AUTH_ENABLED"),
        default=_local_env in {"local", "dev", "development", "test"},
    )
    auth_token_secret: str = os.getenv("AUTH_TOKEN_SECRET", "local-demo-secret-change-me")
    agent_runtime: str = os.getenv("AGENT_RUNTIME", "langgraph")

    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")
    llm_model: str = os.getenv("LLM_MODEL") or os.getenv("MODEL_NAME") or "gpt-4o-mini"
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = (
        os.getenv("OPENAI_BASE_URL")
        or os.getenv("OPENAI_API_BASE")
        or "https://api.openai.com/v1"
    )
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    llm_timeout_s: float = float(os.getenv("LLM_TIMEOUT_S", "8"))
    llm_router_enabled: bool = _truthy(os.getenv("LLM_ROUTER_ENABLED"), default=False)
    llm_planner_enabled: bool = _truthy(os.getenv("LLM_PLANNER_ENABLED"), default=False)
    llm_query_rewrite_enabled: bool = _truthy(
        os.getenv("LLM_QUERY_REWRITE_ENABLED"), default=True
    )
    llm_answer_critic_enabled: bool = _truthy(
        os.getenv("LLM_ANSWER_CRITIC_ENABLED"), default=False
    )
    llm_decision_timeout_s: float = float(os.getenv("LLM_DECISION_TIMEOUT_S", "3"))

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

    def validate_runtime_boundaries(self) -> None:
        env = self.app_env.strip().lower()
        if env in {"local", "dev", "development", "test"}:
            return
        if self.demo_header_auth_enabled:
            raise RuntimeError("DEMO_HEADER_AUTH_ENABLED must be false outside local/dev/test")
        if self.auth_token_secret == "local-demo-secret-change-me":
            raise RuntimeError("AUTH_TOKEN_SECRET must be changed outside local/dev/test")


settings = Settings()
settings.validate_runtime_boundaries()
