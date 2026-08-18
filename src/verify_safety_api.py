"""Verify the remote safety API state machine without an OAK-D Pro.

Requires SAFETY_SERVER_URL and SAFETY_API_KEY in the current environment.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SERVER_URL = os.getenv("SAFETY_SERVER_URL", "").rstrip("/")
API_KEY = os.getenv("SAFETY_API_KEY", "")
API_KEY_HEADER = os.getenv("SAFETY_API_KEY_HEADER", "X-API-Key")


def request(path: str, method: str = "GET", payload: dict | None = None) -> dict:
    if not SERVER_URL:
        raise RuntimeError("SAFETY_SERVER_URL is not set.")
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
        headers[API_KEY_HEADER] = API_KEY
    http_request = Request(f"{SERVER_URL}{path}", data=body, method=method, headers=headers)
    try:
        with urlopen(http_request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(f"{method} {path} failed ({error.code}): {error.read().decode(errors='replace')}") from error
    except URLError as error:
        raise RuntimeError(f"Could not connect to server: {error.reason}") from error


def sensor_event(objects: list[dict]) -> dict:
    return request("/api/v1/sensor-events", "POST", {
        "timestamp": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "source": "simulator",
        "device_id": "api-verifier",
        "fps": 20.0,
        "objects": objects,
    })


def assert_status(name: str, response: dict, expected: str) -> None:
    actual = response.get("system_status")
    marker = "PASS" if actual == expected else "FAIL"
    print(f"[{marker}] {name}: expected {expected}, received {actual}")
    if actual != expected:
        raise AssertionError(f"{name} returned {actual}, not {expected}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify remote safety API state transitions.")
    parser.add_argument("--skip-offline", action="store_true", help="Do not wait for SENSOR_OFFLINE verification")
    args = parser.parse_args()
    if not API_KEY:
        raise RuntimeError("SAFETY_API_KEY is not set.")

    health = request("/api/v1/health")
    print(f"[PASS] health: server={health.get('server')}, sensor_connected={health.get('sensor_connected')}")

    assert_status("SAFE", sensor_event([]), "SAFE")
    caution = [{"label": "person", "confidence": .91, "distance_m": 1.3, "distance_confidence": "high"}]
    assert_status("CAUTION", sensor_event(caution), "CAUTION")

    danger = [{"label": "person", "confidence": .94, "distance_m": .8, "distance_confidence": "high"}]
    first_danger = sensor_event(danger)
    assert_status("DANGER confirmation 1", first_danger, "CAUTION")
    assert_status("DANGER confirmation 2", sensor_event(danger), "DANGER")

    uncertain = [{"label": "unknown object", "confidence": .68, "distance_m": None, "distance_confidence": "invalid"}]
    assert_status("UNCERTAIN", sensor_event(uncertain), "UNCERTAIN")

    if not args.skip_offline:
        print("Waiting 4 seconds for the server sensor-timeout rule...")
        time.sleep(4)
        assert_status("SENSOR_OFFLINE", request("/api/v1/status"), "SENSOR_OFFLINE")

    print("\nAll requested API state checks passed.")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, RuntimeError) as error:
        print(f"\nVerification failed: {error}")
        sys.exit(1)
