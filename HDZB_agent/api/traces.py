"""Trace inspection endpoints used by evaluation and error analysis."""

from typing import Callable

from fastapi import APIRouter, Query


def create_traces_router(get_trace_store: Callable[[], object]) -> APIRouter:
    router = APIRouter(tags=["tracing"])

    @router.get("/agent/traces")
    async def list_traces(
        limit: int = Query(50, ge=1, le=500),
        session_id: str | None = None,
    ):
        """List recent request traces, newest first."""
        return {"traces": get_trace_store().list(limit=limit, session_id=session_id)}

    return router
