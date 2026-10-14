"""Authenticated production API; shares the research engine with local examples."""
import hmac
import os
import asyncio
import logging
from urllib.parse import urlsplit
from contextlib import asynccontextmanager
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, CancelledError
from threading import Lock
from uuid import uuid4

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app import ROOT, run_backtest
from src.catalog import catalog
from src.assets import search_assets
from src.asset_directory import AssetDirectory
from src.quotes import get_quote
from src.saved_comparison import compare_saved
from src.paper import PaperTrading
from src.storage import ExperimentStore

security = HTTPBasic(auto_error=False)
pool = ThreadPoolExecutor(max_workers=2)
jobs, job_lock = {}, Lock()


def owner(credentials: HTTPBasicCredentials | None = Depends(security)):
    username, password = os.getenv("QUANTLAB_USERNAME", "researcher"), os.getenv("QUANTLAB_PASSWORD", "")
    if not password:
        if os.getenv("QUANTLAB_PUBLIC") == "1":
            raise HTTPException(503, "Private deployment requires QUANTLAB_PASSWORD.")
        return "local"
    if credentials is None or not (hmac.compare_digest(credentials.username.encode(), username.encode()) and hmac.compare_digest(credentials.password.encode(), password.encode())):
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Basic"})
    return username


def store():
    return ExperimentStore()


@asynccontextmanager
async def lifespan(application):
    if os.getenv("QUANTLAB_PUBLIC") == "1" and len(os.getenv("QUANTLAB_PASSWORD", "")) < 16:
        raise RuntimeError("Set a QUANTLAB_PASSWORD of at least 16 characters for a private hosted deployment.")
    if os.getenv('QUANTLAB_PUBLIC')=='1' and not os.getenv('QUANTLAB_DB_PATH'):
        raise RuntimeError('Set QUANTLAB_DB_PATH to a database on your persistent disk before deploying.')
    # Fail startup clearly if the configured storage is not writable.
    store()
    async def refresh_directories():
        while True:
            try:
                await asyncio.to_thread(AssetDirectory().refresh_due)
            except Exception:
                logging.getLogger(__name__).exception('Asset-directory refresh failed; retrying later.')
            await asyncio.sleep(3600)
    refresh_task = asyncio.create_task(refresh_directories())
    async def poll_paper():
        while True:
            try:
                await asyncio.to_thread(PaperTrading().tick_due)
            except Exception:
                logging.getLogger(__name__).exception('Paper polling failed; retrying in five seconds.')
            await asyncio.sleep(5)
    paper_task=asyncio.create_task(poll_paper())
    try:
        yield
    finally:
        refresh_task.cancel()
        paper_task.cancel()
        try:
            await refresh_task
        except asyncio.CancelledError:
            pass
        try:
            await paper_task
        except asyncio.CancelledError:
            pass


