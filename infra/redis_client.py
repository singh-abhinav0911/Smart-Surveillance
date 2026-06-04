import redis
import json


class RedisClient:

    def __init__(self,
                 host="localhost",
                 port=6379,
                 db=0,
                 decode_responses=True):

        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=decode_responses,
            socket_keepalive=True,
            socket_timeout=5,
            retry_on_timeout=True
        )

    # -------------------------
    # PUB/SUB (REALTIME EVENTS)
    # -------------------------
    def publish(self, channel, data):
        if isinstance(data, dict):
            data = json.dumps(data)
        self.client.publish(channel, data)

    def subscribe(self, channel):
        pubsub = self.client.pubsub()
        pubsub.subscribe(channel)
        return pubsub

    # -------------------------
    # LIST STORAGE (FEED)
    # -------------------------
    def push_list(self, key, data, limit=100):
        if isinstance(data, dict):
            data = json.dumps(data)

        self.client.lpush(key, data)
        self.client.ltrim(key, 0, limit)

    def get_list(self, key, count=50):
        return self.client.lrange(key, 0, count - 1)

    # -------------------------
    # CACHE (optional future use)
    # -------------------------
    def set(self, key, value, ex=None):
        if isinstance(value, dict):
            value = json.dumps(value)
        self.client.set(key, value, ex=ex)

    def get(self, key):
        return self.client.get(key)