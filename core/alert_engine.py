import time

class AlertEngine:

    

    def __init__(self, shared_state, rules):

        self.shared_state = shared_state
        self.rules = rules
        self.cooldowns = {}

    def trigger(self, camera_id, alert_type, alert):

        rule = self.rules.get(camera_id, {}).get(
            alert_type,
            {"enabled": True, "cooldown": 0}
        )

        if not rule["enabled"]:
            return

        key = (camera_id, alert_type, alert.get("track_id"))
        now = time.time()

        if key in self.cooldowns:
            if now - self.cooldowns[key] < rule["cooldown"]:
                return

        self.cooldowns[key] = now

        self.shared_state.alerts.append(alert)