# 거리 측정 검증 절차

## 목적

OAK-D Pro가 표시하는 거리를 줄자로 잰 실제 거리와 비교한다. 경고·위험
임계값을 확정하기 전 반드시 이 절차를 수행한다.

## 사전 조건

- OAK-D Pro를 USB3로 연결한다.
- 대상은 사람보다 먼저 평평하고 무늬가 있는 판자·상자처럼 화면 중앙을 충분히 채우는 물체를 쓴다.
- 카메라 전면과 대상 전면이 평행하도록 고정한다.
- 거리는 카메라 렌즈가 아니라 **스테레오 카메라 전면 기준**으로 줄자로 잰다.
- 밝은 실내에서 시작한다.

## 측정 명령

각 거리에서 카메라와 대상을 움직이지 않고 100프레임을 수집한다.

```powershell
.\.venv\Scripts\Activate.ps1
python src/depth_condition_test.py --label "050cm_center" --actual-m 0.50 --frames 100
python src/depth_condition_test.py --label "075cm_center" --actual-m 0.75 --frames 100
python src/depth_condition_test.py --label "100cm_center" --actual-m 1.00 --frames 100
python src/depth_condition_test.py --label "150cm_center" --actual-m 1.50 --frames 100
python src/depth_condition_test.py --label "200cm_center" --actual-m 2.00 --frames 100
```

결과는 `data/measurements/depth_validation_results.csv`에 저장된다.

## 판정

| 확인 항목 | 기록값 | 해석 |
| --- | --- | --- |
| 중앙값 오차 | `error_mm`, `error_percent` | 실제 거리와 체계적으로 차이 나는지 확인 |
| 흔들림 | `variation_mm` | 같은 위치에서 값이 얼마나 변하는지 확인 |
| 유효 픽셀 | `valid_roi_percent` | 낮으면 대상·조명·각도를 먼저 개선 |

0.5m·0.75m에서 불안정하면 대시보드의 위험거리 0.91m를 실제 제동 기준으로 쓰지 않는다. 객체 탐지 화면은 위 정적 검증을 통과한 뒤에만 별도로 확인한다.

## 이번 보정 내용

- RGB 객체 좌표에 맞도록 stereo depth를 CAM_A(RGB)에 정렬했다.
- 근거리 측정을 위해 extended disparity와 left-right check를 켰다.
- RGB·객체탐지·depth의 시간 차가 120ms를 넘으면 이전 depth를 재사용하지 않는다.
- 접근 중 실제 변화값을 버리던 거리 점프 필터를 제거했다.
