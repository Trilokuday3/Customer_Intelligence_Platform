import pytest

from api.database import normalize_database_url


@pytest.mark.parametrize(
    "given, expected",
    [
        ("postgresql://u:p@host/db?sslmode=require", "postgresql+psycopg2://u:p@host/db?sslmode=require"),
        ("postgres://u:p@host/db", "postgresql+psycopg2://u:p@host/db"),
        ("postgresql+psycopg2://u:p@host/db", "postgresql+psycopg2://u:p@host/db"),
        ("sqlite:///./cip.db", "sqlite:///./cip.db"),
    ],
)
def test_postgres_urls_name_the_psycopg2_driver(given, expected):
    assert normalize_database_url(given) == expected
