from utils.logger import get_logger

log = get_logger("event_engine")


class EventEngine:

    def __init__(self, saver_queue=None):
        self.saver_queue = saver_queue

    def emit(self, event):

        log.debug(f"Event: {event}")

        if self.saver_queue is not None:
            self.saver_queue.put(event)