import cv2
import time

class WebcamCamera:

    def __init__(self, source, camera_id, line_y=360):
        self.source = source
        self.camera_id = camera_id
        self.line_y = line_y

        self.cap = cv2.VideoCapture(source)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def read(self):
        return self.cap.read()

    def release(self):
        self.cap.release()