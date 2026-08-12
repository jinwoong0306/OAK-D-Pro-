# 3~5분 최종 데모 진행 스크립트

1. OAK-D Pro를 USB3에 연결하고 ` .\run_demo.ps1 `를 실행한다.
2. 화면의 FPS, 객체 수, `CLEAR` 상태를 소개한다.
3. 사람 또는 일반 물체를 카메라에 보인다. bounding box, 객체명, confidence, 거리를 설명한다.
4. 대상을 약 1m 안쪽으로 이동한다. `WARNING: TOO CLOSE`와 빨간 상태 전환을 보여 준다.
5. `data/logs/detections.csv`와 `data/logs/warning_frames/`를 열어 로그·캡처 저장을 확인한다.
6. 밝은 환경 약 1m에서 가장 안정적이며 저조도 거리값은 보정이 필요하다는 한계를 설명한다.
