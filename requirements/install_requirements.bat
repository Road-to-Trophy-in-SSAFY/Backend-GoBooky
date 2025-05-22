@echo off
REM Windows 전용 설치 스크립트

echo Windows 환경에서 패키지를 설치합니다...
pip install -r requirements-base.txt
pip install -r requirements-windows.txt
echo 설치가 완료되었습니다!
