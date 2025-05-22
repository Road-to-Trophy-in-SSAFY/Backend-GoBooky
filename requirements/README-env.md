# GoBooky 프로젝트 환경 설정 안내

## 크로스 플랫폼 개발 설정

본 프로젝트는 macOS와 Windows 환경 모두에서 작업할 수 있도록 구성되어 있습니다.
OS별 의존성 패키지를 자동으로 설치하기 위해 다음 파일들이 제공됩니다:

### 설치 파일 구조

- `requirements-base.txt`: 모든 OS에 공통으로 필요한 패키지
- `requirements-windows.txt`: Windows 전용 패키지 (pywin32 등)
- `requirements-mac.txt`: macOS 전용 패키지
- `install_requirements.sh`: macOS/Linux용 설치 스크립트
- `install_requirements.bat`: Windows용 설치 스크립트

## 설치 방법

### macOS / Linux 사용자

```bash
# 스크립트에 실행 권한 부여
chmod +x install_requirements.sh

# 스크립트 실행
./install_requirements.sh
```

### Windows 사용자

```cmd
# cmd 또는 PowerShell에서 실행
install_requirements.bat
```

## 주의사항

- 가상환경(venv)은 각 OS별로 생성해 사용하세요.
- 원본 `requirements.txt`는 더 이상 사용하지 않습니다.
- 새로운 패키지를 추가할 때는 `requirements-base.txt`에 추가하되, OS 전용 패키지는 각각 해당 파일에 추가해 주세요.

## 가상환경 활성화

```bash
# macOS/Linux
source ./venv/bin/activate

# Windows
.\venv\Scripts\activate
```
