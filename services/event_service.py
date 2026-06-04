import time
import json

class EventService:

    def __init__(self, redis_client, repository):
        self.redis = redis_client
        self.repository = repository

    def emit_event(self, event):

        # save postgres
        self.repository.insert_event(event)

        # websocket realtime
        self.redis.publish(
            "events",
            json.dumps(event)
        )

        # activity feed
        self.redis.lpush(
            "activity_feed",
            json.dumps(event)
        )