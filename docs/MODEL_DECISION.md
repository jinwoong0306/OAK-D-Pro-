# MVP 객체 감지 모델 선택

선택 모델: `yolov6-nano` (DepthAI Model Zoo 사전학습 COCO 모델)

## 선택 이유

- OAK-D Pro의 RVC2 플랫폼에서 DepthAI v3 `DetectionNetwork`와
  `SpatialDetectionNetwork`로 공식 지원된다.
- 사람과 일반 COCO 객체를 감지하므로, 현재 MVP의 "사람 또는 일반 객체" 범위를
  커스텀 학습 없이 충족한다.
- bounding box, 클래스명, confidence, stereo depth 기반 공간 좌표를 한 파이프라인에서
  다룰 수 있다.
- 모델은 첫 실행 시 Model Zoo에서 내려받아 캐시되므로 별도 모델 변환 과정이 없다.

## 초기 설정

- confidence threshold: 0.5
- depth 범위: 0.1m ~ 3.0m
- 우선 대상: `person`

## 제외한 선택지

- 커스텀 모델: 데이터 수집·라벨링·변환이 필요해 3주 MVP 범위 밖이다.
- 더 큰 YOLO 모델: 초기 MVP의 재현성과 FPS 목표에 비해 불필요한 위험이 있다.
