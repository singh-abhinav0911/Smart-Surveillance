import { BASE } from "./theme";

const WS_URL = BASE.replace("http", "ws") + "/ws/events";

let socket       = null;
let retryCount   = 0;
let retryTimer   = null;
let heartbeatTimer = null;
const MAX_RETRY_MS = 30000;
const subscribers  = new Set();
const statusSubs   = new Set();

function getRetryDelay() {
  // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s max
  return Math.min(1000 * Math.pow(2, retryCount), MAX_RETRY_MS);
}

function notifyStatus(connected) {
  statusSubs.forEach(cb => cb(connected));
}

function startHeartbeat() {
  clearInterval(heartbeatTimer);
  heartbeatTimer = setInterval(() => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      try { socket.send(JSON.stringify({ type: "ping" })); } catch {}
    }
  }, 25000);
}

function stopHeartbeat() {
  clearInterval(heartbeatTimer);
}

export function connectWS() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return;

  socket = new WebSocket(WS_URL);

  socket.onopen = () => {
    retryCount = 0;
    notifyStatus(true);
    startHeartbeat();
  };

  socket.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data);
      if (d.type === "pong") return; // heartbeat reply
      subscribers.forEach(cb => cb(d));
    } catch {}
  };

  socket.onclose = (e) => {
    stopHeartbeat();
    notifyStatus(false);
    // Don't retry on intentional close (code 1000)
    if (e.code === 1000) return;
    const delay = getRetryDelay();
    retryCount++;
    retryTimer = setTimeout(connectWS, delay);
  };

  socket.onerror = () => {
    socket.close();
  };
}

export function disconnectWS() {
  clearTimeout(retryTimer);
  stopHeartbeat();
  if (socket) {
    socket.close(1000, "intentional");
    socket = null;
  }
  retryCount = 0;
}

// Subscribe to messages
export function subscribeWS(cb) {
  subscribers.add(cb);
  return () => subscribers.delete(cb);
}

// Subscribe to connection status changes
export function subscribeStatus(cb) {
  statusSubs.add(cb);
  return () => statusSubs.delete(cb);
}