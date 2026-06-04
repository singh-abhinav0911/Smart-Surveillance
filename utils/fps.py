"""Simple FPS counter utility."""

import time


class FPS:
    def __init__(self):
        self._start = None
        self._frames = 0

    def start(self):
        self._start = time.time()
        self._frames = 0
        return self

    def update(self):
        self._frames += 1

    def fps(self):
        if not self._start:
            return 0.0
        return self._frames / (time.time() - self._start)
