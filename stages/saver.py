# stages/saver.py

import os
import json
import queue
import cv2
from datetime import datetime
from database.database_manager import DatabaseManager


class SaverStage:

    def __init__(self, input_queue):
        self.input_queue = input_queue
        self.running     = False
        self.db          = DatabaseManager()

        # Create dirs for saving violation images
        os.makedirs("data/events/violations", exist_ok=True)
        os.makedirs("data/events/detections", exist_ok=True)

    def run(self):
        print("[SAVER] started")
        self.running = True

        while self.running:
            try:
                packet = self.input_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[SAVER] queue error: {e}")
                continue

            try:
                self._process(packet)
            except Exception as e:
                print(f"[SAVER] process error: {e}")

    def _process(self, packet):

        # ── Regular detection event ───────────────────────────────────
        if "db_event" in packet:
            event = packet["db_event"]
            try:
                self.db.insert_detection(
                    object_type=event.get("vehicle_type"),
                    image_path="",
                    track_id=event.get("track_id"),
                    plate_number=event.get("plate_number"),
                    camera_name=event.get("camera_id"),
                    speed_kmh=event.get("speed_kmh")
                )
            except Exception as e:
                print(f"[SAVER] insert_detection error: {e}")
            return

        # ── Violation event ───────────────────────────────────────────
        if "violation" in packet:
            v     = packet["violation"]
            frame = packet.get("frame")

            # Save snapshot image
            image_path = self._save_image(frame, v.get("violation_type"),
                                          v.get("camera_id"),
                                          v.get("track_id"))

            # Save to DB
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
                print(f"[SAVER] insert_violation error: {e}")
            return

        print(f"[SAVER] unknown packet type: {packet.keys()}")

    def _save_image(self, frame, violation_type, camera_id, track_id):
        """Save violation frame as image. Returns path or None."""
        if frame is None:
            return None
        try:
            ts       = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            v_type   = violation_type or "unknown"
            cam      = camera_id or "cam"
            filename = f"data/events/violations/{v_type}_{cam}_{track_id}_{ts}.jpg"
            cv2.imwrite(filename, frame)
            print(f"[SAVER] image saved: {filename}")
            return filename
        except Exception as e:
            print(f"[SAVER] image save error: {e}")
            return None

    def stop(self):
        self.running = False
        print("[SAVER] stopped")