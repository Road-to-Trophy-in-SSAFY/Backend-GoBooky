#!/bin/bash

# OS 타입 감지
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "macOS 환경을 감지했습니다. 맥 환경에 맞는 패키지를 설치합니다..."
    pip install -r requirements-base.txt
    pip install -r requirements-mac.txt
    echo "설치가 완료되었습니다!"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    # Windows - Git Bash나 MSYS 등에서 실행될 경우
    echo "Windows 환경을 감지했습니다. 윈도우 환경에 맞는 패키지를 설치합니다..."
    pip install -r requirements-base.txt
    pip install -r requirements-windows.txt
    echo "설치가 완료되었습니다!"
else
    # 기타 OS (Linux 등)
    echo "기타 OS 환경을 감지했습니다. 기본 패키지만 설치합니다..."
    pip install -r requirements-base.txt
    echo "설치가 완료되었습니다!"
fi
