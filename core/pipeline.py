# core/pipeline.py
#
# CHANGES FROM ORIGINAL:
#   - VisualizerStage removed from pipeline threads entirely.
#     main.py reads visual_queue directly — having two consumers
#     (VisualizerStage thread + main.py loop) caused frames to be
#     silently stolen, so the display window showed nothing.
#   - VisualizerStage import removed (it's now dead code — delete
#     stages/visualizer.py when ready).
#   - All other stages and queues unchanged.

from queue import Queue
from threading import Thread

from core.alert_engine import AlertEngine
from core.speed_estimator import SpeedEstimator
from core.reid_worker import ReIDWorker
from core.reid_manager import ReIDManager

from config.zones import ZONES
from core.zones.zone_manager import ZoneManager

from stages.frame_reader import FrameReader
from stages.tracker import TrackerStage
from stages.analytics import AnalyticsStage
from stages.saver import SaverStage
from stages.anpr import ANPRStage


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

        # ── Per-camera components ─────────────────────────────────────
        self.anpr = ANPRStage()

        self.speed_estimator = SpeedEstimator(
            pixels_per_meter=10,
            speed_limit=60
        )

        self.zone_manager = ZoneManager(
            ZONES.get(camera_id, [])
        )

        # ── Queues ────────────────────────────────────────────────────
        # maxsize=1: each stage always processes the LATEST data.
        # Old frames are dropped — no lag buildup.
        # Exception: db_queue is larger so DB writes aren't dropped.
        #
        # visual_queue is read by main.py (display loop), NOT by any
        # pipeline thread. Keep maxsize=1 so display always shows latest.
        self.tracking_queue  = Queue(maxsize=2)
        self.analytics_queue = Queue(maxsize=2)
        self.visual_queue    = Queue(maxsize=1)   # consumed by main.py only
        self.db_queue        = Queue(maxsize=50)  # consumed by SaverStage

        # ── Stages ───────────────────────────────────────────────────
        self.reader = FrameReader(
            camera_id=camera_id,
            camera=camera,
            output_queue=self.tracking_queue,
            inference_worker=inference_worker,
            inference_every_n=2
        )

        self.tracker = TrackerStage(
            input_queue=self.tracking_queue,
            output_queue=self.analytics_queue,
            reid_worker=self.reid_worker,
            reid_manager=self.reid_manager
        )

        self.analytics = AnalyticsStage(
            input_queue=self.analytics_queue,
            output_queue=self.visual_queue,
            db_queue=self.db_queue,
            event_engine=self.event_engine,
            alert_engine=self.alert_engine,
            zone_manager=self.zone_manager,
            camera_id=camera_id,
            line_y=camera.line_y if hasattr(camera, "line_y") else 360,
            speed_estimator=self.speed_estimator,
            anpr=self.anpr
        )

        # NOTE: VisualizerStage intentionally removed from threads.
        # main.py reads self.visual_queue directly in its display loop.
        # Having both a VisualizerStage thread AND main.py reading the
        # same queue means only one of them gets each frame — the window
        # shows nothing half the time.

        self.saver = SaverStage(
            input_queue=self.db_queue
        )

        # ── Threads ───────────────────────────────────────────────────
        # Stages are plain classes — no threads inside them.
        # Pipeline owns all threads.
        self.threads = [
            Thread(target=self.reader.run,    daemon=True, name=f"reader-{camera_id}"),
            Thread(target=self.tracker.run,   daemon=True, name=f"tracker-{camera_id}"),
            Thread(target=self.analytics.run, daemon=True, name=f"analytics-{camera_id}"),
            Thread(target=self.saver.run,     daemon=True, name=f"saver-{camera_id}"),
        ]

    def start(self):
        self.running = True
        print(f"[Pipeline] Starting camera {self.camera_id}")
        for t in self.threads:
            t.start()
        print(f"[Pipeline] All threads started for {self.camera_id}")

    def stop(self):
        self.running = False
        self.reader.stop()
        self.tracker.stop()
        self.analytics.stop()
        self.saver.stop()

        for t in self.threads:
            t.join(timeout=2.0)

        print(f"[Pipeline] Camera {self.camera_id} stopped")

    def is_alive(self):
        return all(t.is_alive() for t in self.threads)

    def get_stats(self):
        return {
            "camera_id":      self.camera_id,
            "tracking_queue": self.tracking_queue.qsize(),
            "analytics_queue":self.analytics_queue.qsize(),
            "visual_queue":   self.visual_queue.qsize(),
            "db_queue":       self.db_queue.qsize(),
            "threads_alive":  [t.is_alive() for t in self.threads],
            "threads_names":  [t.name for t in self.threads],
        }