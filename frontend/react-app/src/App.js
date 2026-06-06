import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { GLOBAL_STYLES, C } from "./theme";
import { connectWS, subscribeStatus } from "./ws";
import Sidebar from "./components/Sidebar";
import Dashboard  from "./pages/Dashboard";
import Violations from "./pages/Violations";
import Cameras    from "./pages/Cameras";
import Health     from "./pages/Health";

export default function App() {
  const [wsConnected, setWsConnected] = useState(false);

  useEffect(() => {
    connectWS();
    const unsub = subscribeStatus(setWsConnected);
    return unsub;
  }, []);

  return (
    <BrowserRouter>
      <style>{GLOBAL_STYLES}</style>
      <div style={{ display:"flex", minHeight:"100vh" }}>
        <Sidebar wsConnected={wsConnected} />
        <div style={{ marginLeft:200, flex:1, display:"flex", flexDirection:"column" }}>
          <div style={{ height:52, borderBottom:`1px solid ${C.border}`, padding:"0 28px", display:"flex", alignItems:"center", justifyContent:"space-between", position:"sticky", top:0, background:C.bg, zIndex:100 }}>
            <Routes>
              <Route path="/"           element={<span style={{fontFamily:"'Share Tech Mono',monospace",fontSize:13,letterSpacing:"0.1em"}}>SENTINEL / DASHBOARD</span>} />
              <Route path="/violations" element={<span style={{fontFamily:"'Share Tech Mono',monospace",fontSize:13,letterSpacing:"0.1em"}}>SENTINEL / VIOLATIONS</span>} />
              <Route path="/cameras"    element={<span style={{fontFamily:"'Share Tech Mono',monospace",fontSize:13,letterSpacing:"0.1em"}}>SENTINEL / CAMERAS</span>} />
              <Route path="/health"     element={<span style={{fontFamily:"'Share Tech Mono',monospace",fontSize:13,letterSpacing:"0.1em"}}>SENTINEL / HEALTH</span>} />
            </Routes>
            <div style={{fontFamily:"'Share Tech Mono',monospace",fontSize:11,color:C.textDim}}>
              {new Date().toLocaleDateString("en-GB",{day:"2-digit",month:"short",year:"numeric"}).toUpperCase()}
            </div>
          </div>
          <div style={{ flex:1, padding:"24px 28px", overflowY:"auto" }}>
            <Routes>
              <Route path="/"           element={<Dashboard  wsConnected={wsConnected} />} />
              <Route path="/violations" element={<Violations />} />
              <Route path="/cameras"    element={<Cameras />} />
              <Route path="/health"     element={<Health />} />
            </Routes>
          </div>
        </div>
      </div>
    </BrowserRouter>
  );
}