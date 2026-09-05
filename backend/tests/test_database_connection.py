from app.database.connection import normalize_database_url


def test_normalize_database_url_supports_cloud_postgres_formats() -> None:
    assert normalize_database_url(
        "postgres://user:password@host/database?sslmode=require"
    ) == "postgresql+psycopg://user:password@host/database?sslmode=require"
    assert normalize_database_url(
        "postgresql://user:password@host/database"
    ) == "postgresql+psycopg://user:password@host/database"
    assert normalize_database_url(
        "postgresql+psycopg://user:password@host/database"
    ) == "postgresql+psycopg://user:password@host/database"
    assert normalize_database_url("sqlite:///./mobility.db") == "sqlite:///./mobility.db"
