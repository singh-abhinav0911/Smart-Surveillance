import { useEffect, useState, useRef, useCallback } from "react";
import { connectWS, subscribeWS } from "./ws";
import { fetchStats, fetchViolations } from "./api";

// ── Palette & constants ───────────────────────────────────────────────────────
const COLORS = {
  bg:        "#0a0c0f",
  surface:   "#111418",
  border:    "#1e2329",
  accent:    "#e8ff47",       // sharp lime-yellow
  accentDim: "#b8cc30",
  red:       "#ff4444",
  orange:    "#ff8c00",
  blue:      "#4499ff",
  muted:     "#4a5568",
  text:      "#e2e8f0",
  textDim:   "#718096",
};

const VIOLATION_COLOR = {
  speed_violation: COLORS.orange,
  ppe_violation:   COLORS.red,
  intrusion:       COLORS.blue,
};

const VIOLATION_LABEL = {
  speed_violation: "SPEED",
  ppe_violation:   "PPE",
  intrusion:       "ZONE",
};

// ── Tiny bar-chart component ──────────────────────────────────────────────────
function MiniBarChart({ data, color }) {
  if (!data || data.length === 0) return null;
  const max = Math.max(...data.map(d => d.value), 1);
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 48 }}>
      {data.map((d, i) => (
        <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
          <div style={{
            width: "100%",
            height: `${(d.value / max) * 44}px`,
            background: color,
            opacity: 0.85,
            borderRadius: 2,
            minHeight: d.value > 0 ? 3 : 0,
            transition: "height 0.4s ease",
          }} />
        </div>
      ))}
    </div>
  );
}

// ── Stat card ─────────────────────────────────────────────────────────────────
function StatCard({ label, value, accent, sub, trend }) {
  return (
    <div style={{
      background: COLORS.surface,
      border: `1px solid ${COLORS.border}`,
      borderTop: `2px solid ${accent || COLORS.border}`,
      padding: "18px 20px",
      borderRadius: 4,
      minWidth: 0,
    }}>
      <div style={{ color: COLORS.textDim, fontSize: 10, letterSpacing: "0.15em", textTransform: "uppercase", marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ color: accent || COLORS.text, fontSize: 32, fontFamily: "'Share Tech Mono', monospace", lineHeight: 1 }}>
        {value ?? "—"}
      </div>
      {sub && (
        <div style={{ color: COLORS.textDim, fontSize: 11, marginTop: 6 }}>{sub}</div>
      )}
    </div>
  );
}

// ── Violation badge ───────────────────────────────────────────────────────────
function VBadge({ type }) {
  const color = VIOLATION_COLOR[type] || COLORS.muted;
  const label = VIOLATION_LABEL[type] || type?.toUpperCase() || "?";
  return (
    <span style={{
      display: "inline-block",
      background: color + "22",
      color,
      border: `1px solid ${color}55`,
      borderRadius: 2,
      fontSize: 9,
      letterSpacing: "0.12em",
      padding: "2px 7px",
      fontFamily: "'Share Tech Mono', monospace",
      fontWeight: 700,
    }}>
      {label}
    </span>
  );
}

// ── Violation row ─────────────────────────────────────────────────────────────
function ViolationRow({ v, isNew }) {
  const color = VIOLATION_COLOR[v.violation_type] || COLORS.muted;
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "90px 1fr 80px 90px",
      gap: 12,
      padding: "10px 14px",
      borderBottom: `1px solid ${COLORS.border}`,
      borderLeft: `3px solid ${isNew ? color : "transparent"}`,
      background: isNew ? color + "08" : "transparent",
      alignItems: "center",
      transition: "background 1s ease, border-left-color 1s ease",
      fontSize: 12,
    }}>
      <VBadge type={v.violation_type} />
      <div style={{ color: COLORS.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        <span style={{ color: COLORS.textDim, fontFamily: "'Share Tech Mono', monospace", marginRight: 8, fontSize: 11 }}>
          {v.camera_id || v.camera_name}
        </span>
        {v.object_type}
        {v.speed_kmh != null && (
          <span style={{ color: COLORS.orange, marginLeft: 8, fontFamily: "'Share Tech Mono', monospace" }}>
            {v.speed_kmh} km/h
          </span>
        )}
      </div>
      <div style={{ color: COLORS.textDim, fontSize: 11, fontFamily: "'Share Tech Mono', monospace" }}>
        {v.track_id != null ? `#${v.track_id}` : ""}
      </div>
      <div style={{ color: COLORS.textDim, fontSize: 10, textAlign: "right", fontFamily: "'Share Tech Mono', monospace" }}>
        {v.timestamp ? new Date(v.timestamp).toLocaleTimeString() : "live"}
      </div>
    </div>
  );
}

