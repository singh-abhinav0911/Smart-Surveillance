# app/routes/health.py — new file

from fastapi import APIRouter
from app.main import pipeline_service

router = APIRouter()


@router.get("/health")
def health():
    """Overall system health."""
    pipelines = pipeline_service.pipelines

    return {
        "status":    "ok" if pipelines else "no_cameras",
        "cameras":   len(pipelines),
        "pipelines": {
            cam_id: pipeline.get_stats()
            for cam_id, pipeline in pipelines.items()
        }
    }


@router.get("/health/{camera_id}")
def camera_health(camera_id: str):
    """Health for a specific camera."""
    pipeline = pipeline_service.pipelines.get(camera_id)
    if not pipeline:
        return {"error": f"Camera {camera_id} not found"}
    return pipeline.get_stats()