application = FastAPI(title="Backtest Lab", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@application.middleware("http")
async def request_limits(request: Request, call_next):
    if request.method == "POST":
        origin=request.headers.get('origin')
        if origin and urlsplit(origin).netloc.lower()!=request.headers.get('host','').lower():
            return JSONResponse({'error':'Cross-site requests are not allowed.'},status_code=403)
        try:
            if int(request.headers.get("content-length", "0")) > 4_100_000:
                return JSONResponse({"error": "Request is too large."}, status_code=413)
        except ValueError:
            return JSONResponse({"error": "Invalid content length."}, status_code=400)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 4_100_000:
                return JSONResponse({"error": "Request is too large."}, status_code=413)
        request._body = bytes(body)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@application.exception_handler(ValueError)
async def invalid_request(request, exc):
    return JSONResponse({"error": str(exc)}, status_code=400)


@application.exception_handler(KeyError)
async def missing_item(request, exc):
    return JSONResponse({"error": "Requested item or required field is missing."}, status_code=404)


@application.get("/health")
def health():
    return {"status": "ok", "engine_version": "3"}


@application.get("/")
def index(user=Depends(owner)):
    return FileResponse(ROOT / "index.html")


@application.get("/{asset}")
def asset(asset: str, user=Depends(owner)):
    if asset not in {"style.css", "app.js", "live.js", "research-ui.js", "navigation.js"}:
        raise HTTPException(404)
    return FileResponse(ROOT / asset)


@application.get("/api/catalog")
def options(user=Depends(owner)):
    return catalog()


@application.post("/api/assets/search")
def asset_search(payload: dict, user=Depends(owner)):
    return search_assets(payload.get("source", "market"), payload.get("query", ""))


@application.get('/api/assets/status')
def asset_directory_status(user=Depends(owner)):
    return AssetDirectory().status()


@application.post('/api/quote')
def quote(payload: dict, user=Depends(owner)):
    return get_quote(payload)


@application.get("/api/draft")
def draft(user=Depends(owner)):
    return store().draft(user)


@application.post("/api/draft")
def save_draft(payload: dict, user=Depends(owner)):
    store().save_draft(user, payload)
    return {"saved": True}


def execute(payload, user, cancel_check=None):
    result, data = run_backtest(payload, include_data=True, cancel_check=cancel_check)
    if cancel_check and cancel_check(): raise CancelledError()
    return store().save(user, payload, result, data) if not result["demo"] else result


@application.post("/api/backtest")
def backtest(payload: dict, user=Depends(owner)):
    return execute(payload, user)


@application.get("/api/experiments")
def experiments(user=Depends(owner)):
    return store().list(user)


@application.post('/api/experiments/compare')
def compare_experiments(payload: dict,user=Depends(owner)):
    return compare_saved(user,payload.get('ids'),bool(payload.get('harmonize')))


@application.get('/api/paper')
def paper_sessions(user=Depends(owner)):
    return PaperTrading().list(user)


@application.post('/api/paper')
def start_paper(payload: dict,user=Depends(owner)):
    return PaperTrading().start(user,payload)


@application.post('/api/paper/{identifier}/stop')
def stop_paper(identifier: str,user=Depends(owner)):
    return PaperTrading().stop(user,identifier)


@application.get("/api/experiments/{identifier}")
def experiment(identifier: str, user=Depends(owner)):
    return store().get(user, identifier)


@application.post("/api/replay")
def replay(payload: dict, user=Depends(owner)):
    database = store()
    record = database.get(user, payload["id"])
    data = pd.read_csv(StringIO(database.dataset(user, payload["id"])), index_col=0, parse_dates=True)
    result = run_backtest(record["config"], data=data)
    return {**result, "dataset_hash": record["dataset_hash"], "replayed": True}


@application.post("/api/jobs", status_code=202)
def create_job(payload: dict, user=Depends(owner)):
    identifier = uuid4().hex
    with job_lock:
        active = sum(job["state"] in {"queued", "running"} for job in jobs.values())
        if active >= 4:
            raise HTTPException(429, "The research queue is full. Wait for a run to finish.")
        # Retain only recent terminal jobs; finished experiments are in SQLite.
        for key in list(jobs)[:-100]:
            if jobs[key]["state"] not in {"queued", "running"}: jobs.pop(key)
        jobs[identifier] = {"owner": user, "state": "queued"}
    def work():
        with job_lock:
            if jobs[identifier]["state"] == "cancelled": return
            jobs[identifier]["state"] = "running"
        try:
            def cancelled():
                with job_lock: return jobs[identifier]["state"] == "cancelled"
            result = execute(payload, user, cancelled)
            with job_lock:
                if jobs[identifier]["state"] != "cancelled": jobs[identifier].update(state="complete", result=result)
        except Exception as exc:
            with job_lock:
                if jobs[identifier]["state"] != "cancelled": jobs[identifier].update(state="failed", error=str(exc) if isinstance(exc, ValueError) else "Backtest failed. Check the configuration and provider connection.")
    pool.submit(work)
    return {"id": identifier, "state": "queued"}


@application.get("/api/jobs/{identifier}")
def job(identifier: str, user=Depends(owner)):
    with job_lock:
        record = jobs.get(identifier)
        if record is None or record["owner"] != user: raise HTTPException(404)
        return {k: v for k, v in record.items() if k != "owner"}


@application.post("/api/jobs/{identifier}/cancel")
def cancel(identifier: str, user=Depends(owner)):
    with job_lock:
        record = jobs.get(identifier)
        if record is None or record["owner"] != user: raise HTTPException(404)
        if record["state"] in {"queued", "running"}: record["state"] = "cancelled"
    return {"state": record["state"], "note": "Downloads may finish, but simulation stops at the next bar. Cancelled work is not saved."}
