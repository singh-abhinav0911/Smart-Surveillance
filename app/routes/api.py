# app/routes/api.py

from fastapi import APIRouter, Query, HTTPException
from database.database_manager import DatabaseManager

router = APIRouter(prefix="/api")
db = DatabaseManager()


@router.get("/stats")
def get_stats():
    try:
        return db.get_global_stats()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Stats unavailable: {e}")


@router.get("/health")
def get_health():
    try:
        from app_context import pipeline_service, inference_worker
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Context unavailable: {e}")

    pipelines_status = {}
    for camera_id, pipeline in pipeline_service.pipelines.items():
        stats = pipeline.get_stats()
        dead_threads = [
            name for name, alive in zip(stats["threads_names"], stats["threads_alive"])
            if not alive
        ]
        pipelines_status[camera_id] = {
            "tracking_queue":  stats["tracking_queue"],
            "analytics_queue": stats["analytics_queue"],
            "visual_queue":    stats["visual_queue"],
            "db_queue":        stats["db_queue"],
            "threads_alive":   all(stats["threads_alive"]),
            "dead_threads":    dead_threads,
        }

    overall = all(p["threads_alive"] for p in pipelines_status.values())

    return {
        "inference": {
            "fps":     round(inference_worker.fps, 1),
            "queue":   inference_worker.input_queue.qsize(),
            "dropped": inference_worker.total_dropped,
            "alive":   inference_worker.is_alive,
        },
        "pipelines":       pipelines_status,
        "overall_healthy": overall,
    }


@router.get("/live")
def liveness():
    """Kubernetes liveness probe — process is running."""
    return {"status": "ok"}


@router.get("/ready")
def readiness():
    """Readiness probe — checks DB, Redis, inference, pipelines."""
    checks = {}
    failed = []

    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = f"error: {e}"
        failed.append("db")

    try:
        import redis as _redis
        r = _redis.Redis(host="localhost", port=6379, socket_connect_timeout=2)
        r.ping()
        r.close()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
        failed.append("redis")

    try:
        from app_context import inference_worker
        if inference_worker.is_alive:
            checks["inference"] = "ok"
        else:
            checks["inference"] = "not running"
            failed.append("inference")
    except Exception as e:
        checks["inference"] = f"error: {e}"
        failed.append("inference")

    try:
        from app_context import pipeline_service
        n = len(pipeline_service.pipelines)
        checks["pipelines"] = f"{n} active"
        if n == 0:
            failed.append("pipelines")
    except Exception as e:
        checks["pipelines"] = f"error: {e}"
        failed.append("pipelines")

    if failed:
        raise HTTPException(
            status_code=503,
            detail={"status": "not ready", "failed": failed, "checks": checks}
        )
    return {"status": "ready", "checks": checks}


@router.get("/violations")
def get_violations(
    limit:          int = Query(default=30, ge=1, le=200),
    offset:         int = Query(default=0,  ge=0),
    camera_id:      str = Query(default=None),
    violation_type: str = Query(default=None),
):
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                where  = ["1=1"]
                params = []
                if camera_id:
                    where.append("camera_id = %s")
                    params.append(camera_id)
                if violation_type:
                    where.append("violation_type = %s")
                    params.append(violation_type)
                params += [limit, offset]
                cur.execute(f"""
                    SELECT id, timestamp, camera_id, track_id, global_id,
                           violation_type, object_type, bbox,
                           speed_kmh, zone_id, metadata, image_path
                    FROM violations
                    WHERE {" AND ".join(where)}
                    ORDER BY timestamp DESC
                    LIMIT %s OFFSET %s
                """, params)
                rows = cur.fetchall()
        result = []
        for r in rows:
            row = dict(r)
            if row.get("timestamp"):
                row["timestamp"] = row["timestamp"].isoformat()
            result.append(row)
        return result
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB error: {e}")


@router.get("/violations/count")
def get_violations_count():
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT violation_type, COUNT(*)::int AS count
                    FROM violations GROUP BY violation_type
                """)
                rows = cur.fetchall()
        return {r["violation_type"]: r["count"] for r in rows}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB error: {e}")