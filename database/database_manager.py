import psycopg2
import json
from psycopg2 import pool as psycopg2_pool
from psycopg2.extras import RealDictCursor
from datetime import datetime
import threading
import os
import queue
import time
from utils.logger import get_logger

log = get_logger("database")

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


if load_dotenv:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    load_dotenv(os.path.join(os.path.dirname(BASE_DIR), ".env"))


class PooledConnection:
    def __init__(self, manager, conn, pooled=True):
        self._manager = manager
        self._conn = conn
        self._pooled = pooled
        self._released = False

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __enter__(self):
        return self._conn

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self.release()

    def release(self):
        if self._released:
            return
        self._released = True
        if self._pooled and self._manager.connection_pool is not None:
            self._manager.connection_pool.putconn(self._conn)
        else:
            self._conn.close()


class DatabaseManager:
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.pool_min = int(os.getenv("DB_POOL_MIN", "5"))
        self.pool_max = int(os.getenv("DB_POOL_MAX", "50"))
        self.connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))
        self.async_writes = os.getenv("DB_ASYNC_WRITES", "true").lower() in {
            "1", "true", "yes", "on"
        }
        self.batch_size = max(1, int(os.getenv("DB_BATCH_SIZE", "100")))
        self.batch_interval = max(0.01, float(os.getenv("DB_BATCH_INTERVAL", "0.25")))
        self.event_queue = queue.Queue(maxsize=int(os.getenv("DB_EVENT_QUEUE_SIZE", "5000")))
        self.event_writer_stop = threading.Event()
        self.event_writer_thread = None
        self.event_writer_stats = {
            "queued": 0,
            "written": 0,
            "dropped": 0,
            "sync_fallback": 0,
            "batch_failures": 0,
        }
        self.event_writer_stats_lock = threading.Lock()
        self.db_config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "database": os.getenv("DB_NAME", "surveillance_db"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", ""),
            "port": os.getenv("DB_PORT", "5432"),
        }
        # ─────────────────────────────────────────────────────────────
        # CONNECTION POOLING: Reuse connections instead of creating new ones
        # ─────────────────────────────────────────────────────────────
        self._pool_lock = threading.Lock()
        try:
            self.connection_pool = psycopg2_pool.ThreadedConnectionPool(
                minconn=self.pool_min,
                maxconn=self.pool_max,
                host=self.db_config["host"],
                database=self.db_config["database"],
                user=self.db_config["user"],
                password=self.db_config["password"],
                port=self.db_config["port"],
                connect_timeout=self.connect_timeout,
                cursor_factory=RealDictCursor,
            )
            log.info(f"Connection pool initialized ({self.pool_min}-{self.pool_max} connections)")
        except Exception as e:
            log.error(f"Could not create connection pool: {e}")
            raise

        self._init_db()
        self._migrate_db()
        self._start_event_writer()
        self._initialized = True

    def get_connection(self):
        """Get a connection from the pool."""
        if self.connection_pool is None:
            raise RuntimeError("Database connection pool is not initialized")

        try:
            conn = self.connection_pool.getconn()
            return PooledConnection(self, conn, pooled=True)
        except psycopg2_pool.PoolError as e:
            raise RuntimeError(
                f"Database connection pool exhausted ({self.pool_max} max). "
                "Increase DB_POOL_MAX or reduce request/worker concurrency."
            ) from e

    def _normalize_pagination(self, limit=100, offset=0, max_limit=1000):
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 100
        try:
            offset = int(offset)
        except (TypeError, ValueError):
            offset = 0
        limit = max(1, min(limit, max_limit))
        offset = max(0, offset)
        return limit, offset

    def close_connection(self, conn):
        """Return a connection back to the pool."""
        if isinstance(conn, PooledConnection):
            conn.release()
            return

        if self.connection_pool is not None:
            try:
                self.connection_pool.putconn(conn)
            except Exception as e:
                log.error(f"Error returning connection to pool: {e}")
                conn.close()
        else:
            conn.close()

    def close_pool(self):
        """Close all connections in the pool (call on shutdown)."""
        self.shutdown_event_writer()
        if self.connection_pool is not None:
            self.connection_pool.closeall()
            log.info("Connection pool closed")

    def _start_event_writer(self):
        if not self.async_writes or self.event_writer_thread is not None:
            return
        self.event_writer_thread = threading.Thread(
            target=self._event_writer_loop,
            daemon=True,
            name="DBEventWriter",
        )
        self.event_writer_thread.start()

    def shutdown_event_writer(self, timeout=5):
        if self.event_writer_thread is None:
            return
        start = time.time()
        while not self.event_queue.empty() and time.time() - start < timeout:
            time.sleep(0.05)
        self.event_writer_stop.set()
        self.event_writer_thread.join(timeout=timeout)

    def _event_writer_loop(self):
        while not self.event_writer_stop.is_set():
            events = []
            deadline = time.time() + self.batch_interval
            while len(events) < self.batch_size and time.time() < deadline:
                try:
                    timeout = max(0.01, deadline - time.time())
                    events.append(self.event_queue.get(timeout=timeout))
                except queue.Empty:
                    break
            if not events:
                continue
            ok = self.batch_insert_events(events)
            for _ in events:
                self.event_queue.task_done()
            if not ok:
                with self.event_writer_stats_lock:
                    self.event_writer_stats["dropped"] += len(events)
                    self.event_writer_stats["batch_failures"] += 1
                log.warning(f"Dropped {len(events)} event(s) after batch insert failure")
            else:
                with self.event_writer_stats_lock:
                    self.event_writer_stats["written"] += len(events)

    def _queue_event(self, event):
        if not self.async_writes:
            return self.batch_insert_events([event])
        try:
            self.event_queue.put_nowait(event)
            with self.event_writer_stats_lock:
                self.event_writer_stats["queued"] += 1
            return True
        except queue.Full:
            log.warning("Event queue full; writing synchronously")
            ok = self.batch_insert_events([event])
            with self.event_writer_stats_lock:
                self.event_writer_stats["sync_fallback"] += 1
                if ok:
                    self.event_writer_stats["written"] += 1
                else:
                    self.event_writer_stats["dropped"] += 1
            return ok

    def get_metrics(self):
        with self.event_writer_stats_lock:
            stats = self.event_writer_stats.copy()
        return {
            **stats,
            "event_queue_size": self.event_queue.qsize(),
            "event_queue_max": self.event_queue.maxsize,
            "async_writes": self.async_writes,
            "batch_size": self.batch_size,
            "batch_interval": self.batch_interval,
            "pool_min": self.pool_min,
            "pool_max": self.pool_max,
        }

    # ─────────────────────────────────────────────────────────────────────
    # HELPER: Context manager for pooled connections
    # ─────────────────────────────────────────────────────────────────────
    def _get_pooled_connection(self):
        """Helper method to properly manage pooled connections."""
        from contextlib import contextmanager

        @contextmanager
        def pooled_conn_context():
            conn = self.get_connection()
            try:
                yield conn
            finally:
                self.close_connection(conn)

        return pooled_conn_context()

    # ─────────────────────────────────────────────────────────────────────
    def _init_db(self):
        """Create tables if they do not already exist."""

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS detections (
                        id             SERIAL PRIMARY KEY,
                        created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        date           TEXT    NOT NULL,
                        time           TEXT    NOT NULL,
                        object_type    TEXT    NOT NULL,
                        event_type     TEXT    DEFAULT 'Entry',
                        track_id       INTEGER,
                        plate_number   TEXT,
                        plate_img_path TEXT,
                        image_path     TEXT    NOT NULL,
                        camera_name    TEXT    DEFAULT 'Main',
                        speed_kmh      FLOAT,
                        gender         TEXT
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS ppe_violations (
                        id             SERIAL PRIMARY KEY,
                        date           TEXT    NOT NULL,
                        time           TEXT    NOT NULL,
                        camera_name    TEXT    NOT NULL,
                        object_type    TEXT    NOT NULL,
                        violation_type TEXT    NOT NULL,
                        image_path     TEXT    NOT NULL
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS seatbelt_violations (
                        id             SERIAL PRIMARY KEY,
                        date           TEXT    NOT NULL,
                        time           TEXT    NOT NULL,
                        camera_name    TEXT    NOT NULL,
                        vehicle_type   TEXT    NOT NULL,
                        violation_type TEXT    NOT NULL,
                        image_path     TEXT    NOT NULL
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS night_alerts (
                        id             SERIAL PRIMARY KEY,
                        date           TEXT    NOT NULL,
                        time           TEXT    NOT NULL,
                        object_type    TEXT    NOT NULL,
                        plate_number   TEXT,
                        plate_img_path TEXT,
                        image_path     TEXT    NOT NULL,
                        camera_name    TEXT    NOT NULL
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS mobile_usage (
                        id             SERIAL PRIMARY KEY,
                        date           TEXT    NOT NULL,
                        time           TEXT    NOT NULL,
                        camera_name    TEXT    NOT NULL,
                        vehicle_type   TEXT    NOT NULL,
                        violation_type TEXT    NOT NULL,
                        image_path     TEXT    NOT NULL
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS mobile_walking_logs (
                        id             SERIAL PRIMARY KEY,
                        date           TEXT    NOT NULL,
                        time           TEXT    NOT NULL,
                        camera_name    TEXT    NOT NULL,
                        violation_type TEXT    NOT NULL,
                        image_path     TEXT    NOT NULL
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS restricted_zone_logs (
                        id             SERIAL PRIMARY KEY,
                        date           TEXT    NOT NULL,
                        time           TEXT    NOT NULL,
                        camera_name    TEXT    NOT NULL,
                        violation_type TEXT    NOT NULL,
                        image_path     TEXT    NOT NULL
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sleep_detection_logs (
                        id             SERIAL PRIMARY KEY,
                        date           TEXT    NOT NULL,
                        time           TEXT    NOT NULL,
                        camera_name    TEXT    NOT NULL,
                        violation_type TEXT    NOT NULL,
                        image_path     TEXT    NOT NULL
                    )
                ''')

                # ── violations table ──────────────────────────────────
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS violations (
                        id             SERIAL PRIMARY KEY,
                        date           TEXT,
                        time           TEXT,
                        timestamp      TIMESTAMP NOT NULL DEFAULT NOW(),
                        camera_id      TEXT      NOT NULL,
                        track_id       INTEGER,
                        global_id      TEXT,
                        violation_type TEXT      NOT NULL,
                        object_type    TEXT,
                        bbox           JSONB,
                        speed_kmh      FLOAT,
                        zone_id        TEXT,
                        metadata       JSONB     DEFAULT '{}',
                        image_path     TEXT
                    )
                ''')

                # ─────────────────────────────────────────────────────────────
                # ADD INDEXES FOR QUERY OPTIMIZATION
                # ─────────────────────────────────────────────────────────────
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_detections_date
                    ON detections(date DESC);
                ''')

                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_detections_created_at
                    ON detections(created_at DESC);
                ''')

                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_detections_camera_date
                    ON detections(camera_name, date DESC);
                ''')

                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_detections_camera_created_at
                    ON detections(camera_name, created_at DESC);
                ''')

                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_detections_object_type
                    ON detections(object_type);
                ''')

                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_ppe_violations_date
                    ON ppe_violations(date DESC);
                ''')

                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_ppe_violations_camera_date
                    ON ppe_violations(camera_name, date DESC);
                ''')

                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_seatbelt_violations_date
                    ON seatbelt_violations(date DESC);
                ''')

                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_night_alerts_date
                    ON night_alerts(date DESC);
                ''')

                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_mobile_usage_date
                    ON mobile_usage(date DESC);
                ''')

                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_mobile_walking_date
                    ON mobile_walking_logs(date DESC);
                ''')

                log.info("Database indexes created successfully")
                conn.commit()

    # ─────────────────────────────────────────────────────────────────────
    def _migrate_db(self):
        """Add new columns to existing PostgreSQL databases."""

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'detections'
                """)
                columns = [row['column_name'] for row in cursor.fetchall()]

                migrations = {
                    'event_type': "ALTER TABLE detections ADD COLUMN event_type TEXT DEFAULT 'Entry'",
                    'track_id': "ALTER TABLE detections ADD COLUMN track_id INTEGER",
                    'plate_number': "ALTER TABLE detections ADD COLUMN plate_number TEXT",
                    'plate_img_path': "ALTER TABLE detections ADD COLUMN plate_img_path TEXT",
                    'camera_name': "ALTER TABLE detections ADD COLUMN camera_name TEXT DEFAULT 'Main'",
                    'speed_kmh': "ALTER TABLE detections ADD COLUMN speed_kmh FLOAT",
                    'gender': "ALTER TABLE detections ADD COLUMN gender TEXT",
                }

                for col, sql in migrations.items():
                    if col not in columns:
                        cursor.execute(sql)

                # Add migration for night_alerts table
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'night_alerts'
                """)
                night_alert_columns = [row['column_name'] for row in cursor.fetchall()]

                if 'plate_img_path' not in night_alert_columns:
                    cursor.execute("ALTER TABLE night_alerts ADD COLUMN plate_img_path TEXT")

                # ── violations table: add missing columns if table existed
                #    before this schema version ──────────────────────────
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'violations'
                """)
                viol_cols = [row['column_name'] for row in cursor.fetchall()]

                violations_migrations = {
                    'date':           "ALTER TABLE violations ADD COLUMN date TEXT",
                    'time':           "ALTER TABLE violations ADD COLUMN time TEXT",
                    'timestamp':      "ALTER TABLE violations ADD COLUMN timestamp TIMESTAMP NOT NULL DEFAULT NOW()",
                    'camera_id':      "ALTER TABLE violations ADD COLUMN camera_id TEXT NOT NULL DEFAULT ''",
                    'track_id':       "ALTER TABLE violations ADD COLUMN track_id INTEGER",
                    'global_id':      "ALTER TABLE violations ADD COLUMN global_id TEXT",
                    'violation_type': "ALTER TABLE violations ADD COLUMN violation_type TEXT NOT NULL DEFAULT ''",
                    'object_type':    "ALTER TABLE violations ADD COLUMN object_type TEXT",
                    'bbox':           "ALTER TABLE violations ADD COLUMN bbox JSONB",
                    'speed_kmh':      "ALTER TABLE violations ADD COLUMN speed_kmh FLOAT",
                    'zone_id':        "ALTER TABLE violations ADD COLUMN zone_id TEXT",
                    'metadata':       "ALTER TABLE violations ADD COLUMN metadata JSONB DEFAULT '{}'",
                    'image_path':     "ALTER TABLE violations ADD COLUMN image_path TEXT",
                }

                if viol_cols:
                    for col, sql in violations_migrations.items():
                        if col not in viol_cols:
                            cursor.execute(sql)
                            log.info(f"violations: added column '{col}'")

                # ── violations indexes (safe here — columns guaranteed exist)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_violations_camera_id ON violations(camera_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_violations_timestamp ON violations(timestamp DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_violations_type ON violations(violation_type)")

                conn.commit()

    # ─────────────────────────────────────────────────────────────────────
    # BATCH INSERT: Combine multiple events into single transaction
    # This reduces database load from 50k queries/sec to 500 queries/sec
    # ─────────────────────────────────────────────────────────────────────
    def batch_insert_events(self, events):
        if not events:
            return

        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            for event in events:
                event_type = event.get('type')
                data = event.get('data')

                if event_type == 'detection':
                    cursor.execute('''
                        INSERT INTO detections
                            (date, time, object_type, event_type, track_id,
                             plate_number, plate_img_path, image_path,
                             camera_name, speed_kmh, gender)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''', data)

                elif event_type == 'ppe_violation':
                    cursor.execute('''
                        INSERT INTO ppe_violations
                            (date, time, camera_name, object_type, violation_type, image_path)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', data)

                elif event_type == 'night_alert':
                    cursor.execute('''
                        INSERT INTO night_alerts
                            (date, time, object_type, plate_number, image_path, camera_name)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', data)

                elif event_type == 'seatbelt_violation':
                    cursor.execute('''
                        INSERT INTO seatbelt_violations
                            (date, time, camera_name, vehicle_type, violation_type, image_path)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', data)

                elif event_type == 'mobile_usage':
                    cursor.execute('''
                        INSERT INTO mobile_usage
                            (date, time, camera_name, vehicle_type, violation_type, image_path)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', data)

                elif event_type == 'mobile_walking':
                    cursor.execute('''
                        INSERT INTO mobile_walking_logs
                            (date, time, camera_name, violation_type, image_path)
                        VALUES (%s, %s, %s, %s, %s)
                    ''', data)

            conn.commit()
            return True

        except Exception as e:
            conn.rollback()
            log.error(f"Batch insert error: {e}")
            return False

        finally:
            self.close_connection(conn)

    # ─────────────────────────────────────────────────────────────────────
    # NEW: Save a violation event with snapshot image path
    # ─────────────────────────────────────────────────────────────────────
    def insert_violation(self, camera_id, track_id, global_id,
                         violation_type, object_type, bbox,
                         speed_kmh, zone_id, metadata, image_path):
        """Save a violation event to the violations table."""
        from datetime import datetime as _dt
        now = _dt.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO violations
                        (date, time, camera_id, track_id, global_id, violation_type,
                         object_type, bbox, speed_kmh, zone_id,
                         metadata, image_path, timestamp)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    date_str,
                    time_str,
                    camera_id,
                    track_id,
                    global_id,
                    violation_type,
                    object_type,
                    json.dumps(bbox) if bbox else None,
                    speed_kmh,
                    zone_id,
                    json.dumps(metadata) if metadata else '{}',
                    image_path
                ))
                conn.commit()
                log.info(f"violation saved: {violation_type} camera={camera_id} track={track_id}")
        except Exception as e:
            log.error(f"insert_violation error: {e}")
            conn.rollback()
        finally:
            self.close_connection(conn)

    # ─────────────────────────────────────────────────────────────────────
    def insert_detection(self, object_type, image_path,
                         event_type='Entry', track_id=None,
                         plate_number=None, camera_name='Main',
                         speed_kmh=None, gender=None,
                         plate_img_path=None):
        """Persist one detection event."""
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        return self._queue_event({
            'type': 'detection',
            'data': (
                date_str, time_str, object_type, event_type, track_id,
                plate_number, plate_img_path, image_path, camera_name,
                speed_kmh, gender
            )
        })

    # ─────────────────────────────────────────────────────────────────────
    def insert_night_alert(self, object_type, image_path,
                           plate_number=None, plate_img_path=None, camera_name='Main'):
        """Persist one night-alert event."""
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO night_alerts
                        (date, time, object_type, plate_number, plate_img_path, image_path, camera_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''', (date_str, time_str, object_type, plate_number, plate_img_path,
                      image_path, camera_name))
                conn.commit()
        return True

    # ─────────────────────────────────────────────────────────────────────
    def insert_ppe_violation(self, object_type, violation_type, image_path,
                             camera_name='Main'):
        """Persist one PPE violation event."""
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO ppe_violations
                        (date, time, camera_name, object_type, violation_type, image_path)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', (date_str, time_str, camera_name, object_type,
                      violation_type, image_path))
                conn.commit()
        return True

    # ─────────────────────────────────────────────────────────────────────
    def get_recent_ppe_violations(self, limit=10):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT * FROM ppe_violations ORDER BY id DESC LIMIT %s', (limit,)
                )
                rows = cursor.fetchall()
        return rows

    def get_all_ppe_violations(self, date=None, camera=None, limit=100, offset=0):
        """Retrieve all PPE violations with optional filtering."""
        limit, offset = self._normalize_pagination(limit, offset)
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                query = "SELECT * FROM ppe_violations WHERE 1=1"
                params = []

                if date:
                    query += " AND date = %s"
                    params.append(date)
                if camera:
                    query += " AND camera_name = %s"
                    params.append(camera)

                query += " ORDER BY id DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                cursor.execute(query, params)
                rows = cursor.fetchall()
        return rows

    # ─────────────────────────────────────────────────────────────────────
    def get_ppe_stats_today(self):
        date_str = datetime.now().strftime("%Y-%m-%d")
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*)::int AS count FROM ppe_violations WHERE date=%s", (date_str,)
                )
                result = cursor.fetchone()
                return int(result.get('count', 0))

    # ─────────────────────────────────────────────────────────────────────
    def insert_seatbelt_violation(self, vehicle_type, violation_type, image_path,
                                  camera_name='Main'):
        """Persist one seatbelt violation event."""
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO seatbelt_violations
                        (date, time, camera_name, vehicle_type, violation_type, image_path)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', (date_str, time_str, camera_name, vehicle_type,
                      violation_type, image_path))
                conn.commit()
        return True

    # ─────────────────────────────────────────────────────────────────────
    def get_recent_seatbelt_violations(self, limit=10):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT * FROM seatbelt_violations ORDER BY id DESC LIMIT %s', (limit,)
                )
                rows = cursor.fetchall()
        return rows

    # ─────────────────────────────────────────────────────────────────────
    def insert_mobile_usage_violation(self, vehicle_type, violation_type, image_path,
                                      camera_name='Main'):
        """Persist one mobile usage violation event."""
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO mobile_usage
                        (date, time, camera_name, vehicle_type, violation_type, image_path)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', (date_str, time_str, camera_name, vehicle_type,
                      violation_type, image_path))
                conn.commit()
        return True

    # ─────────────────────────────────────────────────────────────────────
    def get_recent_mobile_usage_violations(self, limit=10):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT * FROM mobile_usage ORDER BY id DESC LIMIT %s', (limit,)
                )
                rows = cursor.fetchall()
        return rows

    # ─────────────────────────────────────────────────────────────────────
    def insert_mobile_walking_violation(self, violation_type, image_path,
                                        camera_name='Main'):
        """Persist one pedestrian mobile usage violation event."""
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO mobile_walking_logs
                        (date, time, camera_name, violation_type, image_path)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (date_str, time_str, camera_name, violation_type, image_path))
                conn.commit()
        return True

    # ─────────────────────────────────────────────────────────────────────
    def get_recent_mobile_walking_violations(self, limit=10):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT * FROM mobile_walking_logs ORDER BY id DESC LIMIT %s', (limit,)
                )
                rows = cursor.fetchall()
        return rows

    # ─────────────────────────────────────────────────────────────────────
    def insert_restricted_zone_violation(self, violation_type, image_path,
                                         camera_name='Main'):
        """Persist one restricted zone entry event."""
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO restricted_zone_logs
                        (date, time, camera_name, violation_type, image_path)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (date_str, time_str, camera_name, violation_type, image_path))
                conn.commit()
        return True

    # ─────────────────────────────────────────────────────────────────────
    def get_recent_restricted_violations(self, limit=10):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT * FROM restricted_zone_logs ORDER BY id DESC LIMIT %s', (limit,)
                )
                rows = cursor.fetchall()
        return rows

    # ─────────────────────────────────────────────────────────────────────
    def insert_sleep_violation(self, violation_type, image_path,
                               camera_name='Main'):
        """Persist one sleep detection event."""
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO sleep_detection_logs
                        (date, time, camera_name, violation_type, image_path)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (date_str, time_str, camera_name, violation_type, image_path))
                conn.commit()
        return True

    # ─────────────────────────────────────────────────────────────────────
    def get_recent_sleep_violations(self, limit=10):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT * FROM sleep_detection_logs ORDER BY id DESC LIMIT %s', (limit,)
                )
                rows = cursor.fetchall()
        return rows

    # ─────────────────────────────────────────────────────────────────────
    def get_all_detections(self, limit=100, offset=0):
        limit, offset = self._normalize_pagination(limit, offset)
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT * FROM detections ORDER BY id DESC LIMIT %s OFFSET %s',
                    (limit, offset)
                )
                rows = cursor.fetchall()
        return rows

    def get_recent_night_alerts(self, limit=10):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT * FROM night_alerts ORDER BY id DESC LIMIT %s', (limit,)
                )
                rows = cursor.fetchall()
        return rows

    def get_detections_by_category(self, categories, limit=100, offset=0):
        limit, offset = self._normalize_pagination(limit, offset)
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                placeholders = ', '.join(['%s'] * len(categories))
                query = (f'SELECT * FROM detections '
                         f'WHERE object_type IN ({placeholders}) '
                         f'ORDER BY id DESC LIMIT %s OFFSET %s')
                cursor.execute(query, list(categories) + [limit, offset])
                rows = cursor.fetchall()
        return rows

    # ─────────────────────────────────────────────────────────────────────
    def get_detections_by_camera(self, camera_name, limit=100, offset=0):
        """Return all detections for a specific camera, newest first."""
        limit, offset = self._normalize_pagination(limit, offset)
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT * FROM detections WHERE camera_name = %s '
                    'ORDER BY id DESC LIMIT %s OFFSET %s',
                    (camera_name, limit, offset)
                )
                rows = cursor.fetchall()
        return rows

    # ─────────────────────────────────────────────────────────────────────
    def get_plate_detections(self, limit=100, offset=0):
        """Return all detections that contain a number plate."""
        limit, offset = self._normalize_pagination(limit, offset)
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT * FROM detections '
                    'WHERE plate_number IS NOT NULL '
                    'ORDER BY id DESC LIMIT %s OFFSET %s',
                    (limit, offset)
                )
                rows = cursor.fetchall()
        return rows

    # ─────────────────────────────────────────────────────────────────────
    def get_stats_for_report(self, date_str):
        """Statistics for a specific date used in PDF report generation."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*)::int AS count FROM detections WHERE date=%s AND event_type='Entry'",
                    (date_str,)
                )
                entries = int(cursor.fetchone().get('count', 0))

                cursor.execute(
                    "SELECT COUNT(*)::int AS count FROM detections WHERE date=%s AND event_type='Exit'",
                    (date_str,)
                )
                exits = int(cursor.fetchone().get('count', 0))

                cursor.execute(
                    "SELECT COUNT(*)::int AS count FROM detections "
                    "WHERE date=%s AND object_type IN ('car','bus','truck','motorcycle')",
                    (date_str,)
                )
                vehicles = int(cursor.fetchone().get('count', 0))

                cursor.execute(
                    "SELECT COUNT(DISTINCT plate_number)::int AS count FROM detections "
                    "WHERE date=%s AND plate_number IS NOT NULL",
                    (date_str,)
                )
                unique_plates = int(cursor.fetchone().get('count', 0))

                cursor.execute("SELECT COUNT(*)::int AS count FROM night_alerts WHERE date=%s", (date_str,))
                night_alerts = int(cursor.fetchone().get('count', 0))

                cursor.execute("""
                    SELECT SUBSTRING(time, 1, 2) AS hour, COUNT(*)::int AS count
                    FROM detections
                    WHERE date = %s
                    GROUP BY hour
                """, (date_str,))
                hourly_data = {row['hour']: row['count'] for row in cursor.fetchall()}

        return {
            'entries': entries,
            'exits': exits,
            'vehicles': vehicles,
            'unique_plates': unique_plates,
            'night_alerts': night_alerts,
            'hourly_data': hourly_data,
        }

    # ─────────────────────────────────────────────────────────────────────
    def get_global_stats(self):
        """Aggregate statistics for the dashboard header cards."""
        today = datetime.now().strftime("%Y-%m-%d")
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*)::int AS count FROM detections WHERE event_type='Entry' AND date=%s", (today,))
                entries = int(cursor.fetchone().get('count', 0))

                cursor.execute("SELECT COUNT(*)::int AS count FROM detections WHERE event_type='Exit' AND date=%s", (today,))
                exits = int(cursor.fetchone().get('count', 0))

                cursor.execute(
                    "SELECT COUNT(*)::int AS count FROM detections "
                    "WHERE date=%s AND object_type IN ('car','bus','truck','motorcycle')",
                    (today,)
                )
                vehicles = int(cursor.fetchone().get('count', 0))

                cursor.execute("SELECT COUNT(*)::int AS count FROM night_alerts")
                night_alerts = int(cursor.fetchone().get('count', 0))

                cursor.execute("SELECT COUNT(*)::int AS count FROM ppe_violations WHERE date=%s", (today,))
                helmet_violations = int(cursor.fetchone().get('count', 0))

                cursor.execute("SELECT COUNT(*)::int AS count FROM seatbelt_violations WHERE date=%s", (today,))
                seatbelt_violations = int(cursor.fetchone().get('count', 0))

                cursor.execute("SELECT COUNT(*)::int AS count FROM mobile_usage WHERE date=%s", (today,))
                mobile_violations = int(cursor.fetchone().get('count', 0))

                cursor.execute("SELECT COUNT(*)::int AS count FROM mobile_walking_logs WHERE date=%s", (today,))
                mobile_walking_violations = int(cursor.fetchone().get('count', 0))

                cursor.execute("SELECT COUNT(*)::int AS count FROM restricted_zone_logs WHERE date=%s", (today,))
                restricted_violations = int(cursor.fetchone().get('count', 0))

                cursor.execute("SELECT COUNT(*)::int AS count FROM sleep_detection_logs WHERE date=%s", (today,))
                sleep_violations = int(cursor.fetchone().get('count', 0))

                cursor.execute("SELECT COUNT(*)::int AS count FROM detections WHERE date=%s AND object_type='person'", (today,))
                humans = int(cursor.fetchone().get('count', 0))

                cursor.execute("SELECT COUNT(*)::int AS count FROM detections WHERE date=%s AND object_type='car'", (today,))
                cars = int(cursor.fetchone().get('count', 0))

                cursor.execute("SELECT COUNT(*)::int AS count FROM detections WHERE date=%s AND object_type='truck'", (today,))
                trucks = int(cursor.fetchone().get('count', 0))

                cursor.execute("SELECT COUNT(*)::int AS count FROM detections WHERE date=%s AND object_type IN ('motorcycle', 'bicycle')", (today,))
                bikes = int(cursor.fetchone().get('count', 0))

                cursor.execute("""
                    SELECT SUBSTRING(time, 1, 2) AS hour,
                           SUM(CASE WHEN object_type='person' THEN 1 ELSE 0 END) as humans,
                           SUM(CASE WHEN object_type IN ('car','truck','bus','motorcycle') THEN 1 ELSE 0 END) as vehicles
                    FROM detections
                    WHERE date = %s
                    GROUP BY hour
                """, (today,))
                rows = cursor.fetchall()
                hourly_series = {
                    row['hour']: {
                        'humans': row['humans'],
                        'vehicles': row['vehicles']
                    }
                    for row in rows
                }

        return {
            'entries': entries,
            'exits': exits,
            'vehicles': vehicles,
            'humans': humans,
            'cars': cars,
            'trucks': trucks,
            'bikes': bikes,
            'night_alerts': night_alerts,
            'helmet_violations': helmet_violations,
            'seatbelt_violations': seatbelt_violations,
            'mobile_violations': mobile_violations,
            'mobile_walking_violations': mobile_walking_violations,
            'restricted_violations': restricted_violations,
            'sleep_violations': sleep_violations,
            'hourly_series': hourly_series,
        }

    # ─────────────────────────────────────────────────────────────────────
    def search_detections(self, date=None, time=None,
                          plate_number=None, camera_name=None,
                          object_type=None, limit=100, offset=0):
        """Flexible detection search. All params optional."""
        limit, offset = self._normalize_pagination(limit, offset)
        query = "SELECT * FROM detections WHERE 1=1"
        params = []

        if date:
            query += " AND date = %s"
            params.append(date)
        if time:
            query += " AND time LIKE %s"
            params.append(f"%{time}%")
        if plate_number:
            query += " AND plate_number LIKE %s"
            params.append(f"%{plate_number}%")
        if camera_name:
            query += " AND camera_name = %s"
            params.append(camera_name)
        if object_type:
            if object_type.lower() == 'plate':
                query += " AND plate_number IS NOT NULL"
            else:
                query += " AND object_type = %s"
                params.append(object_type)

        query += " ORDER BY id DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
        return rows

    def clear_all_history(self):
        """Truncate all history and violation tables."""
        if self.async_writes:
            self.event_queue.join()
        tables = [
            'detections', 'ppe_violations', 'seatbelt_violations',
            'mobile_usage', 'mobile_walking_logs', 'restricted_zone_logs',
            'sleep_detection_logs', 'night_alerts', 'violations'
        ]
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                for table in tables:
                    cursor.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
                conn.commit()
        return True

    def delete_detection(self, detection_id):
        """Delete a single detection record by ID."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM detections WHERE id = %s", (detection_id,))
                conn.commit()
        return True