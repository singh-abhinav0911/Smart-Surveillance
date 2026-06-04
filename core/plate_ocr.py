import easyocr

class PlateOCR:

    def __init__(self):

        self.reader = easyocr.Reader(
            ["en"],
            gpu=False
        )

    def read_plate(self, image):

        try:

            results = self.reader.readtext(image)

            if not results:
                return None

            best = max(
                results,
                key=lambda x: x[2]
            )

            plate = best[1]

            return (
                plate
                .replace(" ", "")
                .replace("-", "")
                .upper()
            )

        except Exception as e:

            print("[OCR ERROR]", e)

            return None