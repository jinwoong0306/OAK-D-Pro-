# 로컬 엣지 MVP 구조

## 실행 구조

```text
OAK-D Pro → object_distance_demo.py → 로컬 엣지 API → 로컬 대시보드
                                  └→ SAFE / CAUTION / DANGER 판단
```

위 흐름은 모두 노트북에서 실행된다. 인터넷, 리눅스 서버, API 키가 없어도
거리 기준 판단과 가상 정지 UI가 동작한다.

## 한 번에 실행

```powershell
.\run_demo.ps1
```

또는 다음 명령을 사용한다.

```powershell
python -m src.edge_main
```

실행 후 현장 대시보드는 `http://127.0.0.1:8010/dashboard/`에서 연다.
카메라 없이 UI와 로컬 API만 확인하려면 다음을 사용한다.

```powershell
python -m src.edge_main --dashboard-only
```

## 역할 분리

| 구성 요소 | 역할 | 인터넷 필요 |
| --- | --- | --- |
| 노트북 엣지 런타임 | 카메라 입력, 거리 판단, 상태 전환, 현장 대시보드 | 아니오 |
| 리눅스 서버 | 향후 원격 모니터링, 운행 로그, 관리자 기능 | 선택 |

리눅스 서버는 MVP의 안전 판단 경로에 포함하지 않는다. 추후 서버를 다시
연결하더라도, 노트북이 이미 판단한 결과를 복제·기록하는 용도로만 사용한다.

## 안전 범위

`VIRTUAL_STOP`은 화면상 가상 정지 권고다. 실제 브레이크나 모터를 제어하지
않는다.
