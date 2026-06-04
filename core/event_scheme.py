def create_event(
    event_type,
    track_id,
    global_id,
    camera_id,
    bbox,
    metadata=None
):

    return {
        "event_type": event_type,
        "track_id": track_id,
        "global_id": global_id,
        "camera_id": camera_id,
        "timestamp": __import__("time").time(),
        "bbox": bbox,
        "metadata": metadata or {}
    }