import { useState, useEffect, useCallback } from "react";
import { api } from "../api";
import { C, VCOLOR, VLABEL, MONO, snapshotUrl } from "../theme";
import { VBadge, Card, CardHeader, Spinner, SnapshotModal } from "../components/UI";

const INPUT = { background:C.surface2, border:`1px solid ${C.border}`, borderRadius:3, color:C.text, padding:"6px 10px", fontSize:12, fontFamily:MONO, outline:"none", width:"100%" };
const BTN   = (accent) => ({ background:accent?"rgba(232,255,71,0.12)":"transparent", border:`1px solid ${accent?C.accent:C.border}`, color:accent?C.accent:C.textDim, borderRadius:3, padding:"6px 14px", fontSize:11, fontFamily:MONO, letterSpacing:"0.08em", cursor:"pointer" });

export default function Violations() {
  const [violations, setViolations] = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [selected,   setSelected]   = useState(null);
  const [filters, setFilters] = useState({ camera_id:"", violation_type:"", limit:50, offset:0 });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filters.camera_id)     params.camera_id     = filters.camera_id;
      if (filters.violation_type) params.violation_type = filters.violation_type;
      params.limit  = filters.limit;
      params.offset = filters.offset;
      const d = await api.violations(params);
      setViolations(Array.isArray(d) ? d : d.violations || []);
    } catch {}
    setLoading(false);
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  function exportCSV() {
    const cols = ["id","timestamp","camera_id","track_id","violation_type","object_type","speed_kmh","zone_id"];
    const rows = [cols.join(","), ...violations.map(v => cols.map(c => JSON.stringify(v[c]??"",-1)).join(","))];
    const blob = new Blob([rows.join("\n")], { type:"text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `violations_${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
  }

  const TYPES = ["","speed_violation","ppe_violation","intrusion"];

  return (
    <div>
      {/* Filters */}
      <Card style={{ marginBottom:16, padding:"14px 18px" }}>
        <div style={{ display:"grid", gridTemplateColumns:"1fr 160px 80px 80px auto auto", gap:10, alignItems:"end" }}>
          <div>
            <div style={{fontSize:9,color:C.muted,letterSpacing:"0.12em",textTransform:"uppercase",marginBottom:5}}>Camera ID</div>
            <input style={INPUT} placeholder="gate_1" value={filters.camera_id} onChange={e=>setFilters(f=>({...f,camera_id:e.target.value,offset:0}))} />
          </div>
          <div>
            <div style={{fontSize:9,color:C.muted,letterSpacing:"0.12em",textTransform:"uppercase",marginBottom:5}}>Type</div>
            <select style={{...INPUT}} value={filters.violation_type} onChange={e=>setFilters(f=>({...f,violation_type:e.target.value,offset:0}))}>
              {TYPES.map(t=><option key={t} value={t}>{t||"All types"}</option>)}
            </select>
          </div>
          <div>
            <div style={{fontSize:9,color:C.muted,letterSpacing:"0.12em",textTransform:"uppercase",marginBottom:5}}>Limit</div>
            <select style={{...INPUT}} value={filters.limit} onChange={e=>setFilters(f=>({...f,limit:+e.target.value,offset:0}))}>
              {[20,50,100,200].map(n=><option key={n}>{n}</option>)}
            </select>
          </div>
          <div style={{alignSelf:"flex-end"}}>
            <button style={BTN(true)} onClick={load}>Filter</button>
          </div>
          <div style={{alignSelf:"flex-end"}}>
            <button style={BTN(false)} onClick={()=>setFilters({camera_id:"",violation_type:"",limit:50,offset:0})}>Reset</button>
          </div>
          <div style={{alignSelf:"flex-end"}}>
            <button style={BTN(false)} onClick={exportCSV}>↓ CSV</button>
          </div>
        </div>
      </Card>

      {/* Table */}
      <Card>
        <CardHeader title="Violations" right={`${violations.length} records`} />
        <div style={{ display:"grid", gridTemplateColumns:"80px 100px 1fr 80px 90px 80px 32px", gap:10, padding:"6px 16px", borderBottom:`1px solid ${C.border}` }}>
          {["Type","Camera","Object","Track","Speed","Time",""].map(h=>(
            <div key={h} style={{fontSize:9,letterSpacing:"0.12em",textTransform:"uppercase",color:C.muted}}>{h}</div>
          ))}
        </div>
        <div style={{maxHeight:"calc(100vh - 280px)", overflowY:"auto"}}>
          {loading
            ? <Spinner />
            : violations.length===0
            ? <div style={{padding:40,textAlign:"center",color:C.muted}}>No violations match the current filters</div>
            : violations.map((v,i)=>(
              <div key={v.id??i} onClick={()=>setSelected(v)} style={{ display:"grid", gridTemplateColumns:"80px 100px 1fr 80px 90px 80px 32px", gap:10, padding:"10px 16px", borderBottom:`1px solid ${C.border}`, alignItems:"center", fontSize:12, cursor:"pointer", transition:"background 0.15s" }}
                onMouseEnter={e=>e.currentTarget.style.background=C.surface2}
                onMouseLeave={e=>e.currentTarget.style.background="transparent"}>
                <VBadge type={v.violation_type} />
                <span style={{fontFamily:MONO,fontSize:11,color:C.textDim}}>{v.camera_id}</span>
                <span style={{overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{v.object_type}</span>
                <span style={{fontFamily:MONO,fontSize:11,color:C.textDim}}>{v.track_id!=null?`#${v.track_id}`:""}</span>
                <span style={{fontFamily:MONO,fontSize:11,color:v.speed_kmh>60?C.orange:C.textDim}}>{v.speed_kmh!=null?`${v.speed_kmh} km/h`:"—"}</span>
                <span style={{fontFamily:MONO,fontSize:10,color:C.textDim}}>{v.timestamp?new Date(v.timestamp).toLocaleTimeString():""}</span>
                <span style={{fontSize:12,color:v.image_path?C.accent:C.muted,textAlign:"center"}}>{v.image_path?"⊙":"·"}</span>
              </div>
            ))
          }
        </div>

        {/* Pagination */}
        <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",padding:"10px 16px",borderTop:`1px solid ${C.border}`}}>
          <span style={{fontFamily:MONO,fontSize:11,color:C.textDim}}>offset: {filters.offset}</span>
          <div style={{display:"flex",gap:8}}>
            <button style={BTN(false)} disabled={filters.offset===0} onClick={()=>setFilters(f=>({...f,offset:Math.max(0,f.offset-f.limit)}))}>← Prev</button>
            <button style={BTN(false)} disabled={violations.length<filters.limit} onClick={()=>setFilters(f=>({...f,offset:f.offset+f.limit}))}>Next →</button>
          </div>
        </div>
      </Card>

      <SnapshotModal v={selected} onClose={()=>setSelected(null)} />
    </div>
  );
}