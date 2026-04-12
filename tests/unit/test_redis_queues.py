# tests/unit/test_redis_queues.py
from unittest.mock import MagicMock, patch


def test_get_queues_returns_sensitive_and_cloud_keys():
    with patch("src.queue.redis_queues.Redis") as mock_redis_cls, \
         patch("src.queue.redis_queues.Queue") as mock_queue_cls:
        mock_redis_cls.from_url.return_value = MagicMock()
        mock_queue_cls.side_effect = lambda name, connection: MagicMock(name=name)

        from src.queue.redis_queues import get_queues
        queues = get_queues("redis://localhost:6379/0")

        assert "sensitive" in queues
        assert "cloud" in queues


def test_get_queues_uses_correct_queue_names():
    names_used = []
    with patch("src.queue.redis_queues.Redis") as mock_redis_cls, \
         patch("src.queue.redis_queues.Queue") as mock_queue_cls:
        mock_redis_cls.from_url.return_value = MagicMock()
        mock_queue_cls.side_effect = lambda name, connection: names_used.append(name) or MagicMock()

        from src.queue.redis_queues import get_queues
        get_queues("redis://localhost:6379/0")

        assert "sensitive-queue" in names_used
        assert "cloud-queue" in names_used


def test_get_queues_connects_with_provided_url():
    with patch("src.queue.redis_queues.Redis") as mock_redis_cls, \
         patch("src.queue.redis_queues.Queue"):
        mock_redis_cls.from_url.return_value = MagicMock()

        from src.queue.redis_queues import get_queues
        get_queues("redis://myhost:6379/1")

        mock_redis_cls.from_url.assert_called_with("redis://myhost:6379/1")
