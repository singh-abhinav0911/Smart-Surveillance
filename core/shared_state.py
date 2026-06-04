


class SharedState:

    def __init__(self):

        
        # =========================
        # LIVE VIDEO FRAMES
        # =========================

        self.latest_frames = {}

        # =========================
        # GLOBAL HUMAN IDS
        # =========================

        self.unique_humans = {}

        # =========================
        # CAMERA STATS
        # =========================

        self.camera_stats = {}

        # =========================
        # ACTIVE TRACKS
        # =========================

        self.active_tracks = {}

        # =========================
        # GLOBAL ALERTS
        # =========================

        self.alerts = []

        # =========================
        # TRACK HISTORY
        # =========================

        self.track_history = {}

        # =========================
        # GLOBAL REID EMBEDDINGS
        # =========================

        self.embeddings = {}