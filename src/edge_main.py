"""Single-command local edge runtime: camera, safety decision, and dashboard."""

from __future__ import annotations

import argparse
import os
import threading
import time

import uvicorn

from src.edge_server import app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local OAK-D wheelchair safety edge runtime.")
    parser.add_argument("--host", default="127.0.0.1", help="Local dashboard bind address.")
    parser.add_argument("--port", type=int, default=8010, help="Local dashboard port.")
    parser.add_argument("--dashboard-only", action="store_true", help="Start the local dashboard without opening the camera.")
    args = parser.parse_args()

    server = uvicorn.Server(uvicorn.Config(app, host=args.host, port=args.port, log_level="info"))
    thread = threading.Thread(target=server.run, name="edge-dashboard", daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError("로컬 엣지 대시보드를 시작하지 못했습니다.")

    print(f"Local edge dashboard: http://{args.host}:{args.port}/dashboard/")
    if args.dashboard_only:
        try:
            while thread.is_alive():
                time.sleep(0.2)
        except KeyboardInterrupt:
            pass
        finally:
            server.should_exit = True
        return

    # object_distance_demo reads these variables when it is imported.  The
    # camera process always publishes to the local edge API in this runtime.
    os.environ["SAFETY_SERVER_URL"] = f"http://{args.host}:{args.port}"
    os.environ["SAFETY_API_KEY"] = "local-edge"
    os.environ["SAFETY_API_KEY_HEADER"] = "X-Edge-Local"
    from src.object_distance_demo import main as run_camera

    try:
        run_camera()
    finally:
        server.should_exit = True
        thread.join(timeout=3)


if __name__ == "__main__":
    main()
