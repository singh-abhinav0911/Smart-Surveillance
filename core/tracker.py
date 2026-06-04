# core/tracker.py
#
# CHANGES FROM ORIGINAL:
#   - Tracks no longer die when a detection is missing for one frame.
#     Each track has an `age` counter — it survives up to `max_age`
#     frames without a match, then is removed. This eliminates flicker
#     caused by inference_every_n skipping frames.
#
#   - "Coasted" tracks (no detection this frame) keep their last known
#     bbox and are still returned — the visualizer keeps drawing them
#     at the last known position instead of making them vanish.
#
#   - Greedy matching now skips already-used track IDs so one track
#     can't be assigned to two detections in the same frame.
#
#   - max_age=8 is good for inference_every_n=2 at 30fps.
#     Increase to 15-20 if you raise inference_every_n.

from core.messages import Track


class SimpleByteTrack:

    def __init__(self, max_age=8, min_iou=0.3):
        self.tracks   = {}   # track_id -> {bbox, class_id, confidence, age}
        self.next_id  = 0
        self.max_age  = max_age
        self.min_iou  = min_iou

    def iou(self, box1, box2):
        x1,  y1,  x2,  y2  = box1
        x1b, y1b, x2b, y2b = box2

        xi1 = max(x1, x1b);  yi1 = max(y1, y1b)
        xi2 = min(x2, x2b);  yi2 = min(y2, y2b)

        inter = max(0, xi2 - xi1) * max(0, yi2 - yi1)
        area1 = (x2 - x1) * (y2 - y1)
        area2 = (x2b - x1b) * (y2b - y1b)
        union = area1 + area2 - inter

        return inter / union if union > 0 else 0


class TrackerManager:

    def __init__(self, max_age=8, min_iou=0.3):
        self.tracker = SimpleByteTrack(max_age=max_age, min_iou=min_iou)

    def update(self, detections, frame=None):

        existing = self.tracker.tracks          # {id -> track_dict}
        matched_track_ids  = set()              # track IDs claimed this frame
        matched_det_indices = set()             # detection indices claimed

        # ── Step 1: match detections to existing tracks ───────────────
        # Build match pairs: (iou, track_id, det_index)
        matches = []
        for det_i, det in enumerate(detections):
            for track_id, track in existing.items():
                score = self.tracker.iou(det.bbox, track["bbox"])
                if score >= self.tracker.min_iou:
                    matches.append((score, track_id, det_i))

        # Sort best IoU first — greedy assignment
        matches.sort(key=lambda x: x[0], reverse=True)

        assignment = {}   # track_id -> det_index
        for score, track_id, det_i in matches:
            if track_id in matched_track_ids:
                continue   # track already claimed
            if det_i in matched_det_indices:
                continue   # detection already claimed
            assignment[track_id] = det_i
            matched_track_ids.add(track_id)
            matched_det_indices.add(det_i)

        # ── Step 2: update matched tracks (reset age, update bbox) ────
        updated = {}
        for track_id, det_i in assignment.items():
            det = detections[det_i]
            updated[track_id] = {
                "bbox":       list(det.bbox),
                "class_id":   det.class_id,
                "confidence": det.confidence,
                "age":        0,               # seen this frame — reset age
            }

        # ── Step 3: coast unmatched tracks (increment age) ────────────
        # Tracks survive up to max_age frames without a detection.
        # They keep their last known bbox so the visualizer doesn't flicker.
        for track_id, track in existing.items():
            if track_id in matched_track_ids:
                continue   # already updated above
            new_age = track.get("age", 0) + 1
            if new_age <= self.tracker.max_age:
                updated[track_id] = {
                    "bbox":       track["bbox"],   # last known position
                    "class_id":   track["class_id"],
                    "confidence": track.get("confidence", 0.0),
                    "age":        new_age,
                }
            # else: track is too old — drop it (not added to updated)

        # ── Step 4: create new tracks for unmatched detections ─────────
        for det_i, det in enumerate(detections):
            if det_i in matched_det_indices:
                continue   # already matched to an existing track
            new_id = self.tracker.next_id
            self.tracker.next_id += 1
            updated[new_id] = {
                "bbox":       list(det.bbox),
                "class_id":   det.class_id,
                "confidence": det.confidence,
                "age":        0,
            }

        # ── Step 5: commit ────────────────────────────────────────────
        self.tracker.tracks = updated

        # ── Step 6: return as Track objects ───────────────────────────
        return [
            Track(
                track_id=track_id,
                bbox=data["bbox"],
                class_id=data["class_id"],
            )
            for track_id, data in updated.items()
        ]