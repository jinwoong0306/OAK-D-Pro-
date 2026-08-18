const states = {
  SAFE: {
    symbol: "✓", description: "전방 안전", action: "정상 주행", actionCode: "NORMAL_DRIVE",
    object: "감지된 장애물 없음", objectIcon: "—", distance: "—", distanceNote: "안전 거리",
    distanceConfidence: "—", objectConfidence: "—", reason: "유효한 위험 거리 내 장애물이 없습니다.", fps: "19.8 FPS", source: "SIMULATOR"
  },
  CAUTION: {
    symbol: "!", description: "감속 권고", action: "속도를 줄이세요", actionCode: "VIRTUAL_SLOW_DOWN",
    object: "사람", objectIcon: "●", distance: "1.28 m", distanceNote: "주의 거리",
    distanceConfidence: "높음", objectConfidence: "91%", reason: "사람이 감속 권고 거리 1.5m 이내에 있습니다.", fps: "19.4 FPS", source: "SIMULATOR"
  },
  DANGER: {
    symbol: "■", description: "정지 필요", action: "즉시 정지하세요", actionCode: "VIRTUAL_STOP",
    object: "사람", objectIcon: "●", distance: "0.82 m", distanceNote: "위험 거리",
    distanceConfidence: "높음", objectConfidence: "94%", reason: "사람이 가상 정지 기준 거리 1.0m 이내에 있습니다.", fps: "19.6 FPS", source: "SIMULATOR"
  },
  UNCERTAIN: {
    symbol: "?", description: "거리 측정 불안정", action: "전방을 직접 확인하세요", actionCode: "CHECK_FORWARD",
    object: "알 수 없는 객체", objectIcon: "?", distance: "측정 불가", distanceNote: "신뢰 불가",
    distanceConfidence: "낮음", objectConfidence: "68%", reason: "유효 depth 값이 부족해 위험 거리를 확정할 수 없습니다.", fps: "18.7 FPS", source: "SIMULATOR"
  },
  SENSOR_OFFLINE: {
    symbol: "×", description: "센서 연결 확인", action: "센서 상태를 확인하세요", actionCode: "CHECK_SENSOR",
    object: "센서 데이터 없음", objectIcon: "×", distance: "—", distanceNote: "마지막 수신 3초 초과",
    distanceConfidence: "—", objectConfidence: "—", reason: "마지막 센서 이벤트 이후 3초 이상 데이터가 수신되지 않았습니다.", fps: "—", source: "NO DATA"
  }
};

