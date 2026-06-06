# core/detector.py
import cv2
import torch
from ultralytics import YOLO
from utils.logger import get_logger
from core.messages import Detection


log = get_logger("detector")


class Detector:

    def __init__(self, model_path="models/yolov8n.pt", conf=0.5, device=None):

        # ── Auto select device ────────────────────────────────
        if device is None:
            if torch.cuda.is_available():
                self.device = "cuda"
            elif torch.backends.mps.is_available():
                self.device = "mps"   # Apple Silicon
            else:
                self.device = "cpu"
        else:
            self.device = device

        log.info(f"Loading model on {self.device}")

        self.model = YOLO(model_path)
        self.model.to(self.device)
        self.conf = conf

        # ── Warmup — first inference is always slow ───────────────────
        import numpy as np
        dummy = np.zeros((640, 640, 3), dtype="uint8")
        self.model(dummy, verbose=False)
        log.info(f"Model ready on {self.device}")
        log.info(f"Classes: {self.model.names}")

    def detect(self, frame):

        orig_h, orig_w = frame.shape[:2]

         # Resize to smaller before inference — much faster on CPU
        small = cv2.resize(frame, (320, 320)) # half size = 4x faster
        
        
        scale_x = orig_w / 320
        scale_y = orig_h / 320 

        results = self.model(
            small,
            verbose=False,
            conf=self.conf,
            device=self.device,
            # ── These 3 lines speed up inference significantly ────────
            imgsz=320,       # fixed size — no resize overhead
                      # faster NMS
        )[0]

        detections = []

        for r in results.boxes.data.tolist():
            x1, y1, x2, y2, score, class_id = r
            x1 *= scale_x
            x2 *= scale_x
            y1 *= scale_y
            y2 *= scale_y
            detections.append(
                Detection(
                    bbox=[x1, y1, x2, y2],
                    confidence=float(score),
                    class_id=int(class_id)
                )
            )

        return detections