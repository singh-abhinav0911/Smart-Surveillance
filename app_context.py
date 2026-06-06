# app_context.py
# Single source of truth for shared singletons.
# Import from here — never from app.main — to avoid circular imports.

from queue import Queue
from core.shared_state import SharedState
from core.inference_worker import InferenceWorker
from core.event_engine import EventEngine
from core.alert_engine import AlertEngine
from services.pipeline_service import PipelineService
from config.settings import settings

shared_state     = SharedState()
event_queue      = Queue(maxsize=500)
inference_worker = InferenceWorker(shared_state)
event_engine     = EventEngine(saver_queue=event_queue)
alert_engine     = AlertEngine(shared_state, rules={})

pipeline_service = PipelineService(
    cameras=settings.CAMERAS,
    shared_state=shared_state,
    inference_worker=inference_worker,
    event_engine=event_engine,
    alert_engine=alert_engine
)