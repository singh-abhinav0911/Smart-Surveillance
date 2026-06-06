# stages/analytics.py

import time
import queue
from utils.logger import get_logger
from core.speed_estimator import SpeedEstimator
from core.events_type import EventType
from core.event_scheme import create_event
from core.constants import CLASS_MAP
from utils.queue_utils import safe_put

log = get_logger("analytics")


class AnalyticsStage:

    def __init__(self, input_queue, output_queue, db_queue, event_engine,
                 alert_engine, zone_manager, camera_id, line_y,
                 speed_estimator=None, anpr=None, stream_queue=None):

        self.input_queue         = input_queue
        self.output_queue        = output_queue
        self.db_queue            = db_queue
        self.stream_queue        = stream_queue   # can be None
        self.event_engine        = event_engine
        self.alert_engine        = alert_engine
        self.zone_manager        = zone_manager
        self.camera_id           = camera_id
        self.line_y              = line_y
        self.speed_estimator     = speed_estimator
        self.anpr                = anpr

        self.last_positions      = {}
        self.active_ppe_alerts   = set()
        self.active_intrusions   = set()
        self.known_plates        = {}
        self.in_count            = 0
        self.out_count           = 0
        self.running             = True

        self.violation_cooldowns    = {}
        self.VIOLATION_COOLDOWN_SEC = 10

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _should_fire_violation(self, track_id: int, violation_type: str) -> bool:
        key  = f"{track_id}_{violation_type}"
        last = self.violation_cooldowns.get(key, 0)
        now  = time.time()
        if now - last > self.VIOLATION_COOLDOWN_SEC:
            self.violation_cooldowns[key] = now
            return True
        return False

    def _send_violation(self, violation: dict, frame):
        """Send violation to db_queue with frame snapshot."""
        safe_put(self.db_queue, {
            "violation": violation,
            "frame":     frame
        })
        log.info(f"violation fired: {violation['violation_type']} "
                 f"track={violation['track_id']}")

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        log.info("started")

        while self.running:

            try:
                message = self.input_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            except Exception as e:
                log.debug(f"get error: {e}")
                continue

            log.debug(f"processing {len(message.tracks)} tracks")

            for track in message.tracks:

                track_id      = track.track_id
                x1, y1, x2, y2 = track.bbox
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2

                # ── Zone check ────────────────────────────────────────
                current_zone = None
                try:
                    current_zone = self.zone_manager.get_zone(cx, cy)
                except Exception:
                    pass

                # ── Speed estimation ──────────────────────────────────
                if self.speed_estimator and track.class_id in [2, 3, 5, 7]:
                    try:
                        speed, violation = self.speed_estimator.update(
                            track_id, track.bbox
                        )
                        if speed is not None:
                            track.speed = speed
                            if violation and self._should_fire_violation(
                                    track_id, "speed_violation"):
                                self.event_engine.emit(create_event(
                                    event_type=EventType.SPEED_VIOLATION,
                                    track_id=track_id,
                                    global_id=track.global_id,
                                    camera_id=self.camera_id,
                                    bbox=track.bbox,
                                    metadata={"speed": speed,
                                              "limit": self.speed_estimator.speed_limit}
                                ))
                                self._send_violation({
                                    "camera_id":      self.camera_id,
                                    "track_id":       track_id,
                                    "global_id":      getattr(track, "global_id", track_id),
                                    "violation_type": "speed_violation",
                                    "object_type":    CLASS_MAP.get(track.class_id, "unknown"),
                                    "bbox":           list(track.bbox),
                                    "speed_kmh":      round(speed, 2),
                                    "zone_id":        None,
                                    "metadata":       {"limit": self.speed_estimator.speed_limit}
                                }, message.frame.copy())
                    except Exception as e:
                        log.debug(f"speed error: {e}")

                # ── ANPR ──────────────────────────────────────────────
                if self.anpr and track.class_id in [2, 3, 5, 7]:
                    try:
                        if track_id not in self.known_plates:
                            plate = self.anpr.process_vehicle(message.frame, track)
                            if plate:
                                self.known_plates[track_id] = plate
                                track.plate = plate
                                log.info(f"plate detected: {plate} track={track_id}")
                    except Exception as e:
                        log.debug(f"anpr error: {e}")

                # ── PPE check (persons in restricted zones only) ───────
                if track.class_id == 0:
                    in_restricted = (
                        current_zone is not None and
                        getattr(current_zone, "zone_type", None) == "restricted"
                    )
                    if in_restricted and self._should_fire_violation(
                            track_id, "ppe_violation"):
                        log.info(f"PPE violation track={track_id} zone={current_zone.zone_id}")
                        self._send_violation({
                            "camera_id":      self.camera_id,
                            "track_id":       track.track_id,
                            "global_id":      getattr(track, "global_id", track.track_id),
                            "violation_type": "ppe_violation",
                            "object_type":    "person",
                            "bbox":           list(track.bbox),
                            "speed_kmh":      None,
                            "zone_id":        getattr(current_zone, "zone_id", None),
                            "metadata":       {"violation": "helmet_missing"}
                        }, message.frame.copy())

                # ── Zone intrusion ────────────────────────────────────
                if (current_zone and
                        getattr(current_zone, "zone_type", None) == "restricted"):
                    intrusion_key = (
                        getattr(track, "global_id", track_id),
                        current_zone.zone_id
                    )
                    if (intrusion_key not in self.active_intrusions and
                            self._should_fire_violation(track_id, "intrusion")):
                        self.active_intrusions.add(intrusion_key)
                        try:
                            self.alert_engine.trigger(
                                camera_id=self.camera_id,
                                alert_type="intrusion",
                                alert={
                                    "type":      "INTRUSION",
                                    "track_id":  track_id,
                                    "global_id": getattr(track, "global_id", track_id),
                                    "zone_id":   current_zone.zone_id
                                }
                            )
                        except Exception as e:
                            log.debug(f"zone alert error: {e}")

                        self._send_violation({
                            "camera_id":      self.camera_id,
                            "track_id":       track_id,
                            "global_id":      getattr(track, "global_id", track_id),
                            "violation_type": "intrusion",
                            "object_type":    CLASS_MAP.get(track.class_id, "unknown"),
                            "bbox":           list(track.bbox),
                            "speed_kmh":      None,
                            "zone_id":        getattr(current_zone, "zone_id", None),
                            "metadata":       {}
                        }, message.frame.copy())

                # ── Line crossing ─────────────────────────────────────
                if track_id not in self.last_positions:
                    self.last_positions[track_id] = cy
                    continue

                prev_y = self.last_positions[track_id]

                if prev_y < self.line_y and cy >= self.line_y:
                    self.in_count += 1
                    log.info(f"IN — total={self.in_count}")
                    try:
                        self.event_engine.emit(create_event(
                            event_type=EventType.DETECTION,
                            track_id=track_id,
                            global_id=track.global_id,
                            camera_id=self.camera_id,
                            bbox=track.bbox,
                            metadata={"direction": "IN"}
                        ))
                    except Exception as e:
                        log.debug(f"line IN event error: {e}")

                elif prev_y > self.line_y and cy <= self.line_y:
                    self.out_count += 1
                    log.info(f"OUT — total={self.out_count}")
                    try:
                        self.event_engine.emit(create_event(
                            event_type=EventType.DETECTION,
                            track_id=track_id,
                            global_id=track.global_id,
                            camera_id=self.camera_id,
                            bbox=track.bbox,
                            metadata={"direction": "OUT"}
                        ))
                    except Exception as e:
                        log.debug(f"line OUT event error: {e}")

                self.last_positions[track_id] = cy

            # ── Attach analytics and forward to display queues ────────
            message.camera_id = self.camera_id
            message.analytics = {
                "in_count":  self.in_count,
                "out_count": self.out_count
            }

            safe_put(self.output_queue, message)

            # ── Stream queue is optional ──────────────────────────────
            if self.stream_queue is not None:
                safe_put(self.stream_queue, message)

    def stop(self):
        self.running = False