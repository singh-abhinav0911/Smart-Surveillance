# core/inference_worker.py

import time
from queue import Queue, Full, Empty
from threading import Thread

from utils.logger import get_logger
from core.detector import Detector
from core.messages import DetectionPacket
from utils.queue_utils import safe_put

log = get_logger("inference")


class InferenceWorker:

    def __init__(self, shared_state, batch_size=4, queue_maxsize=4):
        self.input_queue  = Queue(maxsize=queue_maxsize)
        self.running      = False
        self.shared_state = shared_state
        self.detector     = Detector()
        self.batch_size   = batch_size
        self._thread      = None          # kept so we can join on shutdown

        # -- Stats ------------------------------------------------
        self.total_frames  = 0
        self.total_dropped = 0
        self.last_fps_time = time.time()
        self.fps           = 0.0

    def submit(self, message, callback):
        try:
            self.input_queue.put_nowait((message, callback))
        except Full:
            self.total_dropped += 1

    def submit_if_free(self, message, callback):
        try:
            self.input_queue.put_nowait((message, callback))
            return True
        except Full:
            self.total_dropped += 1
            return False

    def run(self):
        log.info("thread alive")

        while self.running:
            batch     = []
            callbacks = []

            try:
                message, callback = self.input_queue.get(timeout=0.1)
                batch.append(message)
                callbacks.append(callback)
            except Empty:
                continue

            while len(batch) < self.batch_size:
                try:
                    message, callback = self.input_queue.get_nowait()
                    batch.append(message)
                    callbacks.append(callback)
                except Empty:
                    break

            if not batch:
                continue

            t0 = time.time()
            frames  = [m.frame for m in batch]
            results = [self.detector.detect(frame) for frame in frames]
            inference_ms = (time.time() - t0) * 1000

            self.total_frames += len(batch)
            now = time.time()
            if now - self.last_fps_time >= 2.0:
                elapsed = now - self.last_fps_time
                self.fps = self.total_frames / elapsed
                self.total_frames  = 0
                self.last_fps_time = now
                log.info(
                    f"{self.fps:.1f} FPS | batch={len(batch)} | "
                    f"latency={inference_ms:.0f}ms | "
                    f"queue={self.input_queue.qsize()} | "
                    f"dropped={self.total_dropped}"
                )

            for message, result, callback in zip(batch, results, callbacks):
                self.shared_state.active_tracks[message.camera_id] = result
                result_packet = DetectionPacket(
                    camera_id=message.camera_id,
                    frame=message.frame,
                    detections=result,
                    timestamp=time.time()
                )
                log.debug(f"sending {len(result)} detections to {message.camera_id}")
                safe_put(callback, (message.camera_id, result_packet))

        log.info("run loop exited")

    def start(self):
        self.running = True
        self._thread = Thread(target=self.run, daemon=True, name="inference-worker")
        self._thread.start()
        log.info("started")

    def stop(self, timeout: float = 5.0):
        """
        Signal the run loop to exit and wait for the thread to finish.
        timeout: seconds to wait before giving up.
        """
        self.running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                log.warning(f"inference thread did not exit within {timeout}s")
            else:
                log.info("inference thread stopped cleanly")
        log.info(f"total dropped: {self.total_dropped}")

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()