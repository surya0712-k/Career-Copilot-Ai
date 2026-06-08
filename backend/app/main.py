import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.routes import analysis, auth, goals, interviews, livekit, memory, profiles, progress, roadmaps
from app.config import get_settings
from app.db.session import AsyncSessionLocal, engine
from app.memory.qdrant_client import ensure_collection
from app.models import AnalysisJob
from app.models.base import Base

logger = logging.getLogger(__name__)


async def _fail_stale_analysis_jobs() -> None:
    """Jobs left 'running' after a reload/restart can never finish."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AnalysisJob).where(AnalysisJob.status == "running"))
        stale = result.scalars().all()
        for job in stale:
            job.status = "failed"
            job.error = "Analysis was interrupted. Please run it again."
        if stale:
            await db.commit()
            logger.info("Marked %d stale analysis job(s) as failed", len(stale))


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_collection()
    await _fail_stale_analysis_jobs()
    yield
    await engine.dispose()


settings = get_settings()

app = FastAPI(
    title="Career Copilot AI",
    description="Agentic career coach with memory",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger(__name__)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    headers = dict(exc.headers or {})
    origin = request.headers.get("origin")
    if origin and origin in settings.cors_origin_list:
        headers.setdefault("Access-Control-Allow-Origin", origin)
        headers.setdefault("Access-Control-Allow-Credentials", "true")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Return JSON 500 so CORS middleware can attach headers (browser otherwise reports CORS)."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    headers: dict[str, str] = {}
    origin = request.headers.get("origin")
    if origin and origin in settings.cors_origin_list:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(status_code=500, content={"detail": "Internal server error"}, headers=headers)


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
app.include_router(goals.router, prefix="/goals", tags=["goals"])
app.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
app.include_router(roadmaps.router, prefix="/roadmaps", tags=["roadmaps"])
app.include_router(interviews.router, prefix="/interviews", tags=["interviews"])
app.include_router(livekit.router, prefix="/livekit", tags=["livekit"])
app.include_router(progress.router, prefix="/progress", tags=["progress"])
app.include_router(memory.router, prefix="/memory", tags=["memory"])


@app.get("/health")
async def health():
    return {"status": "ok"}
