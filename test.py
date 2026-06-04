import cv2
import stages.anpr

print(stages.anpr.__file__)

from stages.anpr import ANPRStage

anpr = ANPRStage()

img = cv2.imread(
    r"C:\Users\abhin\OneDrive\Documents\surveillance-pipeline-main\stages\test.jpg.jpg"
)

class DummyTrack:
    track_id = 1
    bbox = [0, 0, img.shape[1], img.shape[0]]

plate = anpr.process_vehicle(
    img,
    DummyTrack()
)

print("PLATE =", plate)