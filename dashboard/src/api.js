const BASE = "http://localhost:8000/api";

export async function fetchStats() {
  const res = await fetch(`${BASE}/stats`);
  if (!res.ok) throw new Error("stats fetch failed");
  return res.json();
}

export async function fetchViolations(limit = 20, offset = 0) {
  const res = await fetch(`${BASE}/violations?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error("violations fetch failed");
  return res.json();
}

export async function fetchDetections(limit = 20, offset = 0) {
  const res = await fetch(`${BASE}/detections?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error("detections fetch failed");
  return res.json();
}