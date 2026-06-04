import time
import numpy as np
from collections import defaultdict, deque


class SpeedEstimator:

    def __init__(
        self,
        calibrator,
        fps=30,
        history_size=15,
        speed_limit=60
    ):

        self.calibrator = calibrator

        self.fps = fps
        self.history_size = history_size

        self.speed_limit = speed_limit

        self.track_history = defaultdict(
            lambda: deque(maxlen=history_size)
        )

        self.speed_cache = {}

    def update(self, track_id, bbox):

        """
        bbox:
        [x1,y1,x2,y2]

        Returns:
            speed_kmph
            violation
        """

        x1, y1, x2, y2 = bbox

        cx = int((x1 + x2) / 2)
        cy = int(y2)

        world_x, world_y = \
            self.calibrator.image_to_world(
                (cx, cy)
            )

        now = time.time()

        self.track_history[track_id].append(
            (
                world_x,
                world_y,
                now
            )
        )

        speed = self.compute_speed(track_id)

        violation = False

        if speed is not None:
            violation = speed > self.speed_limit

        return speed, violation

    def compute_speed(self, track_id):

        history = self.track_history[track_id]

        if len(history) < 2:
            return None

        x1, y1, t1 = history[0]
        x2, y2, t2 = history[-1]

        distance = np.sqrt(
            (x2 - x1) ** 2 +
            (y2 - y1) ** 2
        )

        dt = t2 - t1

        if dt <= 0:
            return None

        speed_mps = distance / dt

        speed_kmph = speed_mps * 3.6

        self.speed_cache[track_id] = speed_kmph

        return round(speed_kmph, 2)

    def get_speed(self, track_id):
        return self.speed_cache.get(track_id)