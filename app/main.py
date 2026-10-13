"""Moímetro local development server. Default deployment: 127.0.0.1 only.

WARNING: not certified for clinical use. Never connect to the public Internet.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, records, sensors, setup
from app.storage import init_db


@asynccontextmanager
async def lifespan(application: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Moímetro",
    description="Prototipo no validado clínicamente de sistema local de historias médicas.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None, redoc_url=None, openapi_url=None,
)
app.include_router(setup.router)
app.include_router(auth.router)
app.include_router(records.router)
app.include_router(sensors.router)
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'"
    )
    if request.url.path.startswith("/api/") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(static_dir / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "network_mode": "local", "clinical_validation": "pending"}
