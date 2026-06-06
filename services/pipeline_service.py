from core.pipeline import Pipeline
from threading import Thread
from utils.logger import get_logger
from core.reid_manager import ReIDManager
from core.reid_worker import ReIDWorker 
from core.reid_model import ReIDModel

log = get_logger("pipeline_service")


class PipelineService:

    def __init__(self, cameras, shared_state, inference_worker, event_engine, alert_engine):

        self.cameras = cameras
        self.shared_state = shared_state
        self.inference_worker = inference_worker
        self.event_engine = event_engine
        self.alert_engine = alert_engine
        # -------------------------
        # GLOBAL REID SYSTEM (IMPORTANT FIX)
        # -------------------------
        self.reid_manager = ReIDManager()
        self.reid_model = ReIDModel()

        self.reid_worker = ReIDWorker(
            reid_manager=self.reid_manager,
            model=self.reid_model
        )

        self.pipelines = {}
        self.threads = {}

    def start_all(self):

        
        self.reid_worker.start()

        for camera_id, source in self.cameras.items():

            pipeline = Pipeline(
                camera_id=camera_id,
                camera=source,
                shared_state=self.shared_state,
                inference_worker=self.inference_worker,
                event_engine=self.event_engine,
                alert_engine=self.alert_engine,
                reid_worker=self.reid_worker,
                reid_manager=self.reid_manager
            )

            self.pipelines[camera_id] = pipeline

            t = Thread(target=pipeline.start, daemon=True)
            t.start()

            self.threads[camera_id] = t

            log.info(f"Started {camera_id}")

    def stop_all(self):

        self.reid_worker.stop()

        for cam_id, pipeline in self.pipelines.items():
            pipeline.stop()

        log.info("All stopped")

    def status(self):
        return {
            cam_id: thread.is_alive()
            for cam_id, thread in self.threads.items()
        }