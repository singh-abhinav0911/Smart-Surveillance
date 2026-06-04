import json


class EventRepository:

    def __init__(self, db):
        self.db = db

    def insert_event(self, event):

        conn = self.db.get_conn()

        try:

            cur = conn.cursor()

            cur.execute(
                """
                INSERT INTO events(
                    event_type,
                    camera_id,
                    track_id,
                    global_id,
                    metadata
                )
                VALUES (%s,%s,%s,%s,%s)
                """,
                (
                    event["event_type"],
                    event["camera_id"],
                    event["track_id"],
                    event["global_id"],
                    json.dumps(event["metadata"])
                )
            )

            conn.commit()

        finally:
            self.db.release(conn)