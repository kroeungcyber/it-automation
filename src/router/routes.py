# src/router/routes.py
from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.models.task import RouteDecision, TaskRecord, TaskRequest, TaskStatus
from src.router.classifier import Classifier, ClassificationResult
from src.router.payload_scanner import PayloadScanner, ScanResult

log = structlog.get_logger()
router = APIRouter()
scanner = PayloadScanner()

# Set by create_app() at startup
classifier: Classifier | None = None
queues: dict[str, Any] | None = None
session_factory: Any | None = None

# In-memory store; replaced by DB writes in Plan 2
task_store: dict[str, TaskRecord] = {}


class TaskCreateResponse(BaseModel):
    task_id: str
    route: str
    status: str


@router.post("/tasks", status_code=202, response_model=TaskCreateResponse)
async def create_task(request: TaskRequest) -> TaskCreateResponse:
    log.info("task.received", source=request.source, user=request.user_id)

    # Payload scanner runs before classification — any secret match → LOCAL
    if scanner.scan(request.raw_input) == ScanResult.SENSITIVE:
        log.warning("task.scanner.hit.rerouted_local", user=request.user_id)
        classification = ClassificationResult(route="local", method="failsafe")
    else:
        classification = classifier.classify(request.raw_input)

    route = RouteDecision.LOCAL if classification.route == "local" else RouteDecision.CLOUD
    record = TaskRecord(request=request, status=TaskStatus.QUEUED, route=route)
    task_store[str(request.id)] = record

    queue_key = "sensitive" if route == RouteDecision.LOCAL else "cloud"
    # Worker function path — implemented in Plan 2. Tasks will queue here until workers are deployed.
    queues[queue_key].enqueue("src.workers.process_task", record.model_dump_json())

    log.info(
        "task.enqueued",
        task_id=str(request.id),
        route=route.value,
        method=classification.method,
    )
    return TaskCreateResponse(
        task_id=str(request.id),
        route=route.value,
        status=TaskStatus.QUEUED.value,
    )


@router.get("/tasks/{task_id}", response_model=TaskRecord)
async def get_task(task_id: str) -> TaskRecord:
    record = task_store.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return record
