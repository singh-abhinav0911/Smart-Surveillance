import numpy as np
import time

from torch import embedding


class ReIDManager:

    def __init__(self):

        self.global_id = 0

        self.global_memory = {}

        self.embeddings_db = {}

        self.track_memory = {}

        self.lost_tracks = {}

        self.max_gap = 5  # seconds

        self.similarity_threshold = 0.75

        self.memory_timeout = 50  # frames or ticks

    # -------------------------
    # UTILS
    # -------------------------

    def _now(self):
        return time.time()

    def normalize(self, x):
        return x / (np.linalg.norm(x) + 1e-6)

    def cosine_similarity(self, a, b):

        a = self.normalize(a)
        b = self.normalize(b)

        return np.dot(a, b)

    # -------------------------
    # CORE ID ASSIGNMENT
    # -------------------------

    def assign_global_id(self, embedding):

        embedding = self.normalize(embedding)

        best_match = None
        best_score = -1

        for gid, stored_embedding in self.embeddings_db.items():

            stored_embedding = self.normalize(stored_embedding)

            score = np.dot(embedding, stored_embedding)

            if score > best_score:
                best_score = score
                best_match = gid

        if best_score > self.similarity_threshold:
            return best_match

        self.global_id += 1
        gid = self.global_id

        self.embeddings_db[gid] = embedding

        return gid

        
    
    def get_global_id(self, embedding):

        embedding = self.normalize(embedding)

        best_id = None
        best_score = -1

        for gid, stored_embedding in self.embeddings_db.items():

            stored_embedding = self.normalize(stored_embedding)
            score = np.dot(embedding, stored_embedding)

            if score > best_score:
                best_score = score
                best_id = gid

        if best_score > self.similarity_threshold:
            return best_id

        return None

    # -------------------------
    # TRACK UPDATE (ASYNC ENTRY POINT)
    # -------------------------

    def update_track(self, track_id, embedding, cam_id):

        gid = self.assign_global_id(embedding)

        self.track_memory[track_id] = gid

        now = self._now()

        if gid not in self.global_memory:

            self.global_memory[gid] = {
                "embedding": embedding,
                "last_cam": cam_id,
                "last_seen": now,
                "history": [cam_id]
            }

        else:

            self.global_memory[gid]["embedding"] = embedding
            self.global_memory[gid]["last_cam"] = cam_id
            self.global_memory[gid]["last_seen"] = now

            if cam_id not in self.global_memory[gid]["history"]:
                self.global_memory[gid]["history"].append(cam_id)

        return gid
    
    # -------------------------
    # RE-IDENTIFICATION LOGIC
    # -------------------------

    def recover_from_occlusion(self, embedding):

        embedding = self.normalize(embedding)

        best_gid = None
        best_score = -1

        # check lost tracks first (IMPORTANT)
        for track_id, data in self.lost_tracks.items():

            score = np.dot(
                embedding,
                self.normalize(data["embedding"])
            )

            if score > best_score:
                best_score = score
                best_gid = data["global_id"]

        if best_score > self.similarity_threshold:

            return best_gid

        # fallback to normal DB
        return self.assign_global_id(embedding)

    
    
    def mark_lost(self, track_id, gid, embedding, cam_id):

        self.lost_tracks[track_id] = {
            "global_id": gid,
            "embedding": embedding,
            "cam_id": cam_id,
            "lost_time": self._now()
        }

    # -------------------------
    # CLEANUP LOST TRACKS (IMPORTANT FOR MEMORY MANAGEMENT)
    # -------------------------    

    def cleanup_lost_tracks(self):

        now = self._now()

        to_delete = []

        for tid, data in self.lost_tracks.items():

            if now - data["lost_time"] > self.max_gap:
                to_delete.append(tid)

        for tid in to_delete:
            del self.lost_tracks[tid]    

    # -------------------------
    # CLEANUP OLD TRACKS (IMPORTANT FOR 10 CAMS)
    # -------------------------

    def cleanup(self):

        now = self._now()

        to_delete = []

        for track_id, data in self.track_memory.items():

            if now - data["last_seen"] > self.memory_timeout:
                to_delete.append(track_id)

        for tid in to_delete:
            del self.track_memory[tid]