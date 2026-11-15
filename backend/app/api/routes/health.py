"""A simple liveness endpoint: it does not check future data sources."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    service: Literal["PLANETREX"] = "PLANETREX"
    status: Literal["healthy"] = "healthy"


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Confirm the web process is responding, not that datasets are available."""
    return HealthResponse()
