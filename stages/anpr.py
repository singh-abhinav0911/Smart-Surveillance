import cv2
from sympy import re
import easyocr # pyright: ignore[reportMissingImports]
from ultralytics import YOLO
from utils.logger import get_logger

log = get_logger("anpr")

class ANPRStage:

    def __init__(self):
        log.info("anpr init started")
        self.plate_model = YOLO("models/best.pt")
        log.info("yolo loaded")
        self.reader = easyocr.Reader(
            ["en"],
            gpu=False
        )
        log.info("easyocr loaded")

        self.track_to_plate = {}


    def detect_plate(self, vehicle_crop):

        results = self.plate_model(
            vehicle_crop,
            verbose=False
        )

        best_plate = None
        best_conf = 0

        for r in results:

            for box in r.boxes:

                conf = float(box.conf[0])

                if conf > best_conf:

                    best_conf = conf

                    x1, y1, x2, y2 = map(
                        int,
                        box.xyxy[0]
                    )

                    best_plate = vehicle_crop[
                        y1:y2,
                        x1:x2
                    ]

        return best_plate   

    def read_plate(self, plate_crop):
        log.debug("read plate called")

        try:

            results = self.reader.readtext(
                plate_crop
            )
            log.debug(f"OCR results: {results}")

            if not results:
                return None

            best_text = max(
                results,
                key=lambda x: x[2]
            )

            plate = best_text[1]

            plate = (
                plate
                .replace(".", "")
                .replace(" ", "")
                .replace("-", "")
                .upper()
            )
            

            plate = re.sub(r"[^A-Z0-9]", "", plate.upper())



            return plate

        except Exception as e:

            log.error(f"OCR error: {e}")

            return None
        
    def process_vehicle(self, frame, track):

        track_id = track.track_id

        if track_id in self.track_to_plate:

            return self.track_to_plate[track_id]

        x1, y1, x2, y2 = map(
            int,
            track.bbox
        )

        vehicle_crop = frame[y1:y2, x1:x2]

        if vehicle_crop.size == 0:
            return None

        plate_crop = self.detect_plate(
            vehicle_crop
        )


        if plate_crop is None:
            return None

        plate = self.read_plate(
            plate_crop
        )
        log.debug("Vehicle crop OK")

        if plate:

            self.track_to_plate[track_id] = plate

            log.info(f"Track {track_id} -> {plate}")

        return plate