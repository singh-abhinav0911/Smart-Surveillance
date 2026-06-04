import time
from queue import Queue, Full, Empty
from threading import Thread

from ultralytics import YOLO
from core.detector import Detector
from core.messages import DetectionPacket
from utils.queue_utils import safe_put


class InferenceWorker:

    def __init__(self, shared_state, batch_size=4, queue_maxsize=4):

        # ── FIXED: maxsize=4 not 100 ──────────────────────────────────
        # Only buffer a few frames — old frames are useless in surveillance
        self.input_queue = Queue(maxsize=queue_maxsize)

        self.running = False
        self.shared_state = shared_state
        self.detector = Detector()
        self.batch_size = batch_size

        # ── Stats ─────────────────────────────────────────────────────
        self.total_frames = 0
        self.total_dropped = 0
        self.last_fps_time = time.time()
        self.fps = 0.0

    # ── Submit (blocking=False — drops if busy) ───────────────────────
    def submit(self, message, callback):
        try:
            self.input_queue.put_nowait((message, callback))
        except Full:
            self.total_dropped += 1

    # ── NEW: submit_if_free returns bool ─────────────────────────────
    def submit_if_free(self, message, callback):
        try:
            self.input_queue.put_nowait((message, callback))
            return True
        except Full:
            self.total_dropped += 1
            return False

    def run(self):
        print("[INFERENCE] thread alive")

        while self.running:

            batch = []
            callbacks = []

            # ── Collect batch ─────────────────────────────────────────
            # Block on first item so thread doesn't spin when idle
            try:
                message, callback = self.input_queue.get(timeout=0.1)
                batch.append(message)
                callbacks.append(callback)
            except Empty:
                continue

            # ── Grab remaining items without blocking ─────────────────
            while len(batch) < self.batch_size:
                try:
                    message, callback = self.input_queue.get_nowait()
                    batch.append(message)
                    callbacks.append(callback)
                except Empty:
                    break

            if not batch:
                continue

            # ── Run inference ─────────────────────────────────────────
            t0 = time.time()
            frames = [m.frame for m in batch]
            results = [self.detector.detect(frame) for frame in frames]
            inference_ms = (time.time() - t0) * 1000

            # ── Update FPS stat ───────────────────────────────────────
            self.total_frames += len(batch)
            now = time.time()
            if now - self.last_fps_time >= 2.0:
                elapsed = now - self.last_fps_time
                self.fps = self.total_frames / elapsed
                self.total_frames = 0
                self.last_fps_time = now
                print(f"[INFERENCE] {self.fps:.1f} FPS | "
                      f"batch={len(batch)} | "
                      f"latency={inference_ms:.0f}ms | "
                      f"queue={self.input_queue.qsize()} | "
                      f"dropped={self.total_dropped}")

            # ── Dispatch results ──────────────────────────────────────
            for message, result, callback in zip(batch, results, callbacks):

                # Update shared state
                self.shared_state.active_tracks[message.camera_id] = result

                # Build result packet
                result_packet = DetectionPacket(
                    camera_id=message.camera_id,
                    frame=message.frame,
                    detections=result,
                    timestamp=time.time()
                )

                print(
                    f"[INFERENCE] sending {len(result)} detections "
                    f"to {message.camera_id}"
                )

                # ── FIXED: drop result if downstream queue full ───────
                # Don't block inference thread waiting for visualizer
                safe_put(callback, (message.camera_id, result_packet))

    def start(self):
        self.running = True
        thread = Thread(target=self.run, daemon=True)
        thread.start()
        print("[INFERENCE] started")

    def stop(self):
        self.running = False
        print(f"[INFERENCE] stopped | total dropped: {self.total_dropped}")