# utils/queue_utils.py

from queue import Full, Empty


def safe_put(queue, item):
    """Put item in queue. If full, drop oldest and insert newest."""
    try:
        queue.put_nowait(item)
    except Full:
        try:
            queue.get_nowait()  # drop oldest
        except Empty:
            pass
        try:
            queue.put_nowait(item)  # put newest
        except Full:
            pass  # give up gracefully