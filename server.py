from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import cv2
from app_context import shared_state

from app_context import shared_state   # IMPORTANT (we'll define this)

app = FastAPI()

# ----------------------------
# CAMERA STREAM HANDLER
# ----------------------------

caps = {}

def get_cap(cam_id):
    if cam_id not in caps:
        caps[cam_id] = cv2.VideoCapture(int(cam_id.replace("gate_", "")))
    return caps[cam_id]


@app.get("/video_feed/{cam_id}")
def video_feed(cam_id: str):

    cap = get_cap(cam_id)

    def gen():
        while True:
            ret, frame = cap.read()
            if not ret:
                continue

            _, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


# ----------------------------
# API ENDPOINTS FOR DASHBOARD
# ----------------------------

@app.get("/api/camera_states")
def camera_states():
    return shared_state.camera_stats


@app.get("/api/activity_feed")
def activity_feed():
    return shared_state.alerts[-50:]