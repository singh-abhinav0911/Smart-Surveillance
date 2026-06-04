class ZoneManager:

    def __init__(self, zones):

        self.zones = zones

    def get_zone(self, x, y):

        for zone in self.zones:

            if zone.contains(x, y):
                return zone

        return None