from dataclasses import dataclass,field
import numpy as np
from typing import List

@dataclass
class Detection:
    bbox: list
    confidence: float
    class_id: int

@dataclass
class Track:
    track_id: int
    bbox: list
    class_id: int 
    global_id: int = None
    speed: float = None
    plate: str = None

@dataclass
class FramePacket:
    camera_id: str
    frame: np.ndarray
    timestamp: float

@dataclass
class DetectionPacket:
    camera_id: str
    frame: np.ndarray
    detections: List[Detection]
    timestamp: float
    tracks: list = field(default_factory=list)

@dataclass
class TrackPacket:
    camera_id: str
    frame: np.ndarray
    tracks: List[Track]
    timestamp: float

@dataclass
class AnalyticsPacket:
    camera_id: str
    frame: np.ndarray
    tracks: List[Track]
    analytics: dict
    timestamp: float  
    
      