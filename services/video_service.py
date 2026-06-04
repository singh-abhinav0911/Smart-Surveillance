import cv2

class VideoService:

    def __init__(self):
        self.caps = {}

    def get_stream(self, cam_id):
        if cam_id not in self.caps:
            self.caps[cam_id] = cv2.VideoCapture(int(cam_id))

        return self.caps[cam_id]