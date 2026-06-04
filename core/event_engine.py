class EventEngine:

    def __init__(self, saver_queue=None):
        self.saver_queue = saver_queue

    def emit(self, event):

        print("[EVENT]", event)

        if self.saver_queue is not None:
            self.saver_queue.put(event)