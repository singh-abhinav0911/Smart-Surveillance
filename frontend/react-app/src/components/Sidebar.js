import { NavLink } from "react-router-dom";
import { C, MONO } from "../theme";

const NAV = [
  { to: "/",          icon: "⊡", label: "Dashboard"  },
  { to: "/violations",icon: "⚠", label: "Violations" },
  { to: "/cameras",   icon: "◉", label: "Cameras"    },
  { to: "/health",    icon: "♡", label: "Health"     },
];

export default function Sidebar({ wsConnected }) {
  return (
    <div style={{
      width: 200, minHeight: "100vh", background: C.surface,
      borderRight: `1px solid ${C.border}`,
      display: "flex", flexDirection: "column",
      position: "fixed", left: 0, top: 0, bottom: 0, zIndex: 200,
    }}>
      {/* Logo */}
      <div style={{ padding: "20px 16px", borderBottom: `1px solid ${C.border}` }}>
        <div style={{ display:"flex", alignItems:"center", gap:10 }}>
          <div style={{ width:28, height:28, background:C.accent, borderRadius:2, display:"flex", alignItems:"center", justifyContent:"center", fontSize:14, color:C.bg, fontWeight:700 }}>⊙</div>
          <div>
            <div style={{ fontFamily:MONO, fontSize:11, color:C.text, letterSpacing:"0.08em" }}>SENTINEL</div>
            <div style={{ fontSize:9, color:C.muted, letterSpacing:"0.1em" }}>SURVEILLANCE</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex:1, padding:"12px 8px" }}>
        {NAV.map(({ to, icon, label }) => (
          <NavLink key={to} to={to} end={to==="/"} style={({ isActive }) => ({
            display: "flex", alignItems: "center", gap: 10,
            padding: "9px 10px", borderRadius: 4, marginBottom: 2,
            background: isActive ? C.accent + "18" : "transparent",
            color: isActive ? C.accent : C.textDim,
            fontSize: 12, fontFamily: MONO, letterSpacing: "0.06em",
            borderLeft: isActive ? `2px solid ${C.accent}` : "2px solid transparent",
            transition: "all 0.15s",
          })}>
            <span style={{ fontSize:14 }}>{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Status */}
      <div style={{ padding:"12px 16px", borderTop:`1px solid ${C.border}` }}>
        <div style={{ display:"flex", alignItems:"center", fontSize:10, color: wsConnected ? C.accent : C.muted, fontFamily:MONO }}>
          <span style={{ width:6, height:6, borderRadius:"50%", background: wsConnected ? C.accent : C.muted, display:"inline-block", marginRight:8 }} />
          {wsConnected ? "LIVE" : "OFFLINE"}
        </div>
      </div>
    </div>
  );
}