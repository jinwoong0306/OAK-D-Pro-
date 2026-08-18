"""Local-only safety API and dashboard used by the edge runtime.

The safety decision is deliberately made here, on the laptop connected to the
OAK-D Pro.  A remote server may receive copies of the resulting events later,
but it is not required for the warning or virtual-stop decision.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
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


class EdgeSafetyEngine:
    """Distance-to-status state machine that runs entirely on the laptop."""

    def __init__(self) -> None:
        self.thresholds = json.loads(THRESHOLD_PATH.read_text(encoding="utf-8"))
        self.events: list[dict] = []
        self.danger_hits = 0
        self.last_sensor_received: datetime | None = None
        self.status = self._offline_status()

    def _offline_status(self) -> dict:
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
    def _action_for(status: StatusName) -> str:
        return {
            "SAFE": "NORMAL_DRIVE",
            "CAUTION": "VIRTUAL_SLOW_DOWN",
            "DANGER": "VIRTUAL_STOP",
            "UNCERTAIN": "CHECK_FORWARD",
            "SENSOR_OFFLINE": "CHECK_SENSOR",
        }[status]

    @staticmethod
    def _nearest(objects: list[DetectedObject]) -> DetectedObject | None:
        valid = [item for item in objects if item.distance_m is not None and item.distance_confidence in {"high", "medium"}]
        return min(valid, key=lambda item: item.distance_m) if valid else None

    def _decide(self, event: SensorEvent, nearest: DetectedObject | None) -> tuple[StatusName, str]:
        if not event.objects:
            self.danger_hits = 0
            return "SAFE", "유효한 위험 거리 내 장애물이 없습니다."
        if nearest is None:
            self.danger_hits = 0
            return "UNCERTAIN", "감지된 객체의 거리 신뢰도가 낮아 위험 거리를 판정할 수 없습니다."

        distance = nearest.distance_m
        assert distance is not None
        if distance <= self.thresholds["danger_enter_m"]:
            self.danger_hits += 1
            if self.danger_hits >= self.thresholds["danger_confirmations"]:
                return "DANGER", f"{nearest.label}이(가) 가상 정지 기준 {self.thresholds['danger_enter_m']}m 이내입니다."
            return "CAUTION", "위험 거리 진입을 확인 중입니다."

        self.danger_hits = 0
        if self.status["system_status"] == "DANGER" and distance <= self.thresholds["danger_release_m"]:
            return "DANGER", "안전 거리로 충분히 벗어났는지 확인 중입니다."
        if distance <= self.thresholds["caution_enter_m"]:
            return "CAUTION", f"{nearest.label}이(가) 감속 권고 기준 {self.thresholds['caution_enter_m']}m 이내입니다."
        if self.status["system_status"] == "CAUTION" and distance <= self.thresholds["safe_release_m"]:
            return "CAUTION", "안전 거리로 충분히 벗어났는지 확인 중입니다."
        return "SAFE", "유효한 위험 거리 내 장애물이 없습니다."

    def process(self, event: SensorEvent) -> tuple[dict, bool]:
        self.last_sensor_received = datetime.now(UTC)
        nearest = self._nearest(event.objects)
        status_name, reason = self._decide(event, nearest)
        previous = self.status["system_status"]
        changed = previous != status_name
        self.status = {
            "system_status": status_name,
            "recommended_action": self._action_for(status_name),
            "reason": reason,
            "nearest_object": nearest.model_dump() if nearest else None,
            "last_received_at": self.last_sensor_received.isoformat(),
            "sensor_connected": True,
            "source": event.source.upper(),
            "fps": event.fps,
            "event_id": f"EDGE-{uuid4().hex[:8].upper()}" if changed else self.status["event_id"],
        }
        if changed:
            self.events.insert(0, {
                "at": datetime.now(UTC).isoformat(),
                "status": status_name,
                "reason": reason,
                "event_id": self.status["event_id"],
            })
            self.events = self.events[:20]
        return self.status, changed

    def check_timeout(self) -> tuple[dict, bool]:
        if self.last_sensor_received is None:
            return self.status, False
        elapsed = (datetime.now(UTC) - self.last_sensor_received).total_seconds()
        if elapsed <= self.thresholds["sensor_timeout_seconds"] or self.status["system_status"] == "SENSOR_OFFLINE":
            return self.status, False
        self.status = {
            **self.status,
            "system_status": "SENSOR_OFFLINE",
            "recommended_action": self._action_for("SENSOR_OFFLINE"),
            "reason": f"마지막 센서 이벤트 이후 {self.thresholds['sensor_timeout_seconds']}초 이상 데이터가 수신되지 않았습니다.",
            "sensor_connected": False,
            "event_id": f"EDGE-OFF-{uuid4().hex[:8].upper()}",
        }
        self.events.insert(0, {
            "at": datetime.now(UTC).isoformat(),
            "status": "SENSOR_OFFLINE",
            "reason": self.status["reason"],
            "event_id": self.status["event_id"],
        })
        self.events = self.events[:20]
        return self.status, True


def create_edge_app() -> FastAPI:
    engine = EdgeSafetyEngine()
    clients: set[WebSocket] = set()

    async def broadcast(status: dict) -> None:
        stale: list[WebSocket] = []
        for client in clients:
            try:
                await client.send_json(status)
            except RuntimeError:
                stale.append(client)
        for client in stale:
            clients.discard(client)

    async def watchdog() -> None:
        while True:
            await asyncio.sleep(1)
            status, changed = engine.check_timeout()
            if changed:
                await broadcast(status)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        task = asyncio.create_task(watchdog())
        yield
        task.cancel()

    app = FastAPI(title="Wheelchair Safety Assist Edge", version="0.2.0", lifespan=lifespan)
    app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")

    @app.get("/", include_in_schema=False)
    async def dashboard() -> RedirectResponse:
        """Keep relative dashboard assets under the mounted /dashboard/ path."""
        return RedirectResponse(url="/dashboard/")

    @app.get("/api/v1/health")
    async def health() -> dict:
        return {"edge": "ok", "sensor_connected": engine.status["sensor_connected"]}

    @app.get("/api/v1/status")
    async def current_status() -> dict:
        return engine.status

    @app.get("/api/v1/events")
    async def recent_events(limit: int = 20) -> list[dict]:
        return engine.events[:max(1, min(limit, 20))]

    @app.get("/api/v1/settings")
    async def current_settings() -> dict:
        return engine.thresholds

    @app.post("/api/v1/sensor-events")
    async def sensor_event(event: SensorEvent) -> dict:
        status, _ = engine.process(event)
        await broadcast(status)
        return status

    @app.post("/api/v1/settings")
    async def update_settings(update: SettingsUpdate) -> dict:
        candidate = {**engine.thresholds, **update.model_dump(exclude_none=True)}
        if candidate["danger_enter_m"] >= candidate["caution_enter_m"]:
            raise HTTPException(422, "정지 기준은 감속 권고 기준보다 작아야 합니다.")
        engine.thresholds = candidate
        THRESHOLD_PATH.write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
        return engine.thresholds

    @app.websocket("/ws/dashboard")
    async def dashboard_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        clients.add(websocket)
        await websocket.send_json(engine.status)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            clients.discard(websocket)

    return app


app = create_edge_app()
