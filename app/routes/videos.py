from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import cv2

router = APIRouter()

caps = {}

def get_cap(cam_id):
    if cam_id not in caps:
        caps[cam_id] = cv2.VideoCapture(int(cam_id.replace("gate_", "")))
    return caps[cam_id]

@router.get("/video_feed/{cam_id}")
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