# src/queue/redis_queues.py
from redis import Redis
from rq import Queue

SENSITIVE_QUEUE_NAME = "sensitive-queue"
CLOUD_QUEUE_NAME = "cloud-queue"


def get_queues(redis_url: str) -> dict[str, Queue]:
    conn = Redis.from_url(redis_url)
    return {
        "sensitive": Queue(SENSITIVE_QUEUE_NAME, connection=conn),
        "cloud": Queue(CLOUD_QUEUE_NAME, connection=conn),
    }
