# Linux 안전 대시보드 서버

Linux 서버에서 프로젝트 루트로 이동한 뒤 실행합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
```

같은 네트워크의 브라우저에서 `http://<Linux-서버-IP>:8000`을 엽니다.

- `POST /api/v1/sensor-events`: 노트북 OAK-D 감지 이벤트 수신
- `GET /api/v1/status`: 최신 안전 상태
- `WS /ws/dashboard`: 실시간 대시보드 갱신
- `POST /api/v1/simulator/{SAFE|CAUTION|DANGER|UNCERTAIN|SENSOR_OFFLINE}`: 카메라 없는 시연용 상태 전환