let eventNumber = 0;
let socket;
let lastServerEventId = "";
const get = (id) => document.getElementById(id);
const now = () => new Intl.DateTimeFormat("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(new Date());

function addEvent(state, reason, eventId = "", eventTime = now()) {
  if (eventId && eventId === lastServerEventId) return;
  if (eventId) lastServerEventId = eventId;
  eventNumber += 1;
  const list = get("event-list");
  list.querySelector(".empty-event")?.remove();
  const item = document.createElement("li");
  item.innerHTML = `<span class="event-state">${state}</span><span>${reason}</span><span class="event-time">${eventTime}</span>`;
  list.prepend(item);
  while (list.children.length > 5) list.lastElementChild.remove();
  get("event-count").textContent = `${eventNumber} event${eventNumber === 1 ? "" : "s"}`;
}

function renderEventHistory(events) {
  const list = get("event-list");
  list.replaceChildren();
  if (!events.length) {
    list.innerHTML = '<li class="empty-event">아직 기록된 상태 변경이 없습니다.</li>';
    eventNumber = 0;
    get("event-count").textContent = "0 events";
    return;
  }
  eventNumber = 0;
  events.slice(0, 5).reverse().forEach((event) => {
    const eventTime = event.at
      ? new Intl.DateTimeFormat("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(new Date(event.at))
      : now();
    addEvent(event.status, event.reason, event.event_id, eventTime);
  });
}

function setState(name, serverStatus = null) {
  const fallback = states[name];
  const object = serverStatus?.nearest_object;
  const actionLabels = {
    NORMAL_DRIVE: "정상 주행", VIRTUAL_SLOW_DOWN: "속도를 줄이세요", VIRTUAL_STOP: "즉시 정지하세요",
    CHECK_FORWARD: "전방을 직접 확인하세요", CHECK_SENSOR: "센서 상태를 확인하세요"
  };
  const state = serverStatus ? {
    ...fallback,
    actionCode: serverStatus.recommended_action,
    action: actionLabels[serverStatus.recommended_action] || fallback.action,
    reason: serverStatus.reason || fallback.reason,
    object: object?.label || fallback.object,
    objectIcon: object ? "●" : fallback.objectIcon,
    distance: object?.distance_m != null ? `${object.distance_m.toFixed(2)} m` : fallback.distance,
    distanceNote: object ? (name === "DANGER" ? "위험 거리" : name === "CAUTION" ? "주의 거리" : "안전 거리") : fallback.distanceNote,
    distanceConfidence: object?.distance_confidence ? ({ high: "높음", medium: "보통", low: "낮음", invalid: "신뢰 불가" }[object.distance_confidence]) : fallback.distanceConfidence,
    objectConfidence: object?.confidence != null ? `${Math.round(object.confidence * 100)}%` : fallback.objectConfidence,
    fps: serverStatus.fps != null ? `${serverStatus.fps.toFixed(1)} FPS` : fallback.fps,
    source: serverStatus.source || fallback.source
  } : fallback;
  const card = get("status-card");
  card.className = `status-card status-${name.toLowerCase().replace("_", "-")}`;
  get("status-symbol").textContent = state.symbol;
  get("status-name").textContent = name;
  get("status-description").textContent = state.description;
  get("recommended-action").textContent = state.action;
  get("action-code").textContent = state.actionCode;
  get("object-name").textContent = state.object;
  get("object-icon").textContent = state.objectIcon;
  get("distance-value").textContent = state.distance;
  get("distance-note").textContent = state.distanceNote;
  get("distance-confidence").textContent = state.distanceConfidence;
  get("object-confidence").textContent = state.objectConfidence;
  get("reason").textContent = state.reason;
  get("data-source").textContent = state.source;
  get("fps").textContent = state.fps;
  get("event-id").textContent = serverStatus?.event_id || `SIM-${String(eventNumber + 1).padStart(3, "0")}`;
  get("last-update").textContent = name === "SENSOR_OFFLINE" ? "3초 전 마지막 수신" : "방금 수신";
  get("sensor-connection").innerHTML = name === "SENSOR_OFFLINE"
    ? '<i class="dot"></i> 센서 데이터 없음'
    : '<i class="dot online"></i> 센서 연결됨';
  addEvent(name, state.reason, serverStatus?.event_id || "");
}

async function loadServerStatus() {
  try {
    const response = await fetch("/api/v1/status");
    if (!response.ok) throw new Error("status request failed");
    const status = await response.json();
    setState(status.system_status, status);
    const eventsResponse = await fetch("/api/v1/events?limit=5");
    if (eventsResponse.ok) renderEventHistory(await eventsResponse.json());
    return true;
  } catch {
    // The standalone static preview has no API; the local simulator remains usable.
    return false;
  }
}

function connectSocket() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${protocol}://${window.location.host}/ws/dashboard`);
  socket.onmessage = ({ data }) => {
    const status = JSON.parse(data);
    setState(status.system_status, status);
  };
  socket.onclose = () => setTimeout(connectSocket, 2000);
}

document.querySelectorAll("[data-state]").forEach((button) => button.addEventListener("click", () => {
  // These controls are only for previewing the dashboard UI.  They must not
  // change the remote safety state or require the sensor API key.
  setState(button.dataset.state);
}));

loadServerStatus().then((connected) => { if (connected) connectSocket(); });
