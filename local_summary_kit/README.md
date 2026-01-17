# Jenny Jeon 동영상 요약 키트

이 폴더는 유튜브 동영상의 자막을 추출하고, 구글 Gemini API를 이용해 요약본을 생성하는 도구를 포함하고 있습니다.
클라우드 환경에서의 IP 차단 문제를 우회하기 위해, **본인의 PC(로컬 환경)**에서 실행하시기를 권장합니다.

## 구성 파일
- `summarize.py`: 요약 작업을 수행하는 파이썬 스크립트
- `requirements.txt`: 필요한 라이브러리 목록
- `JennyJeon_Videos.xlsx`: 동영상 목록이 담긴 엑셀 파일 (입력용)

## 사용 방법

### 1. 파이썬 설치
컴퓨터에 파이썬(Python 3.9 이상)이 설치되어 있어야 합니다.

### 2. 라이브러리 설치
터미널(또는 CMD)을 열고 이 폴더 경로로 이동한 뒤, 다음 명령어를 실행하여 필요한 라이브러리를 설치합니다.

```bash
pip install -r requirements.txt
```

### 3. Gemini API Key 준비
Google AI Studio에서 발급받은 API Key가 필요합니다.

### 4. 스크립트 실행
다음 명령어로 스크립트를 실행합니다.

```bash
python summarize.py
```

실행 후 API Key를 입력하라는 메시지가 나오면 키를 붙여넣고 엔터를 누르세요.

### 5. 결과 확인
작업이 완료되면 같은 폴더에 `JennyJeon_Videos_Summarized_Final.xlsx` 파일이 생성됩니다.
이 파일에는 각 동영상의 자막 기반 요약 내용이 포함됩니다. (자막이 없는 경우 제목 기반 추측 내용이 포함됨)
