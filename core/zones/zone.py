import cv2
import numpy as np


class Zone:

    def __init__(self, zone_id, polygon, zone_type="neutral"):

        self.zone_id = zone_id
        self.polygon = np.array(polygon, np.int32)
        self.zone_type = zone_type

    def contains(self, x, y):

        return cv2.pointPolygonTest(
            self.polygon,
            (x, y),
            False
        ) >= 0