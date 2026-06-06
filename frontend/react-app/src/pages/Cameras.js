import { useState, useEffect } from "react";
import { api } from "../api";
import { C, MONO, BASE } from "../theme";
import { Card, CardHeader, Spinner } from "../components/UI";

const INPUT = { background:C.surface2, border:`1px solid ${C.border}`, borderRadius:3, color:C.text, padding:"7px 10px", fontSize:12, fontFamily:MONO, outline:"none", width:"100%" };
const BTN = (accent,danger) => ({ background:danger?"rgba(255,68,68,0.1)":accent?"rgba(232,255,71,0.12)":"transparent", border:`1px solid ${danger?C.red:accent?C.accent:C.border}`, color:danger?C.red:accent?C.accent:C.textDim, borderRadius:3, padding:"7px 16px", fontSize:11, fontFamily:MONO, letterSpacing:"0.08em", cursor:"pointer" });
const LABEL = { fontSize:9, color:C.muted, letterSpacing:"0.12em", textTransform:"uppercase", marginBottom:5 };

export default function Cameras() {
  const [cameras,    setCameras]    = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [showForm,   setShowForm]   = useState(false);
  const [editCam,    setEditCam]    = useState(null);
  const [testResult, setTestResult] = useState({});
  const [form, setForm] = useState({ name:"", source:"", line_y:300, location:"" });

  async function loadCameras() {
    setLoading(true);
    try {
      const d = await api.cameras();
      // Backend returns { cameras: ["gate_1", ...] }
      const names = d.cameras || [];
      setCameras(names.map(id => ({ id, source: "", active: true, line_y: 300, location: "" })));
    } catch {}
    setLoading(false);
  }

  useEffect(() => { loadCameras(); }, []);

  async function testConnection(source) {
    setTestResult(p => ({ ...p, [source]: "testing" }));
    // Simple test: try to reach the stream endpoint
    try {
      const res = await fetch(`${BASE}/stream/${source.replace("gate_","")}`);
      setTestResult(p => ({ ...p, [source]: res.ok ? "ok" : "fail" }));
    } catch {
      setTestResult(p => ({ ...p, [source]: "fail" }));
    }
    setTimeout(() => setTestResult(p => { const n={...p}; delete n[source]; return n; }), 3000);
  }

  function openAdd() { setForm({ name:"", source:"", line_y:300, location:"" }); setEditCam(null); setShowForm(true); }
  function openEdit(cam) { setForm({ name:cam.id, source:cam.source, line_y:cam.line_y, location:cam.location }); setEditCam(cam.id); setShowForm(true); }

  function saveCamera() {
    // NOTE: Saving cameras requires backend camera management API.
    // Currently this updates the .env file — show instructions to user.
    alert(`To ${editCam?"update":"add"} camera "${form.name}", update your .env file:\n\nCAMERA_SOURCES=${form.name}:${form.source}\n\nThen restart the backend.`);
    setShowForm(false);
  }

  const testBtnColor = (src) => {
    const r = testResult[src];
    if (r==="testing") return C.muted;
    if (r==="ok")      return C.green;
    if (r==="fail")    return C.red;
    return C.textDim;
  };

  return (
    <div>
      {/* Header actions */}
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:16 }}>
        <div style={{ fontFamily:MONO, fontSize:13, color:C.text, letterSpacing:"0.08em" }}>Camera Management</div>
        <button style={BTN(true)} onClick={openAdd}>+ Add Camera</button>
      </div>

      {/* Camera cards */}
      {loading
        ? <Spinner />
        : cameras.length===0
        ? (
          <Card style={{padding:40,textAlign:"center"}}>
            <div style={{color:C.muted,fontSize:12,marginBottom:16}}>No cameras configured</div>
            <div style={{fontFamily:MONO,fontSize:11,color:C.textDim,lineHeight:1.8}}>
              Add cameras via the .env file:<br/>
              CAMERA_SOURCES=gate_1:0,gate_2:rtsp://192.168.1.1/stream
            </div>
          </Card>
        )
        : (
          <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(340px,1fr))", gap:16 }}>
            {cameras.map(cam => (
              <Card key={cam.id}>
                {/* Stream preview */}
                <div style={{ background:"#000", aspectRatio:"16/9", position:"relative", overflow:"hidden" }}>
                  <img src={`${BASE}/stream/${cam.id}`} alt="" style={{ width:"100%", height:"100%", objectFit:"contain", display:"block" }}
                    onError={e=>{ e.target.style.display="none"; e.target.nextSibling.style.display="flex"; }} />
                  <div style={{ display:"none", position:"absolute", inset:0, alignItems:"center", justifyContent:"center", color:C.muted, fontSize:12, flexDirection:"column", gap:6 }}>
                    <span style={{fontSize:24}}>⊘</span>No signal
                  </div>
                  {/* Status badge */}
                  <div style={{ position:"absolute", top:8, left:8, background:"rgba(0,0,0,0.7)", padding:"3px 8px", borderRadius:2, display:"flex", alignItems:"center", gap:6 }}>
                    <span style={{ width:6, height:6, borderRadius:"50%", background:cam.active?C.green:C.muted, display:"inline-block" }} />
                    <span style={{ fontFamily:MONO, fontSize:9, color:C.text }}>{cam.active?"LIVE":"OFFLINE"}</span>
                  </div>
                </div>

                {/* Info */}
                <div style={{ padding:"12px 14px" }}>
                  <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:10 }}>
                    <div>
                      <div style={{ fontFamily:MONO, fontSize:13, color:C.text }}>{cam.id}</div>
                      {cam.location && <div style={{ fontSize:11, color:C.textDim, marginTop:2 }}>{cam.location}</div>}
                    </div>
                    <div style={{ display:"flex", gap:6 }}>
                      <button style={BTN(false)} onClick={()=>openEdit(cam)}>Edit</button>
                    </div>
                  </div>

                  <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:8, marginBottom:10 }}>
                    <div style={{ background:C.surface2, padding:"8px 10px", borderRadius:3 }}>
                      <div style={LABEL}>Source</div>
                      <div style={{ fontFamily:MONO, fontSize:11, color:C.textDim, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{cam.source||"—"}</div>
                    </div>
                    <div style={{ background:C.surface2, padding:"8px 10px", borderRadius:3 }}>
                      <div style={LABEL}>Line Y</div>
                      <div style={{ fontFamily:MONO, fontSize:11, color:C.textDim }}>{cam.line_y}px</div>
                    </div>
                  </div>

                  <button
                    style={{ ...BTN(false), width:"100%", color:testBtnColor(cam.id) }}
                    onClick={()=>testConnection(cam.id)}>
                    {testResult[cam.id]==="testing" ? "Testing…" : testResult[cam.id]==="ok" ? "✓ Connected" : testResult[cam.id]==="fail" ? "✗ Failed" : "Test Connection"}
                  </button>
                </div>
              </Card>
            ))}
          </div>
        )
      }

      {/* Add/Edit modal */}
      {showForm && (
        <div onClick={()=>setShowForm(false)} style={{ position:"fixed", inset:0, background:"rgba(0,0,0,0.85)", zIndex:1000, display:"flex", alignItems:"center", justifyContent:"center", backdropFilter:"blur(4px)" }}>
          <div onClick={e=>e.stopPropagation()} style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:6, width:480, overflow:"hidden", boxShadow:"0 24px 80px rgba(0,0,0,0.6)" }}>
            <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"14px 18px", borderBottom:`1px solid ${C.border}` }}>
              <span style={{ fontFamily:MONO, fontSize:12, color:C.text }}>{editCam?"EDIT CAMERA":"ADD CAMERA"}</span>
              <button onClick={()=>setShowForm(false)} style={{ background:"none", border:"none", color:C.muted, cursor:"pointer", fontSize:20 }}>×</button>
            </div>
            <div style={{ padding:"18px 18px", display:"flex", flexDirection:"column", gap:14 }}>
              <div>
                <div style={LABEL}>Camera Name / ID</div>
                <input style={INPUT} placeholder="gate_1" value={form.name} onChange={e=>setForm(f=>({...f,name:e.target.value}))} />
              </div>
              <div>
                <div style={LABEL}>Source</div>
                <input style={INPUT} placeholder="0  or  rtsp://ip/stream  or  path/to/video.mp4" value={form.source} onChange={e=>setForm(f=>({...f,source:e.target.value}))} />
                <div style={{ fontSize:10, color:C.muted, marginTop:4 }}>Webcam index, RTSP URL, or video file path</div>
              </div>
              <div>
                <div style={LABEL}>Counting Line Y (pixels from top)</div>
                <input style={INPUT} type="number" placeholder="300" value={form.line_y} onChange={e=>setForm(f=>({...f,line_y:+e.target.value}))} />
              </div>
              <div>
                <div style={LABEL}>Location Label (optional)</div>
                <input style={INPUT} placeholder="Main Gate, Parking Lot B…" value={form.location} onChange={e=>setForm(f=>({...f,location:e.target.value}))} />
              </div>
              <div style={{ background:C.surface2, padding:"10px 12px", borderRadius:3, marginTop:4 }}>
                <div style={{ fontSize:10, color:C.muted, lineHeight:1.7 }}>
                  After saving, update your <span style={{color:C.accent,fontFamily:MONO}}>.env</span> file and restart the backend for changes to take effect.
                </div>
              </div>
            </div>
            <div style={{ display:"flex", justifyContent:"flex-end", gap:8, padding:"12px 18px", borderTop:`1px solid ${C.border}` }}>
              <button style={BTN(false)} onClick={()=>setShowForm(false)}>Cancel</button>
              <button style={BTN(true)} onClick={saveCamera}>Save Camera</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}