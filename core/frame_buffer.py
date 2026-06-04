# core/frame_buffer.py

import threading
import time


class FrameBuffer:
    """
    Stores ONLY the latest frame per camera.
    Prevents queue buildup and latency explosion.
    """

    def __init__(self):
        # cam_id -> frame
        self.frames = {}

        # cam_id -> timestamp of last update
        self.timestamps = {}

        self.lock = threading.Lock()

    def update(self, cam_id: int, frame):
        """
        Called by camera threads.
        Always overwrites old frame (no buffering).
        """
        with self.lock:
            self.frames[cam_id] = frame
            self.timestamps[cam_id] = time.time()

    def get(self, cam_id: int):
        """
        Called by inference worker.
        Always returns latest available frame.
        """
        with self.lock:
            return self.frames.get(cam_id, None)

    def get_timestamp(self, cam_id: int):
        """
        Optional: useful for debugging stale cameras.
        """
        with self.lock:
            return self.timestamps.get(cam_id, None)

    def get_all_cam_ids(self):
        """
        Useful for inference loop.
        """
        with self.lock:
            return list(self.frames.keys())

    def is_active(self, cam_id: int, timeout_sec: float = 5.0):
        """
        Checks if camera is still alive (optional health check).
        """
        with self.lock:
            ts = self.timestamps.get(cam_id, None)

        if ts is None:
            return False

        return (time.time() - ts) < timeout_sec