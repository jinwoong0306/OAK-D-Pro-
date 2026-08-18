"""Camera-free sensor-event simulator for the remote safety dashboard.

Set SAFETY_SERVER_URL and SAFETY_API_KEY in the PowerShell session, then run:
    python src/simulate_sensor_events.py --scenario full
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SERVER_URL = os.getenv("SAFETY_SERVER_URL", "").rstrip("/")
API_KEY = os.getenv("SAFETY_API_KEY", "")
API_KEY_HEADER = os.getenv("SAFETY_API_KEY_HEADER", "X-API-Key")

SCENARIOS: dict[str, list[dict[str, object]]] = {
    "safe": [],
    "caution": [{"label": "person", "confidence": 0.91, "distance_m": 1.3, "distance_confidence": "high"}],
    "danger": [{"label": "person", "confidence": 0.94, "distance_m": 0.8, "distance_confidence": "high"}],
    "uncertain": [{"label": "unknown object", "confidence": 0.68, "distance_m": None, "distance_confidence": "invalid"}],
}


def send_event(objects: list[dict[str, object]]) -> dict:
    if not SERVER_URL or not API_KEY:
        raise RuntimeError("Set SAFETY_SERVER_URL and SAFETY_API_KEY before running the simulator.")
    payload = {
        "timestamp": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "source": "simulator",
        "device_id": "camera-free-simulator",
        "fps": 20.0,
        "objects": objects,
    }
    request = Request(
        f"{SERVER_URL}/api/v1/sensor-events",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", API_KEY_HEADER: API_KEY},
    )
    try:
        with urlopen(request, timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Server rejected the event ({error.code}): {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Could not connect to the safety server: {error.reason}") from error


def play_state(name: str, seconds: float, interval: float) -> None:
    objects = SCENARIOS[name]
    end_at = time.monotonic() + seconds
    while time.monotonic() < end_at:
        response = send_event(objects)
        nearest = response.get("nearest_object") or {}
        distance = nearest.get("distance_m", "-")
        print(f"{name.upper():9} -> {response['system_status']:16} | distance: {distance}")
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send camera-free safety events to the dashboard server.")
    parser.add_argument("--scenario", choices=[*SCENARIOS, "full"], default="full")
    parser.add_argument("--seconds", type=float, default=3.0, help="Duration for a single state scenario")
    parser.add_argument("--interval", type=float, default=0.5, help="Seconds between events")
    args = parser.parse_args()
    if args.seconds <= 0 or args.interval <= 0:
        parser.error("--seconds and --interval must be positive")

    names = [args.scenario] if args.scenario != "full" else ["safe", "caution", "danger", "uncertain"]
    for name in names:
        print(f"\n--- Simulating {name.upper()} for {args.seconds:.1f}s ---")
        play_state(name, args.seconds, args.interval)

    if args.scenario == "full":
        print("\n--- Simulator stopped ---")
        print("Wait about 3 seconds to confirm SENSOR_OFFLINE on the web dashboard.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSimulator stopped by user.")
    except RuntimeError as error:
        print(f"Simulator error: {error}")
