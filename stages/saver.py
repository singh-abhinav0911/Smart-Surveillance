# stages/saver.py

import os
import json
import queue
import time
import threading
import cv2
from datetime import datetime
from utils.logger import get_logger
from database.database_manager import DatabaseManager

log = get_logger("saver")

# -- Retention policy -----------------------------------------------------
# Snapshots older than this will be deleted by the cleanup thread.
# Override via env var SNAPSHOT_RETENTION_DAYS (default 7).
MAX_AGE_DAYS    = int(os.getenv("SNAPSHOT_RETENTION_DAYS", "7"))
CLEANUP_INTERVAL = 3600  # run cleanup every hour


class SaverStage:

    def __init__(self, input_queue):
        self.input_queue = input_queue
        self.running     = False
        self.db          = DatabaseManager()

        os.makedirs("data/events/violations", exist_ok=True)
        os.makedirs("data/events/detections", exist_ok=True)

        # Start background retention cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._retention_loop,
            daemon=True,
            name="snapshot-cleanup"
        )
        self._cleanup_thread.start()

    def run(self):
        log.info("started")
        self.running = True

        while self.running:
            try:
                packet = self.input_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            except Exception as e:
                log.debug(f"queue error: {e}")
                continue

            try:
                self._process(packet)
            except Exception as e:
                log.debug(f"process error: {e}")

    def _process(self, packet):

        # -- Regular detection event ----------------------------------
        if "db_event" in packet:
            event = packet["db_event"]
            try:
                self.db.insert_detection(
                    object_type  = event.get("vehicle_type"),
                    image_path   = "",
                    track_id     = event.get("track_id"),
                    plate_number = event.get("plate_number"),
                    camera_name  = event.get("camera_id"),
                    speed_kmh    = event.get("speed_kmh")
                )
            except Exception as e:
                log.debug(f"insert_detection error: {e}")
            return

        # -- Violation event ------------------------------------------
        if "violation" in packet:
            v     = packet["violation"]
            frame = packet.get("frame")

            image_path = self._save_image(
                frame,
                v.get("violation_type"),
                v.get("camera_id"),
                v.get("track_id")
            )

            try:
                self.db.insert_violation(
                    camera_id      = v.get("camera_id"),
                    track_id       = v.get("track_id"),
                    global_id      = v.get("global_id"),
                    violation_type = v.get("violation_type"),
                    object_type    = v.get("object_type"),
                    bbox           = v.get("bbox"),
                    speed_kmh      = v.get("speed_kmh"),
                    zone_id        = v.get("zone_id"),
                    metadata       = v.get("metadata", {}),
                    image_path     = image_path
                )
            except Exception as e:
                log.debug(f"insert_violation error: {e}")
            return

        log.debug(f"unknown packet type: {list(packet.keys())}")

    def _save_image(self, frame, violation_type, camera_id, track_id):
        """Save violation frame as JPEG. Returns path or None."""
        if frame is None:
            return None
        try:
            ts       = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            v_type   = violation_type or "unknown"
            cam      = camera_id or "cam"
            filename = f"data/events/violations/{v_type}_{cam}_{track_id}_{ts}.jpg"
            cv2.imwrite(filename, frame)
            log.info(f"image saved: {filename}")
            return filename
        except Exception as e:
            log.error(f"image save error: {e}")
            return None

    # -- Retention cleanup --------------------------------------------
    def _retention_loop(self):
        """Background thread: delete snapshots older than MAX_AGE_DAYS."""
        log.info(f"retention policy: {MAX_AGE_DAYS} days (checks every {CLEANUP_INTERVAL}s)")
        while True:
            try:
                self._cleanup_old_snapshots()
            except Exception as e:
                log.error(f"retention cleanup error: {e}")
            time.sleep(CLEANUP_INTERVAL)

    def _cleanup_old_snapshots(self):
        folder    = "data/events/violations"
        now       = time.time()
        cutoff    = now - (MAX_AGE_DAYS * 86400)
        deleted   = 0
        freed     = 0

        if not os.path.isdir(folder):
            return

        for fname in os.listdir(folder):
            if not fname.endswith(".jpg"):
                continue
            fpath = os.path.join(folder, fname)
            try:
                mtime = os.path.getmtime(fpath)
                if mtime < cutoff:
                    size = os.path.getsize(fpath)
                    os.remove(fpath)
                    deleted += 1
                    freed   += size
            except Exception as e:
                log.debug(f"cleanup skip {fname}: {e}")

        if deleted:
            freed_mb = freed / (1024 * 1024)
            log.info(f"retention: deleted {deleted} snapshots, freed {freed_mb:.1f} MB")

    def stop(self):
        self.running = False
        log.info("stopped")