// ── Live pulse dot ────────────────────────────────────────────────────────────
function PulseDot({ active }) {
  return (
    <span style={{ position: "relative", display: "inline-block", width: 8, height: 8, marginRight: 8 }}>
      <span style={{
        display: "block", width: 8, height: 8, borderRadius: "50%",
        background: active ? COLORS.accent : COLORS.muted,
      }} />
      {active && (
        <span style={{
          position: "absolute", top: 0, left: 0,
          width: 8, height: 8, borderRadius: "50%",
          background: COLORS.accent,
          animation: "ping 1.2s cubic-bezier(0,0,0.2,1) infinite",
        }} />
      )}
    </span>
  );
}

// ── Main App ──────────────────────────────────────────────────────────────────
export default function App() {
  const [stats, setStats]           = useState(null);
  const [violations, setViolations] = useState([]);
  const [liveAlerts, setLiveAlerts] = useState([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [newIds, setNewIds]         = useState(new Set());
  const newIdsRef                   = useRef(new Set());

  // ── Load stats ─────────────────────────────────────────────────────────────
  const loadStats = useCallback(async () => {
    try {
      const data = await fetchStats();
      setStats(data);
    } catch {}
  }, []);

  // ── Load violations from DB ────────────────────────────────────────────────
  const loadViolations = useCallback(async () => {
    try {
      const data = await fetchViolations(30);
      setViolations(Array.isArray(data) ? data : (data.violations || []));
    } catch {}
  }, []);

  // ── Bootstrap ──────────────────────────────────────────────────────────────
  useEffect(() => {
    loadStats();
    loadViolations();
    const statsTimer = setInterval(loadStats, 10000);
    const violTimer  = setInterval(loadViolations, 5000);

    connectWS();
    const unsub = subscribeWS((msg) => {
      setWsConnected(true);
      setLiveAlerts(prev => [{ ...msg, _id: Date.now() }, ...prev].slice(0, 50));

      // Flash new row highlight for 3s
      const id = msg.track_id ?? msg._id ?? Date.now();
      newIdsRef.current.add(id);
      setNewIds(new Set(newIdsRef.current));
      setTimeout(() => {
        newIdsRef.current.delete(id);
        setNewIds(new Set(newIdsRef.current));
      }, 3000);

      // Also refresh violations list on new event
      loadViolations();
      loadStats();
    });

    return () => {
      clearInterval(statsTimer);
      clearInterval(violTimer);
      unsub();
    };
  }, [loadStats, loadViolations]);

  // ── Hourly chart data ──────────────────────────────────────────────────────
  const hourlyBars = stats?.hourly_series
    ? Object.entries(stats.hourly_series)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([h, v]) => ({ label: h, value: (v.humans || 0) + (v.vehicles || 0) }))
    : [];

  // ── Violation type breakdown ───────────────────────────────────────────────
  const violBreakdown = violations.reduce((acc, v) => {
    acc[v.violation_type] = (acc[v.violation_type] || 0) + 1;
    return acc;
  }, {});

  return (
    <div style={{
      minHeight: "100vh",
      background: COLORS.bg,
      color: COLORS.text,
      fontFamily: "'DM Sans', 'Segoe UI', sans-serif",
      fontSize: 13,
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=DM+Sans:wght@300;400;500;600&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: ${COLORS.bg}; }
        ::-webkit-scrollbar-thumb { background: ${COLORS.border}; border-radius: 2px; }
        @keyframes ping {
          75%, 100% { transform: scale(2); opacity: 0; }
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-4px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div style={{
        borderBottom: `1px solid ${COLORS.border}`,
        padding: "0 28px",
        height: 52,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        position: "sticky",
        top: 0,
        background: COLORS.bg,
        zIndex: 100,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{
            width: 28, height: 28,
            background: COLORS.accent,
            borderRadius: 2,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill={COLORS.bg}>
              <circle cx="8" cy="8" r="3" />
              <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41" stroke={COLORS.bg} strokeWidth="1.5" fill="none"/>
            </svg>
          </div>
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 13, letterSpacing: "0.1em", color: COLORS.text }}>
            SURVEILLANCE / DASHBOARD
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div style={{ display: "flex", alignItems: "center", fontSize: 11, color: wsConnected ? COLORS.accent : COLORS.muted }}>
            <PulseDot active={wsConnected} />
            {wsConnected ? "LIVE" : "CONNECTING"}
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: COLORS.textDim }}>
            {new Date().toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }).toUpperCase()}
          </div>
        </div>
      </div>

      <div style={{ padding: "24px 28px", maxWidth: 1400, margin: "0 auto" }}>

        {/* ── Stats row ─────────────────────────────────────────────────── */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10, marginBottom: 24 }}>
          <StatCard label="Entries Today"    value={stats?.entries}             accent={COLORS.accent} />
          <StatCard label="Exits Today"      value={stats?.exits}               accent={COLORS.textDim} />
          <StatCard label="Vehicles"         value={stats?.vehicles}            accent={COLORS.blue} />
          <StatCard label="People"           value={stats?.humans}              accent={COLORS.text} />
          <StatCard label="PPE Violations"   value={stats?.helmet_violations}   accent={COLORS.red} />
          <StatCard label="Speed Violations" value={stats?.speed_violations ?? (violBreakdown.speed_violation || 0)} accent={COLORS.orange} />
          <StatCard label="Zone Intrusions"  value={stats?.restricted_violations ?? (violBreakdown.intrusion || 0)} accent={COLORS.blue} />
          <StatCard label="Night Alerts"     value={stats?.night_alerts}        accent={COLORS.muted} />
        </div>

        {/* ── Main grid ─────────────────────────────────────────────────── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 16 }}>

          {/* ── LEFT: Violations table ──────────────────────────────────── */}
          <div>
            <div style={{
              background: COLORS.surface,
              border: `1px solid ${COLORS.border}`,
              borderRadius: 4,
              overflow: "hidden",
            }}>
              {/* Table header */}
              <div style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "12px 14px",
                borderBottom: `1px solid ${COLORS.border}`,
              }}>
                <span style={{ fontSize: 10, letterSpacing: "0.15em", textTransform: "uppercase", color: COLORS.textDim }}>
                  Violation Log
                </span>
                <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: COLORS.accent }}>
                  {violations.length} records
                </span>
              </div>

              {/* Column headers */}
              <div style={{
                display: "grid",
                gridTemplateColumns: "90px 1fr 80px 90px",
                gap: 12,
                padding: "6px 14px",
                borderBottom: `1px solid ${COLORS.border}`,
              }}>
                {["Type", "Camera / Object", "Track", "Time"].map(h => (
                  <div key={h} style={{ fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase", color: COLORS.muted }}>
                    {h}
                  </div>
                ))}
              </div>

              {/* Rows */}
              <div style={{ maxHeight: 480, overflowY: "auto" }}>
                {violations.length === 0 ? (
                  <div style={{ padding: 32, textAlign: "center", color: COLORS.muted, fontSize: 12 }}>
                    No violations recorded yet
                  </div>
                ) : (
                  violations.map((v, i) => (
                    <ViolationRow
                      key={v.id ?? i}
                      v={v}
                      isNew={newIds.has(v.track_id)}
                    />
                  ))
                )}
              </div>
            </div>

            {/* ── Hourly activity chart ──────────────────────────────────── */}
            <div style={{
              background: COLORS.surface,
              border: `1px solid ${COLORS.border}`,
              borderRadius: 4,
              padding: "16px 18px",
              marginTop: 16,
            }}>
              <div style={{ fontSize: 10, letterSpacing: "0.15em", textTransform: "uppercase", color: COLORS.textDim, marginBottom: 14 }}>
                Hourly Activity — Today
              </div>
              {hourlyBars.length > 0 ? (
                <>
                  <MiniBarChart data={hourlyBars} color={COLORS.accent} />
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
                    {hourlyBars.filter((_, i) => i % 3 === 0).map(d => (
                      <span key={d.label} style={{ fontSize: 9, color: COLORS.muted, fontFamily: "'Share Tech Mono', monospace" }}>
                        {d.label}h
                      </span>
                    ))}
                  </div>
                </>
              ) : (
                <div style={{ color: COLORS.muted, fontSize: 12, textAlign: "center", padding: "16px 0" }}>
                  No activity data yet
                </div>
              )}
            </div>
          </div>

          {/* ── RIGHT: Live feed ────────────────────────────────────────── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

            {/* Violation breakdown */}
            <div style={{
              background: COLORS.surface,
              border: `1px solid ${COLORS.border}`,
              borderRadius: 4,
              padding: "16px 18px",
            }}>
              <div style={{ fontSize: 10, letterSpacing: "0.15em", textTransform: "uppercase", color: COLORS.textDim, marginBottom: 14 }}>
                Violation Breakdown
              </div>
              {Object.entries(VIOLATION_COLOR).map(([type, color]) => {
                const count = violBreakdown[type] || 0;
                const total = violations.length || 1;
                const pct   = Math.round((count / total) * 100);
                return (
                  <div key={type} style={{ marginBottom: 12 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontSize: 11, color: COLORS.textDim }}>{VIOLATION_LABEL[type]}</span>
                      <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color }}>{count}</span>
                    </div>
                    <div style={{ height: 3, background: COLORS.border, borderRadius: 2 }}>
                      <div style={{ height: 3, width: `${pct}%`, background: color, borderRadius: 2, transition: "width 0.6s ease" }} />
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Live event stream */}
            <div style={{
              background: COLORS.surface,
              border: `1px solid ${COLORS.border}`,
              borderRadius: 4,
              overflow: "hidden",
              flex: 1,
            }}>
              <div style={{
                padding: "12px 14px",
                borderBottom: `1px solid ${COLORS.border}`,
                display: "flex", alignItems: "center", justifyContent: "space-between",
              }}>
                <span style={{ fontSize: 10, letterSpacing: "0.15em", textTransform: "uppercase", color: COLORS.textDim }}>
                  Live Events
                </span>
                <div style={{ display: "flex", alignItems: "center", fontSize: 10, color: COLORS.accent }}>
                  <PulseDot active={wsConnected} />
                  {liveAlerts.length}
                </div>
              </div>
              <div style={{ maxHeight: 380, overflowY: "auto" }}>
                {liveAlerts.length === 0 ? (
                  <div style={{ padding: 24, textAlign: "center", color: COLORS.muted, fontSize: 12 }}>
                    Waiting for events…
                  </div>
                ) : (
                  liveAlerts.map((a, i) => (
                    <div key={a._id ?? i} style={{
                      padding: "9px 14px",
                      borderBottom: `1px solid ${COLORS.border}`,
                      display: "flex", alignItems: "center", justifyContent: "space-between",
                      animation: i === 0 ? "fadeIn 0.3s ease" : "none",
                    }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <VBadge type={a.type?.toLowerCase().replace(" ", "_")} />
                        <span style={{ color: COLORS.textDim, fontSize: 11, fontFamily: "'Share Tech Mono', monospace" }}>
                          {a.camera_id}
                        </span>
                      </div>
                      <span style={{ fontSize: 10, color: COLORS.muted, fontFamily: "'Share Tech Mono', monospace" }}>
                        {new Date().toLocaleTimeString()}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}