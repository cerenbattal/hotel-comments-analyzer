from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from .analysis import AnalysisError, ClaudeAnalyzer
from .config import get_settings
from .models import AskAnswer, AskRequest, HotelCandidate, Lang, Report
from .connectors import SourceError
from .service import NotFound, ReportService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    async with httpx.AsyncClient(timeout=20) as http:
        if not hasattr(app.state, "service"):  # tests inject their own
            app.state.service = ReportService(
                settings,
                ClaudeAnalyzer(settings.extraction_model, settings.summary_model),
                http,
            )
        yield


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


@app.get("/api/hotels/{hotel_id}/report", response_model=Report)
async def report(hotel_id: str, lang: Lang = "en", svc: ReportService = Depends(service)):
    try:
        return await svc.report(hotel_id, lang)
    except NotFound as e:
        raise HTTPException(404, "Hotel not found") from e
    except AnalysisError as e:
        raise HTTPException(502, str(e)) from e


@app.post("/api/hotels/{hotel_id}/ask", response_model=AskAnswer)
async def ask(hotel_id: str, body: AskRequest, svc: ReportService = Depends(service)):
    try:
        return await svc.ask(hotel_id, body.question, body.lang)
    except NotFound as e:
        raise HTTPException(404, "Hotel not found") from e
    except AnalysisError as e:
        raise HTTPException(502, str(e)) from e
