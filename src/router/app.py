# src/router/app.py
from __future__ import annotations

from fastapi import FastAPI

from src.config import Settings
from src.db.connection import get_engine, get_session_factory
from src.queue.redis_queues import get_queues
from src.router import routes
from src.router.classifier import Classifier
from src.shared.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    configure_logging(settings.log_level)

    engine = get_engine(settings.database_url)
    session_factory = get_session_factory(engine)
    classifier = Classifier.from_config("config/classification_rules.yaml")
    app_queues = get_queues(settings.redis_url)

    routes.classifier = classifier
    routes.queues = app_queues
    routes.session_factory = session_factory

    app = FastAPI(title="IT Automation Router", version="0.1.0")
    app.include_router(routes.router)
    return app


app = create_app()
