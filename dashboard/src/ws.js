const WS_URL = "ws://localhost:8000/ws/events";

let socket = null;
const listeners = new Set();

export function connectWS() {
  if (socket && socket.readyState === WebSocket.OPEN) return;

  socket = new WebSocket(WS_URL);

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      listeners.forEach(fn => fn(data));
    } catch {}
  };

  socket.onclose = () => {
    // Reconnect after 3s
    setTimeout(connectWS, 3000);
  };

  socket.onerror = () => {
    socket.close();
  };
}

export function subscribeWS(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function disconnectWS() {
  if (socket) socket.close();
}