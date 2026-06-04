import cv2

class Camera:

    def __init__(self, source, camera_id, line_y=360):
        self.source = source
        self.camera_id = camera_id
        self.line_y = line_y

        self.cap = cv2.VideoCapture(source)

    def read(self):
        return self.cap.read()

    def release(self):
        self.cap.release()