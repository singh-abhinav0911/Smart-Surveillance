from core import shared_state
from core.pipeline import Pipeline
from core.alert_engine import AlertEngine
import threading
import time
from cameras.webcam import WebcamCamera
from services.pipeline_service import PipelineService


alert_engine = AlertEngine(shared_state, {})


class CameraManager:

    def __init__(self, camera_sources, shared_state, inference_worker):

        self.camera_sources = camera_sources

        self.pipelines = {}
        self.shared_state = shared_state
        self.inference_worker = inference_worker
        self.running = True

        self.monitor_thread = None

    def start(self):

        self.running = True

        for camera_id, source in self.camera_sources.items():

            self.start_camera(camera_id, source)

        self.monitor_thread = threading.Thread(
            target=self.monitor_pipelines,
            daemon=True
        )

        self.monitor_thread.start()

    def start_camera(self, camera_id, source):

        camera = WebcamCamera(
            source=source,
            camera_id=camera_id
        )

        pipeline = Pipeline(
            camera_id=camera_id,
            camera=camera,
            shared_state=self.shared_state,
            inference_worker=self.inference_worker,
            event_engine=self.event_engine,
            alert_engine=self.alert_engine
        )

        pipeline.start()

    def stop(self):

        self.running = False

        for pipeline in self.pipelines.values():

            pipeline.stop()

        print("[INFO] Camera manager stopped")

    def monitor_pipelines(self):

        while self.running:

            for camera_id, pipeline in self.pipelines.items():

                if not pipeline.is_alive():

                    print(f"[WARNING] Camera {camera_id} crashed")

                    try:
                        pipeline.stop()
                    except:
                        pass

                    source = self.camera_sources[camera_id]

                    self.start_camera(camera_id, source)

                    print(f"[INFO] Camera {camera_id} restarted")

            time.sleep(5)

    def stop(self):
        self.running = False