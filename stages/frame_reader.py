import cv2
import time
from core.messages import FramePacket


class FrameReader:

    def __init__(self, camera_id, camera, output_queue, inference_worker,
                 inference_every_n=3, target_fps=30):

        self.camera_id        = camera_id
        self.output_queue     = output_queue
        self.inference_worker = inference_worker
        self.inference_every_n = inference_every_n
        self.target_fps       = target_fps
        self.frame_interval   = 1.0 / target_fps
        self.running          = False
        self.frame_count      = 0
        self.dropped_frames   = 0

        # ── Open camera — handle int, string, or VideoCapture ─────────
        if isinstance(camera, cv2.VideoCapture):
            self.camera = camera
        else:
            self.camera = cv2.VideoCapture(camera)
            self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not self.camera.isOpened():
            raise RuntimeError(
                f"[FrameReader] Cannot open camera '{camera_id}' — source: {camera}"
            )

        # ── For video files get actual FPS ────────────────────────────
        if isinstance(camera, str):
            actual_fps = self.camera.get(cv2.CAP_PROP_FPS)
            if actual_fps > 0:
                self.frame_interval = 1.0 / actual_fps
                print(f"[FrameReader] {camera_id} — video file, FPS: {actual_fps:.1f}")
        else:
            print(f"[FrameReader] {camera_id} — webcam ready")

    def run(self):
        print(f"[FrameReader] {self.camera_id} started")
        self.running = True
        last_time = time.time()

        while self.running:

            # ── FPS throttle ──────────────────────────────────────────
            now = time.time()
            elapsed = now - last_time
            if elapsed < self.frame_interval:
                time.sleep(self.frame_interval - elapsed)
            last_time = time.time()

            # ── Read frame ────────────────────────────────────────────
            success, frame = self.camera.read()

            if not success:
                # ── Loop video when it ends ───────────────────────────
                self.camera.set(cv2.CAP_PROP_POS_FRAMES, 0)
                success, frame = self.camera.read()
                if not success:
                    print(f"[FrameReader] {self.camera_id} cannot read — stopping")
                    break
                print(f"[FrameReader] {self.camera_id} looping video")

            self.frame_count += 1

            # ── Skip frames for inference ─────────────────────────────
            if self.frame_count % self.inference_every_n != 0:
                continue

            # ── Build packet ──────────────────────────────────────────
            packet = FramePacket(
                camera_id=self.camera_id,
                frame=frame.copy(),
                timestamp=time.time()
            )

            # ── Submit to inference — drop if busy ────────────────────
            submitted = self.inference_worker.submit_if_free(
                packet,
                callback=self.output_queue
            )

            if not submitted:
                self.dropped_frames += 1
                if self.dropped_frames % 30 == 0:
                    print(f"[FrameReader] {self.camera_id} "
                          f"dropped {self.dropped_frames} frames — inference busy")

    def stop(self):
        self.running = False
        self.camera.release()
        print(f"[FrameReader] {self.camera_id} stopped — "
              f"frames: {self.frame_count}, dropped: {self.dropped_frames}")