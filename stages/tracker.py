# stages/tracker.py

import queue
from core.tracker import TrackerManager
from utils.queue_utils import safe_put


class TrackerStage:

    def __init__(self, input_queue, output_queue, reid_worker, reid_manager):
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.reid_worker = reid_worker
        self.reid_manager = reid_manager
        self.tracker = TrackerManager()
        self.running = True

    def run(self):
        print("[TRACKER] started")

        while self.running:

            # ── Get packet with timeout — don't block forever ─────────
            try:
                camera_id, packet = self.input_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[TRACKER] unpack error: {e} — got: {type(self.input_queue.queue[0] if not self.input_queue.empty() else 'empty')}")
                continue

            print(f"[TRACKER] detections={len(packet.detections)}")

            # ── Update tracker ────────────────────────────────────────
            try:
                tracks = self.tracker.update(
                    packet.detections,
                    packet.frame
                )
            except Exception as e:
                print(f"[TRACKER] tracker.update error: {e}")
                continue

            # ── Assign global IDs ─────────────────────────────────────
            for track in tracks:
                cached = self.reid_worker.track_cache.get(track.track_id) \
                         if hasattr(self.reid_worker, 'track_cache') else None

                if cached:
                    track.global_id = cached["global_id"]
                else:
                    track.global_id = track.track_id

                # Submit to reid — stub ignores this
                try:
                    self.reid_worker.submit(
                        track.track_id,
                        packet.frame,
                        track.bbox,
                        packet.camera_id
                    )
                except Exception:
                    pass

            packet.tracks = tracks

            safe_put(self.output_queue, packet)

    def stop(self):
        self.running = False