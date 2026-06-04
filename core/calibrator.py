import cv2
import numpy as np


class RoadCalibrator:
    """
    Converts image points into real-world coordinates (meters)
    using a homography transformation.
    """

    def __init__(self, image_points, world_points):

        self.image_points = np.array(
            image_points,
            dtype=np.float32
        )

        self.world_points = np.array(
            world_points,
            dtype=np.float32
        )

        self.H, _ = cv2.findHomography(
            self.image_points,
            self.world_points
        )

    def image_to_world(self, point):
        """
        point = (x, y)

        Returns:
            (X, Y) in meters
        """

        pt = np.array(
            [[[point[0], point[1]]]],
            dtype=np.float32
        )

        world = cv2.perspectiveTransform(
            pt,
            self.H
        )

        X = float(world[0][0][0])
        Y = float(world[0][0][1])

        return (X, Y)