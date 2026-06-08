"""Structured timing instrumentation for latency analysis."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, ParamSpec, TypeVar

logger = logging.getLogger("career_copilot.timing")

P = ParamSpec("P")
T = TypeVar("T")


class TimingReport:
    """Accumulates step timings for a request/job."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.steps: list[tuple[str, float]] = []
        self._started = time.perf_counter()

    def add(self, step: str, duration_ms: float) -> None:
        self.steps.append((step, duration_ms))

    @property
    def total_ms(self) -> float:
        return (time.perf_counter() - self._started) * 1000

    def log_summary(self, extra: dict[str, Any] | None = None) -> None:
        parts = " | ".join(f"{step}={ms:.0f}ms" for step, ms in self.steps)
        payload = extra or {}
        logger.info(
            "[TIMING] %s total=%.0fms | %s%s",
            self.name,
            self.total_ms,
            parts,
            f" | {payload}" if payload else "",
        )


@asynccontextmanager
async def timed_step(report: TimingReport | None, step: str):
    """Context manager that records async step duration."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info("[TIMING] %s.%s %.0fms", report.name if report else "step", step, duration_ms)
        if report:
            report.add(step, duration_ms)


def timed_node(step_name: str | None = None):
    """Decorator for LangGraph node functions."""

    def decorator(fn: Callable[P, Awaitable[dict[str, Any]]]):
        name = step_name or fn.__name__

        @wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> dict[str, Any]:
            start = time.perf_counter()
            try:
                return await fn(*args, **kwargs)
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                logger.info("[TIMING] node.%s %.0fms", name, duration_ms)

        return wrapper

    return decorator
