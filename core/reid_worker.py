import threading
import queue
import cv2
import numpy as np
import time
from torch import embedding

from core.reid_manager import ReIDManager
from core.reid_model import ReIDModel




class ReIDWorker:

    def __init__(self, reid_manager, model):

        self.queue = queue.Queue(maxsize=500)

        self.reid_manager = reid_manager
        self.model = model

        self.running = True
        self.thread = None

        self.track_cache = {}
        self.cache_ttl = 1.0

        self.batch_size = 16


    def get_global_id(self, embedding):
        return self.reid_manager.match(embedding)    

    def submit(self, track_id, frame, bbox, cam_id):

        if not self.queue.full():
            self.queue.put((track_id, frame, bbox, cam_id))


    def get_cached_id(self, track_id, embedding):


        now = time.time()

        if track_id in self.track_cache:

            cached = self.track_cache[track_id]

            # still valid
            if now - cached["time"] < self.cache_ttl:
                return cached["global_id"]

        # recompute identity
        global_id = self.get_global_id(embedding)

        self.track_cache[track_id] = {
            "global_id": global_id,
            "time": now
        }

        return global_id        

    def start(self):

        self.running = True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop(self):

        self.running = False

    def preprocess(self, crop):

        crop = cv2.resize(crop, (128, 256))
        crop = crop.astype(np.float32) / 255.0
        crop = np.transpose(crop, (2, 0, 1))
        return crop
    


    def run(self):

        while self.running:

            batch = []

            # -------------------------
            # 1. COLLECT BATCH
            # -------------------------
            while len(batch) < self.batch_size:

                try:
                    item = self.queue.get(timeout=0.05)
                    batch.append(item)
                except queue.Empty:
                    break

            if not batch:
                continue

            track_ids = []
            cams = []
            crops = []

            # -------------------------
            # 2. EXTRACT CROPS
            # -------------------------
            for track_id, frame, bbox, cam_id in batch:

                x1, y1, x2, y2 = map(int, bbox)
                h, w = frame.shape[:2]

                x1 = max(0, min(x1, w - 1))
                x2 = max(0, min(x2, w - 1))
                y1 = max(0, min(y1, h - 1))
                y2 = max(0, min(y2, h - 1))

                if x2 <= x1 or y2 <= y1:
                    continue

                crop = frame[y1:y2, x1:x2]
                if crop.size == 0:
                    continue

                crops.append(self.preprocess(crop))
                track_ids.append(track_id)
                cams.append(cam_id)

            if not crops:
                continue

            # -------------------------
            # 3. BATCH INFERENCE (🔥 KEY PART)
            # -------------------------
            crops = np.array(crops, dtype=np.float32)

            embeddings = self.model(crops)  # vectorized forward pass

            # -------------------------
            # 4. UPDATE REID MEMORY
            # -------------------------
            for i in range(len(embeddings)):

                gid = self.reid_manager.update_track(
                    track_id=track_ids[i],
                    embedding=embeddings[i],
                    cam_id=cams[i]
                )

                self.track_cache[track_ids[i]] = {
                    "global_id": gid,
                    "time": time.time()
                }
                
    def stop(self):
        self.running = False            