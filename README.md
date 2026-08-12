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

```powershell
# RGB와 stereo depth 미리보기
python src/stream_preview.py

# RGB·depth 이미지 캡처
python src/capture_streams.py

# 조건별 거리 측정
python src/depth_condition_test.py --label "1m_front" --frames 60

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

- 거리 조건 측정: `data/measurements/depth_condition_results.csv`
- 객체 감지 성능: `data/measurements/performance_results.csv`
- 감지 로그: `data/logs/detections.csv`
- 경고 캡처: `data/logs/warning_frames/`

## 문제 해결

| 증상 | 조치 |
| --- | --- |
| `No available devices` 또는 `X_LINK_ERROR` | 프로그램을 종료하고 USB3 케이블을 다시 연결한 뒤 장치 인식 명령을 다시 실행한다. |
| PowerShell에서 활성화가 막힘 | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` 후 ` .\.venv\Scripts\Activate.ps1 `를 실행한다. |
| 거리값이 `N/A` | 대상이 0.1m~3.0m 범위에 있는지, 조명이 충분한지, 대상이 화면 중앙에 있는지 확인한다. |
| 저조도에서 경고가 부정확함 | 감지는 가능하지만 거리값이 불안정할 수 있다. 밝은 환경의 약 1m 정면 조건을 우선 사용한다. |
