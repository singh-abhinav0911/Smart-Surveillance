import { C, VCOLOR, VLABEL, MONO, snapshotUrl } from "../theme";

export function PulseDot({ active }) {
  return (
    <span style={{ position:"relative", display:"inline-block", width:8, height:8, marginRight:7 }}>
      <span style={{ display:"block", width:8, height:8, borderRadius:"50%", background: active ? C.accent : C.muted }} />
      {active && <span style={{ position:"absolute", top:0, left:0, width:8, height:8, borderRadius:"50%", background:C.accent, animation:"ping 1.2s cubic-bezier(0,0,0.2,1) infinite" }} />}
    </span>
  );
}

export function VBadge({ type }) {
  const color = VCOLOR[type] || C.muted;
  return (
    <span style={{ display:"inline-block", background:color+"22", color, border:`1px solid ${color}55`, borderRadius:2, fontSize:9, letterSpacing:"0.12em", padding:"2px 7px", fontFamily:MONO, fontWeight:700 }}>
      {VLABEL[type] || (type||"?").toUpperCase()}
    </span>
  );
}

export function StatCard({ label, value, accent, sub }) {
  return (
    <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderTop:`2px solid ${accent||C.border}`, padding:"16px 18px", borderRadius:4 }}>
      <div style={{ color:C.textDim, fontSize:10, letterSpacing:"0.15em", textTransform:"uppercase", marginBottom:8 }}>{label}</div>
      <div style={{ color:accent||C.text, fontSize:30, fontFamily:MONO, lineHeight:1 }}>{value ?? "—"}</div>
      {sub && <div style={{ color:C.textDim, fontSize:11, marginTop:6 }}>{sub}</div>}
    </div>
  );
}

export function Card({ children, style={} }) {
  return (
    <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:4, overflow:"hidden", ...style }}>
      {children}
    </div>
  );
}

export function CardHeader({ title, right }) {
  return (
    <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"12px 16px", borderBottom:`1px solid ${C.border}` }}>
      <span style={{ fontSize:10, letterSpacing:"0.15em", textTransform:"uppercase", color:C.textDim }}>{title}</span>
      {right && <span style={{ fontFamily:MONO, fontSize:11, color:C.accent }}>{right}</span>}
    </div>
  );
}

export function Spinner() {
  return <div style={{ width:20, height:20, border:`2px solid ${C.border}`, borderTop:`2px solid ${C.accent}`, borderRadius:"50%", animation:"spin 0.8s linear infinite", margin:"32px auto" }} />;
}

export function SnapshotModal({ v, onClose }) {
  if (!v) return null;
  const imgUrl = snapshotUrl(v.image_path);
  const meta = (() => { try { return typeof v.metadata === "string" ? JSON.parse(v.metadata) : v.metadata || {}; } catch { return {}; } })();
  return (
    <div onClick={onClose} style={{ position:"fixed", inset:0, background:"rgba(0,0,0,0.88)", zIndex:1000, display:"flex", alignItems:"center", justifyContent:"center", backdropFilter:"blur(4px)" }}>
      <div onClick={e=>e.stopPropagation()} style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:6, width:640, maxWidth:"95vw", overflow:"hidden", boxShadow:"0 24px 80px rgba(0,0,0,0.6)" }}>
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"14px 18px", borderBottom:`1px solid ${C.border}` }}>
          <div style={{ display:"flex", alignItems:"center", gap:10 }}>
            <VBadge type={v.violation_type} />
            <span style={{ fontFamily:MONO, fontSize:11, color:C.textDim }}>{v.camera_id} · #{v.track_id}</span>
          </div>
          <button onClick={onClose} style={{ background:"none", border:"none", color:C.muted, cursor:"pointer", fontSize:20, lineHeight:1 }}>×</button>
        </div>
        {imgUrl
          ? <div style={{ background:"#000", maxHeight:360, overflow:"hidden" }}><img src={imgUrl} alt="" style={{ width:"100%", display:"block", objectFit:"contain", maxHeight:360 }} onError={e=>{e.target.style.display="none"}} /></div>
          : <div style={{ height:100, display:"flex", alignItems:"center", justifyContent:"center", color:C.muted, fontSize:12 }}>No snapshot</div>
        }
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"1px", background:C.border }}>
          {[
            ["Time",     v.timestamp ? new Date(v.timestamp).toLocaleString() : "—"],
            ["Camera",   v.camera_id],
            ["Type",     VLABEL[v.violation_type] || v.violation_type],
            ["Object",   v.object_type],
            ["Track",    v.track_id != null ? `#${v.track_id}` : "—"],
            ["Speed",    v.speed_kmh != null ? `${v.speed_kmh} km/h` : "—"],
            ["Zone",     v.zone_id || "—"],
            ["Detail",   meta.violation || (meta.limit ? `limit ${meta.limit}` : "—")],
          ].map(([k,val]) => (
            <div key={k} style={{ background:C.surface, padding:"10px 16px" }}>
              <div style={{ fontSize:9, letterSpacing:"0.12em", textTransform:"uppercase", color:C.muted, marginBottom:4 }}>{k}</div>
              <div style={{ fontFamily:MONO, fontSize:12, color:C.text }}>{val}</div>
            </div>
          ))}
        </div>
        {imgUrl && (
          <div style={{ padding:"10px 16px", borderTop:`1px solid ${C.border}`, display:"flex", justifyContent:"flex-end" }}>
            <a href={imgUrl} download style={{ fontFamily:MONO, fontSize:11, color:C.accent, padding:"6px 14px", border:`1px solid ${C.accent}`, borderRadius:3 }}>
              ↓ Download
            </a>
          </div>
        )}
      </div>
    </div>
  );
}