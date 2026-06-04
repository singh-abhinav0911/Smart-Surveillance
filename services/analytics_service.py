class AnalyticsService:

    def __init__(self, redis_client):
        self.redis = redis_client

    def update_counts(self, camera_id, objects):

        stats = {
            "camera_id": camera_id,
            "person": objects.get("person", 0),
            "vehicle": objects.get("car", 0),
            "truck": objects.get("truck", 0),
            "bike": objects.get("motorcycle", 0)
        }

        self.redis.publish("stats", stats)
        self.redis.push(f"stats:{camera_id}", stats)