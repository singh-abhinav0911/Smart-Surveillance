# core/pipeline.py

from queue import Queue
from threading import Thread

from utils.logger import get_logger
from core.alert_engine import AlertEngine
from core.speed_estimator import SpeedEstimator
from core.reid_worker import ReIDWorker
from core.reid_manager import ReIDManager
from config.settings import settings
from config.zones import ZONES
from core.zones.zone_manager import ZoneManager
from stages.frame_reader import FrameReader
from stages.tracker import TrackerStage
from stages.analytics import AnalyticsStage
from stages.saver import SaverStage
from stages.anpr import ANPRStage

log = get_logger("pipeline")


class Pipeline:

    def __init__(
        self,
        camera_id,
        camera,
        shared_state,
        inference_worker,
        event_engine,
        alert_engine,
        reid_worker,
        reid_manager
    ):
        self.camera_id        = camera_id
        self.camera           = camera
        self.shared_state     = shared_state
        self.inference_worker = inference_worker
        self.reid_worker      = reid_worker
        self.reid_manager     = reid_manager
        self.event_engine     = event_engine
        self.alert_engine     = alert_engine
        self.running          = False

        # -- Per-camera components --------------------------------
        self.anpr = ANPRStage()

        self.speed_estimator = SpeedEstimator(
            pixels_per_meter=settings.PIXELS_PER_MTR,
            speed_limit=settings.SPEED_LIMIT
        )

        self.zone_manager = ZoneManager(
            ZONES.get(camera_id, [])
        )

        # -- Queues -----------------------------------------------
        # maxsize=1/2: stages always process the LATEST data.
        # Old frames are dropped — no lag buildup.
        # db_queue is larger so DB writes are not dropped.
        # visual_queue is read by main.py display loop only.
        self.tracking_queue  = Queue(maxsize=2)
        self.analytics_queue = Queue(maxsize=2)
        self.stream_queue    = Queue(maxsize=1)
        self.visual_queue    = Queue(maxsize=1)
        self.db_queue        = Queue(maxsize=50)

        # -- Stages -----------------------------------------------
        self.reader = FrameReader(
            camera_id=camera_id,
            camera=camera,
            output_queue=self.tracking_queue,
            inference_worker=inference_worker,
            inference_every_n=settings.INFERENCE_EVERY_N
        )

        self.tracker = TrackerStage(
            input_queue=self.tracking_queue,
            output_queue=self.analytics_queue,
            reid_worker=self.reid_worker,
            reid_manager=self.reid_manager
        )

        line_y = camera.line_y if hasattr(camera, "line_y") else settings.LINE_Y

        self.analytics = AnalyticsStage(
            input_queue=self.analytics_queue,
            output_queue=self.visual_queue,
            db_queue=self.db_queue,
            event_engine=self.event_engine,
            alert_engine=self.alert_engine,
            zone_manager=self.zone_manager,
            camera_id=camera_id,
            line_y=line_y,
            speed_estimator=self.speed_estimator,
            anpr=self.anpr,
            stream_queue=self.stream_queue
        )

        # NOTE: VisualizerStage intentionally removed from threads.
        # main.py reads self.visual_queue directly in its display loop.

        self.saver = SaverStage(
            input_queue=self.db_queue
        )

        # -- Threads ----------------------------------------------
        self.threads = [
            Thread(target=self.reader.run,    daemon=True, name=f"reader-{camera_id}"),
            Thread(target=self.tracker.run,   daemon=True, name=f"tracker-{camera_id}"),
            Thread(target=self.analytics.run, daemon=True, name=f"analytics-{camera_id}"),
            Thread(target=self.saver.run,     daemon=True, name=f"saver-{camera_id}"),
        ]

    def start(self):
        self.running = True
        log.info(f"Starting camera {self.camera_id}")
        for t in self.threads:
            t.start()
        log.info(f"All threads started for {self.camera_id}")

    def stop(self):
        self.running = False
        self.reader.stop()
        self.tracker.stop()
        self.analytics.stop()
        self.saver.stop()
        for t in self.threads:
            t.join(timeout=2.0)
        log.info(f"Camera {self.camera_id} stopped")

    def is_alive(self):
        return all(t.is_alive() for t in self.threads)

    def get_stats(self):
        return {
            "camera_id":       self.camera_id,
            "tracking_queue":  self.tracking_queue.qsize(),
            "analytics_queue": self.analytics_queue.qsize(),
            "visual_queue":    self.visual_queue.qsize(),
            "stream_queue":    self.stream_queue.qsize(),
            "db_queue":        self.db_queue.qsize(),
            "threads_alive":   [t.is_alive() for t in self.threads],
            "threads_names":   [t.name for t in self.threads],
            "is_alive":        self.is_alive(),       
        }