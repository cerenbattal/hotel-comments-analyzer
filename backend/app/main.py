from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .analysis import AnalysisError, ClaudeAnalyzer
from .config import get_settings
from .connectors import SourceError
from .db import make_engine, make_sessionmaker
from .migrate import upgrade as migrate_db
from .models import AskAnswer, AskRequest, HistoryPoint, HotelCandidate, Lang, ReportJob
from .scheduler import run_daily
from .service import NotFound, ReportService


@asynccontextmanager
async def lifespan(app: FastAPI):
    if hasattr(app.state, "service"):  # tests inject their own
        yield
        return
    settings = get_settings()
    await asyncio.to_thread(migrate_db, settings.database_url)
    engine = make_engine(settings.database_url)
    async with httpx.AsyncClient(timeout=20) as http:
        svc = ReportService(
            settings,
            ClaudeAnalyzer(settings.extraction_model, settings.summary_model),
            http,
            make_sessionmaker(engine),
        )
        app.state.service = svc
        refresher = (
            asyncio.create_task(run_daily(svc.refresh_scores, settings.daily_refresh_hour_utc))
            if settings.daily_refresh
            else None
        )
        yield
        if refresher:
            refresher.cancel()
        await svc.wait_for_builds()
    await engine.dispose()


app = FastAPI(title="Hotel Comments Analyzer", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def service(request: Request) -> ReportService:
    return request.app.state.service


@app.get("/api/health")
async def health(svc: ReportService = Depends(service)):
    return {"ok": True, "demo_mode": svc.demo_mode}


@app.get("/api/hotels/search", response_model=list[HotelCandidate])
async def search(
    q: str = Query(min_length=2, max_length=200),
    lang: Lang = "en",
    svc: ReportService = Depends(service),
):
    try:
        return await svc.search(q, lang)
    except SourceError as e:
        raise HTTPException(502, str(e)) from e


@app.post("/api/hotels/{hotel_id}/report", response_model=ReportJob)
async def start_report(
    hotel_id: str, response: Response, lang: Lang = "en", svc: ReportService = Depends(service)
):
    """Start building a report (or return a fresh one). Poll GET until status is not 'running'."""
    job = await svc.start_report(hotel_id, lang)
    response.status_code = 202 if job.status == "running" else 200
    return job


@app.get("/api/hotels/{hotel_id}/report", response_model=ReportJob)
async def get_report(hotel_id: str, lang: Lang = "en", svc: ReportService = Depends(service)):
    job = await svc.get_report(hotel_id, lang)
    if job is None:
        raise HTTPException(404, "No report yet; POST to start one")
    return job


@app.get("/api/hotels/{hotel_id}/history", response_model=list[HistoryPoint])
async def history(hotel_id: str, svc: ReportService = Depends(service)):
    return await svc.history(hotel_id)


@app.post("/api/hotels/{hotel_id}/ask", response_model=AskAnswer)
async def ask(hotel_id: str, body: AskRequest, svc: ReportService = Depends(service)):
    try:
        return await svc.ask(hotel_id, body.question, body.lang)
    except NotFound as e:
        raise HTTPException(404, "Hotel not found") from e
    except AnalysisError as e:
        raise HTTPException(502, str(e)) from e
