from core.messages import Detection


log = get_logger("detector_stage")


class DetectorStage:

    def __init__(self, input_queue, output_queue, shared_state):

        self.input_queue = input_queue
        self.output_queue = output_queue
        self.shared_state = shared_state
        self.running

    def parse_result(self, result):

        detections = []

        for r in result.boxes.data.tolist():

            x1, y1, x2, y2, score, class_id = r
            class_id = int(class_id)

            # PERSON ONLY
            if class_id not in [0, 2, 3, 5, 7]:
                continue


            detections.append(
                Detection(
                    bbox=[x1, y1, x2, y2],
                    confidence=float(score),
                    class_id=class_id
                )
            )

        return detections

    def handle_result(self, cam_id, message, result):

        detections = self.parse_result(result)

        message.detections = detections

        log.debug(f"{len(detections)} detections")

        # forward to next stage (tracker)
        self.output_queue.put((cam_id, message))

    def run(self):
        log.info("started")

        while self.running:

            # NOW we expect (cam_id, message, result)
            cam_id, message, result = self.input_queue.get()
            log.debug("got result")

            self.handle_result(cam_id, message, result)

    def stop(self):
        self.running = False        