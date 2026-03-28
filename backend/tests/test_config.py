"""Unit tests for Settings configuration validators."""

from app.config import Settings


class TestConvertDatabaseUrl:
    """Tests for Settings.convert_database_url validator."""

    def test_postgresql_converted_to_asyncpg(self):
        result = Settings.convert_database_url("postgresql://user:pass@host/db")
        assert result == "postgresql+asyncpg://user:pass@host/db"

    def test_asyncpg_url_unchanged(self):
        url = "postgresql+asyncpg://user:pass@host/db"
        result = Settings.convert_database_url(url)
        assert result == url

    def test_other_url_unchanged(self):
        url = "sqlite:///test.db"
        result = Settings.convert_database_url(url)
        assert result == url

    def test_only_first_occurrence_replaced(self):
        url = "postgresql://host/postgresql"
        result = Settings.convert_database_url(url)
        assert result == "postgresql+asyncpg://host/postgresql"
