$ErrorActionPreference = 'Stop'

if (-not (Test-Path '.\.venv\Scripts\python.exe')) {
    throw '가상환경이 없습니다. README의 설치 절차를 먼저 실행하세요.'
}

& '.\.venv\Scripts\python.exe' '-m' 'src.edge_main'
