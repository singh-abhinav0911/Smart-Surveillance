# config/settings.py

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:

    # -- App --------------------------------------------------
    APP_HOST  = os.getenv("APP_HOST", "127.0.0.1")
    APP_PORT  = int(os.getenv("APP_PORT", 8000))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # -- Database ---------------------------------------------
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", 5432))
    DB_NAME = os.getenv("DB_NAME", "surveillance_db")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASS = os.getenv("DB_PASSWORD", "postgres")
    DB_MIN  = int(os.getenv("DB_MIN_CONN", 5))
    DB_MAX  = int(os.getenv("DB_MAX_CONN", 20))

    # -- Redis ------------------------------------------------
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

    # -- Model ------------------------------------------------
    MODEL_PATH        = os.getenv("MODEL_PATH", "models/yolov8n.pt")
    MODEL_CONF        = float(os.getenv("MODEL_CONF", 0.5))
    MODEL_IMGSZ       = int(os.getenv("MODEL_IMGSZ", 640))
    INFERENCE_EVERY_N = int(os.getenv("INFERENCE_EVERY_N", 3))

    # -- Speed ------------------------------------------------
    SPEED_LIMIT    = float(os.getenv("SPEED_LIMIT_KMH", 60))
    PIXELS_PER_MTR = float(os.getenv("PIXELS_PER_METER", 10))

    # -- Line crossing Y position (pixels from top) -----------
    LINE_Y = int(os.getenv("LINE_Y", 360))

    # -- Cameras ----------------------------------------------
    _raw_cameras = os.getenv("CAMERA_SOURCES", "gate_1:data/test_videos/test.mp4")
    CAMERAS: dict = {
        name.strip(): (int(src.strip()) if src.strip().isdigit() else src.strip())
        for entry in _raw_cameras.split(",")
        if ":" in entry
        for name, _, src in [entry.strip().partition(":")]
    }


settings = Settings()