# stages/analytics.py

import queue
from collections import defaultdict

from core.zones import zone
from core.speed_estimator import SpeedEstimator
from core.events_type import EventType
from core.event_scheme import create_event
from core.constants import CLASS_MAP
from stages.anpr import ANPRStage
from utils.queue_utils import safe_put


class AnalyticsStage:

    def __init__(self, input_queue, output_queue, db_queue, event_engine,
                 alert_engine, zone_manager, camera_id, line_y,
                 speed_estimator=None, anpr=None):

        self.input_queue   = input_queue
        self.output_queue  = output_queue
        self.db_queue      = db_queue
        self.event_engine  = event_engine
        self.alert_engine  = alert_engine
        self.zone_manager  = zone_manager
        self.camera_id     = camera_id
        self.line_y        = line_y
        self.speed_estimator    = speed_estimator
        self.anpr               = anpr
        self.last_positions     = {}
        self.active_ppe_alerts  = set()
        self.active_intrusions  = set()
        self.known_plates       = {}
        self.in_count           = 0
        self.out_count          = 0
        self.running            = True

    def run(self):
        print("[ANALYTICS] started")

        while self.running:

            # ── Get with timeout — never block forever ────────────────
            try:
                message = self.input_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[ANALYTICS] get error: {e}")
                continue

            print(f"[ANALYTICS] processing {len(message.tracks)} tracks")

            for track in message.tracks:

                track_id = track.track_id
                x1, y1, x2, y2 = track.bbox
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2

                # ── Zone check ────────────────────────────────────────
                try:
                    zone = self.zone_manager.get_zone(cx, cy)
                except Exception:
                    zone = None

                # ── Speed estimation ──────────────────────────────────
                if self.speed_estimator and track.class_id in [2, 3, 5, 7]:
                    try:
                        speed, violation = self.speed_estimator.update(
                            track_id, track.bbox
                        )
                        if speed is not None:
                            track.speed = speed
                            if violation:
                                event = create_event(
                                    event_type=EventType.SPEED_VIOLATION,
                                    track_id=track_id,
                                    global_id=track.global_id,
                                    camera_id=self.camera_id,
                                    bbox=track.bbox,
                                    metadata={"speed": speed,
                                              "limit": self.speed_estimator.speed_limit}
                                )
                                self.event_engine.emit(event)
                                # ── Speed violation ───────────────────
                                safe_put(self.db_queue, {
                                    "violation": {
                                        "camera_id":      self.camera_id,
                                        "track_id":       track_id,
                                        "global_id":      getattr(track, "global_id", track_id),
                                        "violation_type": "speed_violation",
                                        "object_type":    CLASS_MAP.get(track.class_id, "unknown"),
                                        "bbox":           list(track.bbox),
                                        "speed_kmh":      round(speed, 2),
                                        "zone_id":        None,
                                        "metadata":       {"limit": self.speed_estimator.speed_limit}
                                    },
                                    "frame": message.frame.copy()
                                })
                    except Exception as e:
                        print(f"[ANALYTICS] speed error: {e}")

                # ── ANPR ──────────────────────────────────────────────
                if self.anpr and track.class_id in [2, 3, 5, 7]:
                    try:
                        if track.track_id not in self.known_plates:
                            plate = self.anpr.process_vehicle(message.frame, track)
                            if plate:
                                self.known_plates[track.track_id] = plate
                                track.plate = plate
                    except Exception as e:
                        print(f"[ANALYTICS] anpr error: {e}")

                # ── DB packet ─────────────────────────────────────────
                vehicle_type = CLASS_MAP.get(track.class_id, "unknown")
                db_packet = {
                    "db_event": {
                        "camera_id":    self.camera_id,
                        "track_id":     track.track_id,
                        "vehicle_type": vehicle_type,
                        "plate_number": getattr(track, "plate", None),
                        "speed_kmh":    getattr(track, "speed", None)
                    }
                }
                safe_put(self.db_queue, db_packet)

                # ── PPE check ─────────────────────────────────────────
                if track.class_id == 0:
                    key = f"{track.global_id}_helmet"
                    if key not in self.active_ppe_alerts:
                        self.active_ppe_alerts.add(key)
                        # ── PPE violation ─────────────────────────────
                        safe_put(self.db_queue, {
                            "violation": {
                                "camera_id":      self.camera_id,
                                "track_id":       track.track_id,
                                "global_id":      getattr(track, "global_id", track.track_id),
                                "violation_type": "ppe_violation",
                                "object_type":    "person",
                                "bbox":           list(track.bbox),
                                "speed_kmh":      None,
                                "zone_id":        None,
                                "metadata":       {"violation": "helmet_missing"}
                            },
                            "frame": message.frame.copy()
                        })

                # ── Zone violation ────────────────────────────────────
                if zone and getattr(zone, "zone_type", None) == "restricted":
                    intrusion_key = (track.global_id, zone.zone_id)
                    if intrusion_key not in self.active_intrusions:
                        self.active_intrusions.add(intrusion_key)
                        try:
                            self.alert_engine.trigger(
                                camera_id=self.camera_id,
                                alert_type="intrusion",
                                alert={"type": "INTRUSION",
                                       "track_id": track_id,
                                       "global_id": track.global_id,
                                       "zone_id": zone.zone_id}
                            )
                        except Exception as e:
                            print(f"[ANALYTICS] zone alert error: {e}")
                        # ── Zone intrusion ────────────────────────────
                        safe_put(self.db_queue, {
                            "violation": {
                                "camera_id":      self.camera_id,
                                "track_id":       track_id,
                                "global_id":      getattr(track, "global_id", track_id),
                                "violation_type": "intrusion",
                                "object_type":    CLASS_MAP.get(track.class_id, "unknown"),
                                "bbox":           list(track.bbox),
                                "speed_kmh":      None,
                                "zone_id":        getattr(zone, "zone_id", None),
                                "metadata":       {}
                            },
                            "frame": message.frame.copy()
                        })

                # ── Line crossing ─────────────────────────────────────
                if track_id not in self.last_positions:
                    self.last_positions[track_id] = cy
                    continue

                prev_y = self.last_positions[track_id]

                if prev_y < self.line_y and cy >= self.line_y:
                    self.in_count += 1
                    print(f"[ANALYTICS] IN — total={self.in_count}")
                    try:
                        event = create_event(
                            event_type=EventType.DETECTION,
                            track_id=track_id,
                            global_id=track.global_id,
                            camera_id=self.camera_id,
                            bbox=track.bbox,
                            metadata={"direction": "IN"}
                        )
                        self.event_engine.emit(event)
                    except Exception as e:
                        print(f"[ANALYTICS] line event error: {e}")

                elif prev_y > self.line_y and cy <= self.line_y:
                    self.out_count += 1
                    print(f"[ANALYTICS] OUT — total={self.out_count}")
                    try:
                        event = create_event(
                            event_type=EventType.DETECTION,
                            track_id=track_id,
                            global_id=track.global_id,
                            camera_id=self.camera_id,
                            bbox=track.bbox,
                            metadata={"direction": "OUT"}
                        )
                        self.event_engine.emit(event)
                    except Exception as e:
                        print(f"[ANALYTICS] line event error: {e}")

                self.last_positions[track_id] = cy

            # ── Attach analytics summary to message ───────────────────
            message.camera_id = self.camera_id
            message.analytics = {
                "in_count":  self.in_count,
                "out_count": self.out_count
            }
            print("[ANALYTICS] sending to visualizer")
            print("visual queue size =", self.output_queue.qsize())


            safe_put(self.output_queue, message)
            print("visual queue size after =", self.output_queue.qsize())

    def stop(self):
        self.running = False