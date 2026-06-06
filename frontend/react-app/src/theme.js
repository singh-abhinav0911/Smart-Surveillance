export const C = {
  bg:       "#0a0c0f",
  surface:  "#111418",
  surface2: "#161b22",
  border:   "#1e2329",
  accent:   "#e8ff47",
  red:      "#ff4444",
  orange:   "#ff8c00",
  blue:     "#4499ff",
  green:    "#00cc66",
  muted:    "#4a5568",
  text:     "#e2e8f0",
  textDim:  "#718096",
};

export const BASE = "http://127.0.0.1:8000";

export const VCOLOR = {
  speed_violation: C.orange,
  ppe_violation:   C.red,
  intrusion:       C.blue,
};

export const VLABEL = {
  speed_violation: "SPEED",
  ppe_violation:   "PPE",
  intrusion:       "ZONE",
};

export const MONO = "'Share Tech Mono', monospace";

export function snapshotUrl(image_path) {
  if (!image_path) return null;
  const filename = image_path.split(/[\\/]/).pop();
  return `${BASE}/snapshots/${filename}`;
}

export const GLOBAL_STYLES = `
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=DM+Sans:wght@300;400;500;600&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: ${C.bg}; color: ${C.text}; font-family: 'DM Sans', 'Segoe UI', sans-serif; font-size: 13px; }
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: ${C.bg}; }
  ::-webkit-scrollbar-thumb { background: ${C.border}; border-radius: 2px; }
  @keyframes ping { 75%,100% { transform:scale(2); opacity:0; } }
  @keyframes fadeIn { from { opacity:0; transform:translateY(-4px); } to { opacity:1; transform:translateY(0); } }
  @keyframes spin { to { transform: rotate(360deg); } }
  a { text-decoration: none; color: inherit; }
`;