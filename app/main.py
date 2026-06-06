# app/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from app_context import inference_worker, pipeline_service
from app.routes import events
from app.routes.stream     import router as stream_router
from app.routes.health import router as health_router

from app.routes.violations import router as violations_router
from app.routes.api        import router as api_router
from app.ws.events_ws      import router as ws_router
from utils.logger import get_logger
from config.settings import settings

log = get_logger("app")

# -- Lifespan -----------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting inference worker...")
    inference_worker.start()

    log.info(f"Starting pipelines for cameras: {list(settings.CAMERAS.keys())}")
    pipeline_service.start_all()

    yield

    log.info("Stopping pipelines...")
    pipeline_service.stop_all()

# -- App ----------------------------------------------------------
app = FastAPI(lifespan=lifespan)
os.makedirs("data/events/violations", exist_ok=True)
app.mount("/snapshots", StaticFiles(directory="data/events/violations"), name="snapshots")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(events.router)
app.include_router(api_router)
app.include_router(ws_router)
app.include_router(stream_router)
app.include_router(violations_router)
app.include_router(health_router)