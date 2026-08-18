"""Linux-hosted API and dashboard for the wheelchair safety-assist MVP."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = ROOT_DIR / "web" / "dashboard"
THRESHOLD_PATH = ROOT_DIR / "config" / "safety_thresholds.json"

StatusName = Literal["SAFE", "CAUTION", "DANGER", "UNCERTAIN", "SENSOR_OFFLINE"]


class DetectedObject(BaseModel):
    label: str
    confidence: float = Field(ge=0, le=1)
    distance_m: float | None = Field(default=None, ge=0)
    distance_confidence: Literal["high", "medium", "low", "invalid"] = "invalid"


class SensorEvent(BaseModel):
    timestamp: datetime
    source: Literal["oakd", "simulator"] = "oakd"
    device_id: str | None = None
    fps: float | None = Field(default=None, ge=0)
    objects: list[DetectedObject] = []


class SettingsUpdate(BaseModel):
    caution_enter_m: float | None = Field(default=None, gt=0)
    danger_enter_m: float | None = Field(default=None, gt=0)
    danger_release_m: float | None = Field(default=None, gt=0)
    safe_release_m: float | None = Field(default=None, gt=0)


class SafetyService:
    def __init__(self) -> None:
        self.thresholds = json.loads(THRESHOLD_PATH.read_text(encoding="utf-8"))
        self.clients: set[WebSocket] = set()
        self.events: list[dict] = []
        self.last_sensor_received: datetime | None = None
        self.danger_hits = 0
        self.status = self._empty_status()

    def _empty_status(self) -> dict:
        return {
            "system_status": "SENSOR_OFFLINE",
            "recommended_action": "CHECK_SENSOR",
            "reason": "센서 이벤트를 기다리는 중입니다.",
            "nearest_object": None,
            "last_received_at": None,
            "sensor_connected": False,
            "source": "NO DATA",
            "fps": None,
            "event_id": "BOOT-000",
        }

    @staticmethod
    def _action_for(status: StatusName) -> tuple[str, str]:
        return {
            "SAFE": ("NORMAL_DRIVE", "전방 안전"),
            "CAUTION": ("VIRTUAL_SLOW_DOWN", "감속 권고"),
            "DANGER": ("VIRTUAL_STOP", "정지 필요"),
            "UNCERTAIN": ("CHECK_FORWARD", "거리 측정 불안정"),
            "SENSOR_OFFLINE": ("CHECK_SENSOR", "센서 연결 확인"),
        }[status]

    def _valid_nearest(self, objects: list[DetectedObject]) -> DetectedObject | None:
        valid = [item for item in objects if item.distance_m is not None and item.distance_confidence in {"high", "medium"}]
        return min(valid, key=lambda item: item.distance_m) if valid else None

    def _next_status(self, event: SensorEvent, nearest: DetectedObject | None) -> tuple[StatusName, str]:
        if not event.objects:
            self.danger_hits = 0
            return "SAFE", "유효한 위험 거리 내 장애물이 없습니다."
        if nearest is None:
            self.danger_hits = 0
            return "UNCERTAIN", "감지된 객체의 거리 신뢰도가 낮아 위험 거리를 확정할 수 없습니다."

        distance = nearest.distance_m
        assert distance is not None
        if distance <= self.thresholds["danger_enter_m"]:
            self.danger_hits += 1
            if self.danger_hits >= self.thresholds["danger_confirmations"]:
                return "DANGER", f"{nearest.label}이(가) 가상 정지 기준 거리 {self.thresholds['danger_enter_m']}m 이내에 있습니다."
            return "CAUTION", "위험 거리 진입을 확인 중입니다."

        self.danger_hits = 0
        if self.status["system_status"] == "DANGER" and distance <= self.thresholds["danger_release_m"]:
            return "DANGER", "안전 거리로 충분히 벗어났는지 확인 중입니다."
        if distance <= self.thresholds["caution_enter_m"]:
            return "CAUTION", f"{nearest.label}이(가) 감속 권고 거리 {self.thresholds['caution_enter_m']}m 이내에 있습니다."
        if self.status["system_status"] == "CAUTION" and distance <= self.thresholds["safe_release_m"]:
            return "CAUTION", "안전 거리로 충분히 벗어났는지 확인 중입니다."
        return "SAFE", "유효한 위험 거리 내 장애물이 없습니다."

    async def process(self, event: SensorEvent) -> dict:
        self.last_sensor_received = datetime.now(UTC)
        nearest = self._valid_nearest(event.objects)
        status, reason = self._next_status(event, nearest)
        action, _ = self._action_for(status)
        new_status = {
            "system_status": status,
            "recommended_action": action,
            "reason": reason,
            "nearest_object": nearest.model_dump() if nearest else None,
            "last_received_at": self.last_sensor_received.isoformat(),
            "sensor_connected": True,
            "source": event.source.upper(),
            "fps": event.fps,
            "event_id": f"EVT-{uuid4().hex[:8].upper()}",
        }
        await self._set_status(new_status)
        return self.status

    async def set_simulated_status(self, status: StatusName) -> dict:
        now = datetime.now(UTC)
        examples = {
            "SAFE": [],
            "CAUTION": [DetectedObject(label="person", confidence=.91, distance_m=1.28, distance_confidence="high")],
            "DANGER": [DetectedObject(label="person", confidence=.94, distance_m=.82, distance_confidence="high")],
            "UNCERTAIN": [DetectedObject(label="unknown object", confidence=.68, distance_m=None, distance_confidence="invalid")],
        }
        if status == "SENSOR_OFFLINE":
            self.last_sensor_received = None
            action, _ = self._action_for(status)
            await self._set_status({**self._empty_status(), "system_status": status, "recommended_action": action, "event_id": f"SIM-{uuid4().hex[:8].upper()}"})
            return self.status
        if status == "DANGER":
            self.danger_hits = self.thresholds["danger_confirmations"] - 1
        return await self.process(SensorEvent(timestamp=now, source="simulator", fps=19.5, objects=examples[status]))

    async def check_timeout(self) -> None:
        if self.last_sensor_received is None:
            return
        elapsed = (datetime.now(UTC) - self.last_sensor_received).total_seconds()
        if elapsed > self.thresholds["sensor_timeout_seconds"] and self.status["system_status"] != "SENSOR_OFFLINE":
            action, _ = self._action_for("SENSOR_OFFLINE")
            await self._set_status({**self.status, "system_status": "SENSOR_OFFLINE", "recommended_action": action, "reason": "마지막 센서 이벤트 이후 3초 이상 데이터가 수신되지 않았습니다.", "sensor_connected": False, "event_id": f"OFF-{uuid4().hex[:8].upper()}"})

    async def _set_status(self, new_status: dict) -> None:
        previous = self.status["system_status"]
        self.status = new_status
        if previous != new_status["system_status"]:
            self.events.insert(0, {"at": datetime.now(UTC).isoformat(), "status": new_status["system_status"], "reason": new_status["reason"], "event_id": new_status["event_id"]})
            self.events = self.events[:20]
        await self.broadcast()

    async def broadcast(self) -> None:
        stale = []
        for client in self.clients:
            try:
                await client.send_json(self.status)
            except RuntimeError:
                stale.append(client)
        for client in stale:
            self.clients.discard(client)


service = SafetyService()


async def watchdog() -> None:
    while True:
        await asyncio.sleep(1)
        await service.check_timeout()


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(watchdog())
    yield
    task.cancel()


app = FastAPI(title="Wheelchair Safety Assist API", version="0.1.0", lifespan=lifespan)
app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")


@app.get("/", include_in_schema=False)
async def dashboard() -> FileResponse:
    return FileResponse(DASHBOARD_DIR / "index.html")


@app.get("/api/v1/health")
async def health() -> dict:
    return {"server": "ok", "sensor_connected": service.status["sensor_connected"]}


@app.get("/api/v1/status")
async def current_status() -> dict:
    return service.status


@app.get("/api/v1/events")
async def recent_events(limit: int = 20) -> list[dict]:
    return service.events[: max(1, min(limit, 20))]


@app.get("/api/v1/settings")
async def current_settings() -> dict:
    """Return the active safety thresholds for dashboard display."""
    return service.thresholds


@app.post("/api/v1/sensor-events")
async def sensor_event(event: SensorEvent) -> dict:
    return await service.process(event)


@app.post("/api/v1/settings")
async def update_settings(update: SettingsUpdate) -> dict:
    changes = update.model_dump(exclude_none=True)
    candidate = {**service.thresholds, **changes}
    if candidate["danger_enter_m"] >= candidate["caution_enter_m"]:
        raise HTTPException(422, "정지 기준은 감속 권고 기준보다 작아야 합니다.")
    service.thresholds = candidate
    THRESHOLD_PATH.write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    return service.thresholds


@app.post("/api/v1/simulator/{status_name}")
async def simulator(status_name: StatusName) -> dict:
    return await service.set_simulated_status(status_name)


@app.websocket("/ws/dashboard")
async def dashboard_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    service.clients.add(websocket)
    await websocket.send_json(service.status)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        service.clients.discard(websocket)
