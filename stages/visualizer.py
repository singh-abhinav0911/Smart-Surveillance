# stages/visualizer.py

import cv2
import queue
import threading
import time


class VisualizerStage:

    def __init__(self, input_queue, shared_state, output_queue=None):

        self.input_queue = input_queue
        self.shared_state = shared_state
        self.output_queue = output_queue
        self.running = True
        
        

        # ── FPS tracking ──────────────────────────────────────────────
        self.frame_count = 0
        self.fps = 0.0
        self.last_fps_time = time.time()

   

    def run(self):
        print("[VISUALIZER] started")
        print("running =", self.running)

        while self.running:

            # ── Get latest frame — drop stale ones ───────────────────
            message = None
            try:
                print("waiting, queue size =", self.input_queue.qsize())
                message = self.input_queue.get(timeout=0.1)
                print("got frame")

                # Drain queue — only show latest frame
                while True:
                    try:
                        message = self.input_queue.get_nowait()
                    except queue.Empty:
                        break

            except queue.Empty:
                continue

            if message is None:
                continue

            # ── Draw frame ────────────────────────────────────────────
            frame = message.frame.copy()
            self._draw(frame, message)
            self.shared_state.latest_frames[message.camera_id] = frame

            # ── FPS counter ───────────────────────────────────────────
            self.frame_count += 1
            now = time.time()
            if now - self.last_fps_time >= 1.0:
                self.fps = self.frame_count / (now - self.last_fps_time)
                self.frame_count = 0
                self.last_fps_time = now

            # ── Show FPS on frame ─────────────────────────────────────
            cv2.putText(frame, f"FPS: {self.fps:.1f}",
                        (20, frame.shape[0] - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (255, 255, 0), 2)

            # ── Display ───────────────────────────────────────────────
            cv2.imshow(f"Camera {message.camera_id}", frame)

            # ── waitKey MUST be in same thread as imshow ──────────────
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                self.running = False
                break

            # ── Optional next stage ───────────────────────────────────
            if self.output_queue:
                try:
                    self.output_queue.put_nowait(message)
                except queue.Full:
                    pass

        cv2.destroyAllWindows()
        print("[VISUALIZER] stopped")

    def _draw(self, frame, message):
        """All drawing logic separated for clarity."""

        analytics = getattr(message, "analytics", {})
        tracks = getattr(message, "tracks", [])

        # ── Counting line ─────────────────────────────────────────────
        h, w = frame.shape[:2]
        cv2.line(frame, (0, 300), (w, 300), (0, 255, 255), 2)

        # ── Tracks ────────────────────────────────────────────────────
        overspeed_count = 0
        for track in tracks:
            speed = getattr(track, "speed", None)
            plate = getattr(track, "plate", None)
            track_id = getattr(track, "global_id", getattr(track, "track_id", "?"))

            x1, y1, x2, y2 = map(int, track.bbox)
            color = (0, 0, 255) if (speed and speed > 60) else (0, 255, 0)

            if speed and speed > 60:
                overspeed_count += 1

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            label = f"ID {track_id}"
            if speed is not None:
                label += f" | {speed:.1f} km/h"
            if plate:
                label += f" | {plate}"

            cv2.putText(frame, label, (x1, max(y1 - 10, 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # ── Analytics overlay ─────────────────────────────────────────
        overlays = [
            (f"IN:  {analytics.get('in_count', 0)}",  (20, 40),  (0, 255, 0)),
            (f"OUT: {analytics.get('out_count', 0)}", (20, 80),  (0, 0, 255)),
            (f"OVERSPEED: {overspeed_count}",          (20, 120), (0, 0, 255)),
        ]
        for text, pos, color in overlays:
            cv2.putText(frame, text, pos,
                        cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

    def stop(self):
        self.running = False
        