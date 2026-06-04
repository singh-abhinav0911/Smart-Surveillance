class CounterStage:

    def __init__(self, line_y=300):

        self.line_y = line_y

        self.in_count = 0
        self.out_count = 0

        self.track_positions = {}

        self.counted_ids = set()

    def process(self, message, shared_state):

        for track in message.tracks:

            track_id = track["track_id"]

            x1, y1, x2, y2 = track["bbox"]

            center_y = (y1 + y2) / 2

            previous_y = self.track_positions.get(track_id)

            if previous_y is not None:

                # crossed downward
                if previous_y < self.line_y and center_y >= self.line_y:

                    if track_id not in self.counted_ids:

                        self.in_count += 1
                        self.counted_ids.add(track_id)

                # crossed upward
                elif previous_y > self.line_y and center_y <= self.line_y:

                    if track_id not in self.counted_ids:

                        self.out_count += 1
                        self.counted_ids.add(track_id)

            self.track_positions[track_id] = center_y

        message.analytics["in_count"] = self.in_count
        message.analytics["out_count"] = self.out_count

        return message