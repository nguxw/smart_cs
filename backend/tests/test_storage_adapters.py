from app.data.postgres_repository import POSTGRES_SCHEMA_DDL, normalize_database_url
from app.rag.qdrant_store import stable_embedding


def test_normalize_database_url() -> None:
    assert (
        normalize_database_url("postgresql+psycopg://smartcs:pw@localhost/db")
        == "postgresql://smartcs:pw@localhost/db"
    )


def test_postgres_schema_creates_conversations_before_dependent_tables() -> None:
    ddl = "\n".join(POSTGRES_SCHEMA_DDL).lower()

    conversations_index = ddl.index("create table if not exists conversations")
    cases_index = ddl.index("create table if not exists cases")
    tool_audits_index = ddl.index("create table if not exists tool_audits")

    assert conversations_index < cases_index
    assert conversations_index < tool_audits_index


def test_stable_embedding_shape_and_determinism() -> None:
    first = stable_embedding("退款政策", vector_size=16)
    second = stable_embedding("退款政策", vector_size=16)
    assert first == second
    assert len(first) == 16
    assert abs(sum(value * value for value in first) - 1.0) < 1e-6
