from ultralytics import YOLO


class PlateDetector:

    def __init__(self):

        self.model = YOLO("models/best.pt")

    def detect(self, frame):

        results = self.model(
            frame,
            verbose=False,
            conf=0.5
        )[0]

        plates = []

        for box in results.boxes.data.tolist():

            x1, y1, x2, y2, score, cls = box

            plates.append({
                "bbox": [x1, y1, x2, y2],
                "confidence": float(score)
            })

        return plates