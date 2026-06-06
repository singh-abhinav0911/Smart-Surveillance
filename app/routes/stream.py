# app/routes/stream.py

import cv2
import queue
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app_context import pipeline_service
from utils.logger import get_logger

router = APIRouter()
log = get_logger("stream")


def generate_frames(camera_id: str):
    """Generator that yields MJPEG frames from pipeline stream_queue."""

    pipeline = pipeline_service.pipelines.get(camera_id)
    if not pipeline:
        return

    while True:
        try:
            message = pipeline.stream_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        except Exception:
            break

        try:
            frame     = message.frame.copy()
            tracks    = getattr(message, "tracks", [])
            analytics = getattr(message, "analytics", {})
            h, w      = frame.shape[:2]

            # -- Draw tracks ----------------------------------
            for track in tracks:
                x1, y1, x2, y2 = map(int, track.bbox)
                track_id = getattr(track, "global_id",
                                   getattr(track, "track_id", "?"))
                speed = getattr(track, "speed", None)
                color = (0, 0, 255) if (speed and speed > 60) else (0, 255, 0)

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                label = f"ID:{track_id}"
                if speed is not None:
                    label += f" {speed:.1f}km/h"
                cv2.putText(frame, label, (x1, max(y1 - 10, 12)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            # -- Draw overlays --------------------------------
            cv2.line(frame, (0, 300), (w, 300), (0, 255, 255), 2)
            cv2.putText(frame, f"IN:  {analytics.get('in_count', 0)}",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(frame, f"OUT: {analytics.get('out_count', 0)}",
                        (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            cv2.putText(frame, f"CAM: {camera_id}",
                        (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

            # -- Encode MJPEG ---------------------------------
            ret, buffer = cv2.imencode(
                '.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70]
            )
            if not ret:
                continue

            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' +
                buffer.tobytes() +
                b'\r\n'
            )

        except Exception as e:
            log.error(f"frame error: {e}")
            continue


@router.get("/stream/{camera_id}")
def video_stream(camera_id: str):
    """MJPEG stream endpoint for a camera."""
    return StreamingResponse(
        generate_frames(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/cameras")
def list_cameras():
    """List all active cameras."""
    return {"cameras": list(pipeline_service.pipelines.keys())}