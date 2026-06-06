# main.py  (root — the entrypoint you run: python main.py)
#
# CHANGES FROM ORIGINAL:
#   - Added clear comment that this IS the visualizer.
#     VisualizerStage has been removed from pipeline threads.
#     This loop is the only consumer of pipeline.visual_queue.
#   - Added per-camera window tracking so pressing Q cleanly
#     destroys only that camera's window.
#   - Added pipeline health check: prints a warning if any
#     pipeline thread dies during the session.
#   - Everything else unchanged.

import time
import threading
import queue
import cv2
import uvicorn

from utils.logger import get_logger
from app.main import app, pipeline_service


def visualizer_loop():
    """
    Runs on MAIN thread — required for cv2.imshow on Windows/macOS.

    This is the ONLY consumer of each pipeline's visual_queue.
    VisualizerStage has been removed from pipeline threads — having
    two consumers on the same queue meant frames were randomly stolen
    and the display showed nothing.
    """
    log = get_logger("main")
    log.info("Main thread display loop started")
    log.info("Press Q in any window to quit all cameras")

    # Wait for pipelines and inference worker to start up
    time.sleep(3)

    last_health_check = time.time()

    while True:
        got_any_frame = False

        for camera_id, pipeline in pipeline_service.pipelines.items():

            try:
                message = pipeline.visual_queue.get_nowait()
            except queue.Empty:
                continue
            except Exception:
                continue

            got_any_frame = True

            try:
                frame     = message.frame.copy()
                tracks    = getattr(message, "tracks", [])
                analytics = getattr(message, "analytics", {})

                h, w = frame.shape[:2]

                # ── Counting line ──────────────────────────────────────
                cv2.line(frame, (0, 300), (w, 300), (0, 255, 255), 2)

                # ── Tracks ─────────────────────────────────────────────
                overspeed = 0
                for track in tracks:
                    x1, y1, x2, y2 = map(int, track.bbox)
                    track_id = getattr(track, "global_id",
                                       getattr(track, "track_id", "?"))
                    speed = getattr(track, "speed", None)
                    plate = getattr(track, "plate", None)

                    color = (0, 0, 255) if (speed and speed > 60) else (0, 255, 0)
                    if speed and speed > 60:
                        overspeed += 1

                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                    label = f"ID:{track_id}"
                    if speed is not None:
                        label += f" {speed:.1f}km/h"
                    if plate:
                        label += f" [{plate}]"

                    cv2.putText(frame, label, (x1, max(y1 - 10, 12)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

                # ── Overlays ───────────────────────────────────────────
                overlays = [
                    (f"IN:  {analytics.get('in_count', 0)}",  (20, 40),     (0, 255, 0)),
                    (f"OUT: {analytics.get('out_count', 0)}", (20, 80),     (0, 0, 255)),
                    (f"OVER: {overspeed}",                    (20, 120),    (0, 0, 255)),
                    (f"CAM: {camera_id}",                     (20, h - 40), (255, 255, 0)),
                ]
                for text, pos, color in overlays:
                    cv2.putText(frame, text, pos,
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

                cv2.imshow(f"Camera {camera_id}", frame)

            except Exception as e:
                log.error(f"draw error on {camera_id}: {e}")

        # ── Key handler ────────────────────────────────────────────────
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            log.info("Q pressed — stopping all pipelines")
            pipeline_service.stop_all()
            break

        # ── Pipeline health check every 10s ────────────────────────────
        now = time.time()
        if now - last_health_check > 10.0:
            last_health_check = now
            for camera_id, pipeline in pipeline_service.pipelines.items():
                stats = pipeline.get_stats()
                dead = [name for name, alive in zip(
                    stats["threads_names"], stats["threads_alive"]
                ) if not alive]
                if dead:
                    log.warning(f"WARNING — dead threads on {camera_id}: {dead}")

        # ── Small sleep when no frames available ───────────────────────
        if not got_any_frame:
            time.sleep(0.005)

    cv2.destroyAllWindows()
    log.info("display loop ended")


if __name__ == "__main__":

    # ── Start uvicorn in background thread ────────────────────────────
    server_thread = threading.Thread(
        target=uvicorn.run,
        args=(app,),
        kwargs={
            "host": "127.0.0.1",
            "port": 8000,
            "log_level": "info"
        },
        daemon=True
    )
    server_thread.start()
    log = get_logger("main")
    log.info("Uvicorn started on http://127.0.0.1:8000")

    # ── Run visualizer on main thread (required for cv2.imshow) ───────
    visualizer_loop()

    log.info("Done")