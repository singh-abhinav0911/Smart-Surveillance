import time
import math


class SpeedEstimator:

    def __init__(
        self,
        pixels_per_meter=10,
        speed_limit=60
    ):

        self.pixels_per_meter = pixels_per_meter
        self.speed_limit = speed_limit

        self.last_positions = {}
        self.last_times = {}

    def update(self, track_id, bbox):

        x1, y1, x2, y2 = bbox

        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

        now = time.time()

        if track_id not in self.last_positions:

            self.last_positions[track_id] = (cx, cy)
            self.last_times[track_id] = now

            return None, False

        prev_x, prev_y = self.last_positions[track_id]
        prev_time = self.last_times[track_id]

        distance_pixels = math.sqrt(
            (cx - prev_x) ** 2 +
            (cy - prev_y) ** 2
        )

        dt = now - prev_time

        if dt <= 0:
            return None, False

        distance_meters = (
            distance_pixels /
            self.pixels_per_meter
        )

        speed_mps = distance_meters / dt

        speed_kmh = speed_mps * 3.6

        self.last_positions[track_id] = (cx, cy)
        self.last_times[track_id] = now

        violation = speed_kmh > self.speed_limit

        return round(speed_kmh, 2), violation