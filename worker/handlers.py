"""Job handlers executed by the background worker.

Each handler receives a validated payload dict and returns a JSON-safe
mapping that is persisted as the job result.  The heaviest numerical
work (FEM, ray tracing, hybrid synthesis) runs here instead of blocking
the API request path.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from api.jobs import JobHandler, JOB_KINDS
from api.routes import (
    _fem_mode_payload,
    _hybrid_payload,
    _ray_trace_payload,
)
from api.schemas import FEM2DRequest, HybridRequest, RayTraceRequest


def _run_hybrid(payload: dict[str, Any]) -> Mapping[str, Any]:
    data = HybridRequest.model_validate(payload)
    return _hybrid_payload(data).model_dump(mode="json")


def _run_ray_tracing(payload: dict[str, Any]) -> Mapping[str, Any]:
    data = RayTraceRequest.model_validate(payload)
    return _ray_trace_payload(data).model_dump(mode="json")


def _run_fem2d(payload: dict[str, Any]) -> Mapping[str, Any]:
    data = FEM2DRequest.model_validate(payload)
    return _fem_mode_payload(data).model_dump(mode="json")


JOB_HANDLERS: Mapping[str, JobHandler] = {
    "numerical.hybrid": _run_hybrid,
    "numerical.ray-tracing": _run_ray_tracing,
    "numerical.fem2d": _run_fem2d,
}


def get_job_handlers() -> Mapping[str, JobHandler]:
    """Return the handlers declared by this worker alongside their kinds."""
    return JOB_HANDLERS


def handler_kinds() -> set[str]:
    return set(JOB_KINDS) & set(JOB_HANDLERS)
