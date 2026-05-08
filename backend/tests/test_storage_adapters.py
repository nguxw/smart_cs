from app.data.postgres_repository import normalize_database_url
from app.rag.qdrant_store import stable_embedding


def test_normalize_database_url() -> None:
    assert (
        normalize_database_url("postgresql+psycopg://smartcs:pw@localhost/db")
        == "postgresql://smartcs:pw@localhost/db"
    )


def test_stable_embedding_shape_and_determinism() -> None:
    first = stable_embedding("退款政策", vector_size=16)
    second = stable_embedding("退款政策", vector_size=16)
    assert first == second
    assert len(first) == 16
    assert abs(sum(value * value for value in first) - 1.0) < 1e-6

