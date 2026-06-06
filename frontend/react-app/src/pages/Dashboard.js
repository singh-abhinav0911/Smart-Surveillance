import { useEffect, useState, useCallback } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { api } from "../api";
import { subscribeWS } from "../ws";
import { C, VCOLOR, VLABEL, MONO, BASE, snapshotUrl } from "../theme";
import { StatCard, Card, CardHeader, VBadge, SnapshotModal, PulseDot } from "../components/UI";

export default function Dashboard({ wsConnected }) {
  const [stats, setStats]           = useState(null);
  const [violations, setViolations] = useState([]);
  const [liveAlerts, setLiveAlerts] = useState([]);
  const [selected, setSelected]     = useState(null);
  const [tab, setTab]               = useState("feed");

  const loadStats = useCallback(async () => { try { setStats(await api.stats()); } catch {} }, []);
  const loadV     = useCallback(async () => {
    try {
      const d = await api.violations({ limit: 20 });
      setViolations(Array.isArray(d) ? d : d.violations || []);
    } catch {}
  }, []);

  useEffect(() => {
    loadStats(); loadV();
    const t1 = setInterval(loadStats, 10000);
    const t2 = setInterval(loadV, 5000);
    const unsub = subscribeWS((msg) => {
      setLiveAlerts(p => [{ ...msg, _id: Date.now() }, ...p].slice(0, 30));
      loadV(); loadStats();
    });
    return () => { clearInterval(t1); clearInterval(t2); unsub(); };
  }, [loadStats, loadV]);

  const hourly = stats?.hourly_series
    ? Object.entries(stats.hourly_series).sort().map(([h, v]) => ({ h, total: (v.humans||0)+(v.vehicles||0), humans: v.humans||0, vehicles: v.vehicles||0 }))
    : [];

  const violBreak = violations.reduce((a, v) => { a[v.violation_type] = (a[v.violation_type]||0)+1; return a; }, {});

  return (
    <div>
      <style>{`
        .tabBtn { cursor:pointer; padding:6px 14px; border-radius:3px; font-size:10px; letter-spacing:0.1em; text-transform:uppercase; transition:all 0.2s; font-family:${MONO}; }
        .vrow:hover { background:${C.surface2} !important; cursor:pointer; }
      `}</style>

      {/* Stats */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fit,minmax(140px,1fr))", gap:10, marginBottom:24 }}>
        <StatCard label="Entries Today"    value={stats?.entries}              accent={C.accent} />
        <StatCard label="Exits Today"      value={stats?.exits}                accent={C.textDim} />
        <StatCard label="Vehicles"         value={stats?.vehicles}             accent={C.blue} />
        <StatCard label="People"           value={stats?.humans}               accent={C.text} />
        <StatCard label="PPE Violations"   value={stats?.helmet_violations ?? (violBreak.ppe_violation||0)} accent={C.red} />
        <StatCard label="Speed"            value={stats?.speed_violations    ?? (violBreak.speed_violation||0)} accent={C.orange} />
        <StatCard label="Zone Intrusions"  value={stats?.restricted_violations ?? (violBreak.intrusion||0)} accent={C.blue} />
        <StatCard label="Night Alerts"     value={stats?.night_alerts}         accent={C.muted} />
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"1fr 320px", gap:16 }}>
        {/* LEFT */}
        <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
          {/* Tabs */}
          <div style={{ display:"flex", gap:6 }}>
            {[["feed","Live Feed"],["log","Violation Log"]].map(([id,label])=>(
              <button key={id} className="tabBtn" onClick={()=>setTab(id)} style={{ background:tab===id?C.accent:C.surface, color:tab===id?C.bg:C.textDim, border:`1px solid ${tab===id?C.accent:C.border}` }}>{label}</button>
            ))}
          </div>

          {tab==="feed" && (
            <Card>
              <CardHeader title="Live Camera — gate_1" right={<span style={{display:"flex",alignItems:"center"}}><PulseDot active={true}/>LIVE</span>} />
              <div style={{ background:"#000", aspectRatio:"16/9", position:"relative" }}>
                <img src={`${BASE}/stream/gate_1`} alt="feed" style={{ width:"100%", height:"100%", objectFit:"contain", display:"block" }}
                  onError={e=>{ e.target.style.display="none"; e.target.nextSibling.style.display="flex"; }} />
                <div style={{ display:"none", position:"absolute", inset:0, alignItems:"center", justifyContent:"center", color:C.muted, fontSize:12, flexDirection:"column", gap:8 }}>
                  <span style={{fontSize:28}}>⊘</span>Stream unavailable
                </div>
              </div>
              <div style={{ padding:"10px 16px", display:"flex", gap:20, borderTop:`1px solid ${C.border}` }}>
                <span style={{fontFamily:MONO,fontSize:10,color:C.textDim}}>IN: {stats?.entries??0}</span>
                <span style={{fontFamily:MONO,fontSize:10,color:C.textDim}}>OUT: {stats?.exits??0}</span>
              </div>
            </Card>
          )}

          {tab==="log" && (
            <Card>
              <CardHeader title="Recent Violations" right={`${violations.length} records`} />
              <div style={{ display:"grid", gridTemplateColumns:"80px 1fr 70px 80px", gap:10, padding:"6px 14px", borderBottom:`1px solid ${C.border}` }}>
                {["Type","Camera / Object","Track","Time"].map(h=>(
                  <div key={h} style={{fontSize:9,letterSpacing:"0.12em",textTransform:"uppercase",color:C.muted}}>{h}</div>
                ))}
              </div>
              <div style={{ maxHeight:420, overflowY:"auto" }}>
                {violations.length===0
                  ? <div style={{padding:32,textAlign:"center",color:C.muted}}>No violations yet</div>
                  : violations.map((v,i) => (
                    <div key={v.id??i} className="vrow" onClick={()=>setSelected(v)} style={{ display:"grid", gridTemplateColumns:"80px 1fr 70px 80px", gap:10, padding:"10px 14px", borderBottom:`1px solid ${C.border}`, alignItems:"center", fontSize:12 }}>
                      <VBadge type={v.violation_type} />
                      <div style={{overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>
                        <span style={{color:C.textDim,fontFamily:MONO,marginRight:8,fontSize:11}}>{v.camera_id}</span>
                        {v.object_type}
                        {v.speed_kmh!=null && <span style={{color:C.orange,marginLeft:8,fontFamily:MONO}}>{v.speed_kmh}km/h</span>}
                      </div>
                      <div style={{color:C.textDim,fontSize:11,fontFamily:MONO}}>{v.track_id!=null?`#${v.track_id}`:""}</div>
                      <div style={{color:C.textDim,fontSize:10,fontFamily:MONO}}>{v.timestamp?new Date(v.timestamp).toLocaleTimeString():""}</div>
                    </div>
                  ))
                }
              </div>
            </Card>
          )}

          {/* Hourly chart */}
          <Card style={{padding:"16px 18px"}}>
            <div style={{fontSize:10,letterSpacing:"0.15em",textTransform:"uppercase",color:C.textDim,marginBottom:14}}>Hourly Activity — Today</div>
            {hourly.length>0
              ? <ResponsiveContainer width="100%" height={80}>
                  <BarChart data={hourly} margin={{top:0,right:0,bottom:0,left:-30}}>
                    <XAxis dataKey="h" tick={{fill:C.muted,fontSize:9}} axisLine={false} tickLine={false} />
                    <YAxis tick={{fill:C.muted,fontSize:9}} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{background:C.surface2,border:`1px solid ${C.border}`,borderRadius:4,fontSize:11}} cursor={{fill:C.border}} />
                    <Bar dataKey="humans"   stackId="a" fill={C.blue}   radius={0} />
                    <Bar dataKey="vehicles" stackId="a" fill={C.accent} radius={[2,2,0,0]} />
                  </BarChart>
                </ResponsiveContainer>
              : <div style={{color:C.muted,fontSize:12,textAlign:"center",padding:"12px 0"}}>No activity data yet</div>
            }
          </Card>
        </div>

        {/* RIGHT */}
        <div style={{display:"flex",flexDirection:"column",gap:16}}>
          {/* Breakdown */}
          <Card style={{padding:"16px 18px"}}>
            <div style={{fontSize:10,letterSpacing:"0.15em",textTransform:"uppercase",color:C.textDim,marginBottom:14}}>Violation Breakdown</div>
            {Object.entries(VCOLOR).map(([type,color])=>{
              const count = violBreak[type]||0;
              const pct = Math.round((count/Math.max(violations.length,1))*100);
              return (
                <div key={type} style={{marginBottom:12}}>
                  <div style={{display:"flex",justifyContent:"space-between",marginBottom:4}}>
                    <span style={{fontSize:11,color:C.textDim}}>{VLABEL[type]}</span>
                    <span style={{fontFamily:MONO,fontSize:11,color}}>{count}</span>
                  </div>
                  <div style={{height:3,background:C.border,borderRadius:2}}>
                    <div style={{height:3,width:`${pct}%`,background:color,borderRadius:2,transition:"width 0.6s ease"}} />
                  </div>
                </div>
              );
            })}
          </Card>

          {/* Snapshots */}
          <Card>
            <CardHeader title="Recent Snapshots" />
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:1,background:C.border}}>
              {violations.filter(v=>v.image_path).slice(0,6).map((v,i)=>(
                <div key={v.id??i} onClick={()=>setSelected(v)} style={{background:C.surface,position:"relative",aspectRatio:"16/10",overflow:"hidden",cursor:"pointer"}}>
                  <img src={snapshotUrl(v.image_path)} alt="" style={{width:"100%",height:"100%",objectFit:"cover",display:"block",transition:"transform 0.2s"}}
                    onMouseEnter={e=>e.target.style.transform="scale(1.05)"}
                    onMouseLeave={e=>e.target.style.transform="scale(1)"}
                    onError={e=>e.target.parentElement.style.display="none"} />
                  <div style={{position:"absolute",bottom:0,left:0,right:0,padding:"4px 6px",background:"rgba(0,0,0,0.7)",display:"flex",alignItems:"center",justifyContent:"space-between"}}>
                    <VBadge type={v.violation_type} />
                    {v.speed_kmh!=null && <span style={{fontSize:9,color:C.orange,fontFamily:MONO}}>{v.speed_kmh}km/h</span>}
                  </div>
                </div>
              ))}
            </div>
            {violations.filter(v=>v.image_path).length===0 && <div style={{padding:20,textAlign:"center",color:C.muted,fontSize:12}}>No snapshots yet</div>}
          </Card>

          {/* Live events */}
          <Card style={{flex:1}}>
            <CardHeader title="Live Events" right={<span style={{display:"flex",alignItems:"center"}}><PulseDot active={wsConnected}/>{liveAlerts.length}</span>} />
            <div style={{maxHeight:240,overflowY:"auto"}}>
              {liveAlerts.length===0
                ? <div style={{padding:24,textAlign:"center",color:C.muted,fontSize:12}}>Waiting for events…</div>
                : liveAlerts.map((a,i)=>(
                  <div key={a._id??i} style={{padding:"9px 14px",borderBottom:`1px solid ${C.border}`,display:"flex",alignItems:"center",justifyContent:"space-between",animation:i===0?"fadeIn 0.3s ease":"none"}}>
                    <div style={{display:"flex",alignItems:"center",gap:8}}>
                      <VBadge type={a.type?.toLowerCase().replace(" ","_")} />
                      <span style={{color:C.textDim,fontSize:11,fontFamily:MONO}}>{a.camera_id}</span>
                    </div>
                    <span style={{fontSize:10,color:C.muted,fontFamily:MONO}}>{new Date().toLocaleTimeString()}</span>
                  </div>
                ))
              }
            </div>
          </Card>
        </div>
      </div>

      <SnapshotModal v={selected} onClose={()=>setSelected(null)} />
    </div>
  );
}