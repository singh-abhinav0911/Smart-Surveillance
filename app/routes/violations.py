# app/routes/violations.py — new file

import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from database.database_manager import DatabaseManager

router = APIRouter()
db = DatabaseManager()


@router.get("/violations")
def get_violations(
    camera_id: str = None,
    violation_type: str = None,
    limit: int = 50
):
    """Get recent violations with optional filters."""
    try:
        violations = db.get_violations(
            camera_id=camera_id,
            violation_type=violation_type,
            limit=limit
        )
        return {"violations": violations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/violations/image/{filename:path}")
def get_violation_image(filename: str):
    """Serve violation snapshot image."""
    # Security: only serve from data/events/violations/
    safe_path = os.path.join("data/events/violations", os.path.basename(filename))

    if not os.path.exists(safe_path):
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(safe_path, media_type="image/jpeg")


@router.get("/violations/stats")
def get_violation_stats():
    """Get violation counts by type."""
    try:
        stats = db.get_violation_stats()
        return {"stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))