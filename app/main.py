# app/main.py

from contextlib import asynccontextmanager
from queue import Queue

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.alert_engine import AlertEngine
from core.event_engine import EventEngine
from core.shared_state import SharedState
from core.inference_worker import InferenceWorker
from services.pipeline_service import PipelineService
from app.routes import events
from app.routes.stream     import router as stream_router
from app.routes.violations import router as violations_router

from app.routes.api import router as api_router
from app.ws.events_ws import router as ws_router

# ── Boot system ───────────────────────────────────────────────────────────────
rules        = {}
shared_state = SharedState()

event_queue = Queue(maxsize=500)

inference_worker = InferenceWorker(shared_state)

event_engine = EventEngine(saver_queue=event_queue)
alert_engine = AlertEngine(shared_state, rules)

cameras = {
    "gate_1": "data/test_videos/test.mp4"
}

pipeline_service = PipelineService(
    cameras=cameras,
    shared_state=shared_state,
    inference_worker=inference_worker,
    event_engine=event_engine,
    alert_engine=alert_engine
)

# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[APP] Starting inference worker...")
    inference_worker.start()

    print("[APP] Starting pipelines...")
    pipeline_service.start_all()

    yield  # app runs here

    print("[APP] Stopping pipelines...")
    pipeline_service.stop_all()

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(events.router)
app.include_router(api_router)       # ← /api/stats, /api/violations
app.include_router(ws_router)
app.include_router(stream_router)
app.include_router(violations_router)