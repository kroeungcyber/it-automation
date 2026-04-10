# tests/unit/test_db_connection.py
from unittest.mock import MagicMock, patch


def test_get_engine_calls_create_async_engine():
    with patch("src.db.connection.create_async_engine") as mock_create:
        mock_engine = MagicMock()
        mock_create.return_value = mock_engine

        from src.db.connection import get_engine
        engine = get_engine("postgresql+asyncpg://u:p@localhost/db")

        mock_create.assert_called_once_with(
            "postgresql+asyncpg://u:p@localhost/db", echo=False
        )
        assert engine is mock_engine


def test_get_session_factory_returns_sessionmaker():
    from unittest.mock import MagicMock, patch
    with patch("src.db.connection.async_sessionmaker") as mock_sm:
        mock_factory = MagicMock()
        mock_sm.return_value = mock_factory
        mock_engine = MagicMock()

        from src.db.connection import get_session_factory
        factory = get_session_factory(mock_engine)

        mock_sm.assert_called_once_with(mock_engine, expire_on_commit=False)
        assert factory is mock_factory
