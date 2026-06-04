# app/routes/api.py

from fastapi import APIRouter, Query
from database.database_manager import DatabaseManager

router = APIRouter(prefix="/api")

db = DatabaseManager()


@router.get("/stats")
def get_stats():
    """Global dashboard stats from DB."""
    try:
        return db.get_global_stats()
    except Exception as e:
        return {"error": str(e)}


@router.get("/violations")
def get_violations(
    limit:  int = Query(default=30, ge=1, le=200),
    offset: int = Query(default=0,  ge=0),
):
    """Recent violations with optional pagination."""
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, timestamp, camera_id, track_id, global_id,
                           violation_type, object_type, bbox,
                           speed_kmh, zone_id, metadata, image_path
                    FROM violations
                    ORDER BY timestamp DESC
                    LIMIT %s OFFSET %s
                """, (limit, offset))
                rows = cur.fetchall()
        # RealDictCursor returns dict-like rows — cast to plain dicts
        result = []
        for r in rows:
            row = dict(r)
            # timestamp → ISO string for JSON
            if row.get("timestamp"):
                row["timestamp"] = row["timestamp"].isoformat()
            result.append(row)
        return result
    except Exception as e:
        return {"error": str(e)}


@router.get("/violations/count")
def get_violations_count():
    """Total violation counts grouped by type."""
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT violation_type, COUNT(*)::int AS count
                    FROM violations
                    GROUP BY violation_type
                """)
                rows = cur.fetchall()
        return {r["violation_type"]: r["count"] for r in rows}
    except Exception as e:
        return {"error": str(e)}