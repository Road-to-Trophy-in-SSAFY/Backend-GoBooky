# Python 버전 설정 가이드

## 현재 상태

- Python 3.9.13이 pyenv를 통해 전역으로 설정되어 있습니다.
- 가상환경(venv)도 Python 3.9.13을 사용하고 있습니다.
- 모든 패키지가 성공적으로 설치되었습니다.

## 설정 방법

이 프로젝트는 Python 3.9.13을 사용하며, pyenv를 통해 관리됩니다. 프로젝트를 시작할 때 항상 다음 단계를 따라 주세요:

### 1. 가상환경 활성화

```bash
# Backend-GoBooky 디렉토리에서:
source venv/bin/activate

# 활성화 후, 다음 명령으로 Python 버전 확인
python --version  # Python 3.9.13이 표시되어야 함
```

### 2. Homebrew Python alias와 충돌이 발생한다면

만약 `python` 명령어가 Homebrew의 Python을 가리키는 경우(alias):

```bash
# .zshrc 또는 .bash_profile에서 Python alias 제거
# 에디터로 파일을 열고 다음과 같은 줄을 찾아 주석 처리 또는 삭제
# alias python=/opt/homebrew/opt/python@3.9/bin/python3.9

# 또는 임시로 alias 해제
unalias python
```

### 3. pyenv PATH 우선순위 확인

pyenv가 시스템에 올바르게 설정되어 있는지 확인:

```bash
# .zshrc 또는 .bash_profile에 다음 내용이 있어야 함:
# export PATH="$HOME/.pyenv/shims:$PATH"

# pyenv 전역 버전 확인
pyenv global  # 결과: 3.9.13
```

## 참고사항

- 새 터미널을 열 때마다 가상환경을 활성화해야 합니다.
- VS Code에서 프로젝트를 열 때는 Python 인터프리터로 `./venv/bin/python`을 선택하세요.
