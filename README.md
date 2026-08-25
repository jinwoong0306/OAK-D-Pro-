# OAK-D Pro 거리 기반 객체 감지 MVP

OAK-D Pro의 RGB·stereo depth·YOLOv6-Nano 객체 감지를 결합해 객체별 거리와 접근 경고를 표시하는 Python MVP입니다.

## 폴더 구조

```text
src/          실행 코드
data/
  captures/   RGB·depth 캡처 이미지
  measurements/ 거리 조건 측정 CSV
docs/         모델 선택과 기술 결정 문서
installer/    OAK Viewer 설치본과 설치 로그
.venv/        로컬 Python 가상환경
```

## 설치

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

OAK-D Pro를 USB3 포트에 연결한 뒤 OAK Viewer 또는 아래 명령으로 장치 인식을 확인한다.

```powershell
python -c "import depthai as dai; print(dai.Device.getAllAvailableDevices())"
```

## 주요 실행 명령

## 로컬 엣지 MVP 실행

카메라, 위험 판단, 현장 대시보드는 노트북에서 함께 실행한다. 리눅스 서버나
인터넷 연결은 필요하지 않다.

```powershell
.\run_demo.ps1
# 또는
python -m src.edge_main
```

대시보드: `http://127.0.0.1:8010/dashboard/`

구조와 카메라 없는 점검 방법은 [로컬 엣지 MVP 구조](docs/EDGE_MVP_ARCHITECTURE.md)를 참고한다.

```powershell
# RGB와 stereo depth 미리보기
python src/stream_preview.py

# RGB·depth 이미지 캡처
python src/capture_streams.py

# 줄자로 실측한 거리 조건 검증 (실측값과 오차를 CSV에 저장)
python src/depth_condition_test.py --label "1m_front" --actual-m 1.0 --frames 100

# 객체 감지
python src/object_detection_demo.py

# 객체 감지 + 안정화된 거리 + 1.2m 접근 경고
python src/object_distance_demo.py
```

모든 OpenCV 미리보기는 `q` 키로 종료합니다.

## 빠른 데모 실행

PowerShell에서 아래 한 줄로 가상환경을 확인하고 통합 데모를 실행할 수 있습니다.

```powershell
.\run_demo.ps1
```

## 결과 파일

- 거리 검증: `data/measurements/depth_validation_results.csv`
- 객체 감지 성능: `data/measurements/performance_results.csv`
- 감지 로그: `data/logs/detections.csv`
- 경고 캡처: `data/logs/warning_frames/`

## 문제 해결

| 증상 | 조치 |
| --- | --- |
| `No available devices` 또는 `X_LINK_ERROR` | 프로그램을 종료하고 USB3 케이블을 다시 연결한 뒤 장치 인식 명령을 다시 실행한다. |
| PowerShell에서 활성화가 막힘 | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` 후 ` .\.venv\Scripts\Activate.ps1 `를 실행한다. |
| 거리값이 `N/A` | 대상이 0.4m~3.0m 범위에 있는지, 조명이 충분한지, 대상이 화면 중앙에 있는지 확인한다. |
| 저조도에서 경고가 부정확함 | 감지는 가능하지만 거리값이 불안정할 수 있다. 밝은 환경의 약 1m 정면 조건을 우선 사용한다. |
# Linux Safety Server Connection

When the OAK-D demo is connected to the remote safety dashboard, set these values in the PowerShell session before starting the demo. The API key must match the secret configured only on the Linux server.

```powershell
$env:SAFETY_SERVER_URL = 'http://203.234.62.117:8010'
$env:SAFETY_API_KEY = 'server-secret-goes-here'
$env:SAFETY_API_KEY_HEADER = 'X-API-Key'
python .\src\object_distance_demo.py
```

The demo sends a sensor heartbeat twice per second, including when no object is detected. The web dashboard then shows the sensor as connected while the program is running and switches to `SENSOR_OFFLINE` about three seconds after it stops.

## Camera-free dashboard test

With the same server environment variables set, run the complete safety sequence without an OAK-D Pro:

```powershell
python .\src\simulate_sensor_events.py --scenario full
```

It sends `SAFE → CAUTION → DANGER → UNCERTAIN` events to the real Linux server. When the program ends, wait about three seconds to verify `SENSOR_OFFLINE` in the web dashboard.

## API state-machine verification

Verify the remote server's `SAFE → CAUTION → DANGER → UNCERTAIN → SENSOR_OFFLINE` rules automatically:

```powershell
python .\src\verify_safety_api.py
```

Use `--skip-offline` when the server timeout should not be tested.
