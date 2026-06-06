import { useState, useEffect, useCallback } from "react";
import { api } from "../api";
import { C, MONO } from "../theme";
import { Card, CardHeader, Spinner } from "../components/UI";

function Gauge({ value, max, color, label }) {
  const pct = Math.min(100, Math.round((value / Math.max(max, 1)) * 100));
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display:"flex", justifyContent:"space-between", marginBottom:4 }}>
        <span style={{ fontSize:11, color:C.textDim }}>{label}</span>
        <span style={{ fontFamily:MONO, fontSize:11, color }}>{value}/{max}</span>
      </div>
      <div style={{ height:4, background:C.border, borderRadius:2 }}>
        <div style={{ height:4, width:`${pct}%`, background:color, borderRadius:2, transition:"width 0.5s ease" }} />
      </div>
    </div>
  );
}

function ThreadPill({ name, alive }) {
  return (
    <div style={{ display:"flex", alignItems:"center", gap:8, padding:"6px 10px", background:C.surface2, borderRadius:3, marginBottom:6 }}>
      <span style={{ width:6, height:6, borderRadius:"50%", background:alive?C.green:C.red, display:"inline-block", flexShrink:0 }} />
      <span style={{ fontFamily:MONO, fontSize:11, color:alive?C.text:C.red, flex:1 }}>{name}</span>
      <span style={{ fontSize:9, color:alive?C.green:C.red, letterSpacing:"0.1em" }}>{alive?"ALIVE":"DEAD"}</span>
    </div>
  );
}

export default function Health() {
  const [health,   setHealth]   = useState(null);
  const [loading,  setLoading]  = useState(true);
  const [lastRefresh, setLastRefresh] = useState(null);

  const load = useCallback(async () => {
    try {
      const d = await api.health();
      setHealth(d);
      setLastRefresh(new Date());
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [load]);

  if (loading) return <Spinner />;
  if (!health)  return <div style={{color:C.muted,padding:40,textAlign:"center"}}>Health endpoint unavailable</div>;

  const overall = health.overall_healthy;
  const inf = health.inference || {};
  const pipelines = health.pipelines || {};

  return (
    <div>
      {/* Top status bar */}
      <div style={{ display:"flex", alignItems:"center", gap:16, marginBottom:24, padding:"14px 18px", background:C.surface, border:`1px solid ${C.border}`, borderRadius:4, borderLeft:`3px solid ${overall?C.green:C.red}` }}>
        <span style={{ width:10, height:10, borderRadius:"50%", background:overall?C.green:C.red, display:"inline-block" }} />
        <span style={{ fontFamily:MONO, fontSize:13, color:overall?C.green:C.red }}>{overall?"SYSTEM HEALTHY":"DEGRADED — CHECK PIPELINE"}</span>
        <span style={{ marginLeft:"auto", fontFamily:MONO, fontSize:10, color:C.muted }}>
          {lastRefresh ? `Updated ${lastRefresh.toLocaleTimeString()}` : ""}
        </span>
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>
        {/* Inference worker */}
        <Card>
          <CardHeader title="Inference Worker" />
          <div style={{ padding:"14px 16px" }}>
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:10, marginBottom:16 }}>
              {[
                ["FPS",     `${inf.fps??0}`,    C.accent],
                ["Queue",   `${inf.queue??0}`,  inf.queue>2?C.orange:C.green],
                ["Dropped", `${inf.dropped??0}`,inf.dropped>0?C.orange:C.green],
              ].map(([label,val,color])=>(
                <div key={label} style={{ background:C.surface2, padding:"10px 12px", borderRadius:3 }}>
                  <div style={{ fontSize:9, color:C.muted, letterSpacing:"0.12em", textTransform:"uppercase", marginBottom:6 }}>{label}</div>
                  <div style={{ fontFamily:MONO, fontSize:20, color }}>{val}</div>
                </div>
              ))}
            </div>
            <Gauge value={inf.queue??0} max={4}  color={inf.queue>2?C.orange:C.green} label="Input Queue" />
          </div>
        </Card>

        {/* Per-camera pipelines */}
        {Object.entries(pipelines).map(([camId, p]) => (
          <Card key={camId}>
            <CardHeader title={`Pipeline — ${camId}`} right={
              <span style={{ color: p.threads_alive ? C.green : C.red, fontFamily:MONO, fontSize:10 }}>
                {p.threads_alive ? "● RUNNING" : "● DEAD"}
              </span>
            } />
            <div style={{ padding:"14px 16px" }}>
              {/* Queue gauges */}
              <div style={{ marginBottom:14 }}>
                <Gauge value={p.tracking_queue??0}  max={2}  color={C.blue}   label="Tracking Queue" />
                <Gauge value={p.analytics_queue??0} max={2}  color={C.accent} label="Analytics Queue" />
                <Gauge value={p.db_queue??0}         max={50} color={p.db_queue>40?C.red:C.green} label="DB Queue" />
                <Gauge value={p.visual_queue??0}     max={1}  color={C.textDim} label="Visual Queue" />
              </div>
              {/* Thread pills */}
              <div style={{ fontSize:9, color:C.muted, letterSpacing:"0.12em", textTransform:"uppercase", marginBottom:8 }}>Threads</div>
              {(p.dead_threads?.length > 0 || p.threads_alive === false) && (
                <div style={{ background:"rgba(255,68,68,0.1)", border:`1px solid ${C.red}33`, borderRadius:3, padding:"8px 10px", marginBottom:10, fontSize:11, color:C.red, fontFamily:MONO }}>
                  Dead: {p.dead_threads?.join(", ") || "unknown"}
                </div>
              )}
              {p.dead_threads !== undefined && (
                ["reader","tracker","analytics","saver"].map(name => {
                  const fullName = `${name}-${camId}`;
                  const alive = !p.dead_threads?.includes(fullName);
                  return <ThreadPill key={fullName} name={fullName} alive={alive} />;
                })
              )}
            </div>
          </Card>
        ))}

        {/* DB metrics */}
        <Card>
          <CardHeader title="Database" />
          <div style={{ padding:"14px 16px" }}>
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:10 }}>
              {[
                ["Status", "Connected", C.green],
                ["Pool",   "5 – 50 conn", C.textDim],
              ].map(([label,val,color])=>(
                <div key={label} style={{ background:C.surface2, padding:"10px 12px", borderRadius:3 }}>
                  <div style={{ fontSize:9, color:C.muted, letterSpacing:"0.12em", textTransform:"uppercase", marginBottom:6 }}>{label}</div>
                  <div style={{ fontFamily:MONO, fontSize:12, color }}>{val}</div>
                </div>
              ))}
            </div>
          </div>
        </Card>

        {/* Redis */}
        <Card>
          <CardHeader title="Redis / WebSocket" />
          <div style={{ padding:"14px 16px" }}>
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:10 }}>
              {[
                ["Redis",     "localhost:6379", C.textDim],
                ["Channel",   "events",         C.textDim],
              ].map(([label,val,color])=>(
                <div key={label} style={{ background:C.surface2, padding:"10px 12px", borderRadius:3 }}>
                  <div style={{ fontSize:9, color:C.muted, letterSpacing:"0.12em", textTransform:"uppercase", marginBottom:6 }}>{label}</div>
                  <div style={{ fontFamily:MONO, fontSize:12, color }}>{val}</div>
                </div>
              ))}
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}