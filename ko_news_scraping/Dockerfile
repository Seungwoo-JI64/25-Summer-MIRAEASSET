# 1. 파이썬 3.12 버전을 기반으로 환경 구성을 시작합니다.
FROM python:3.12-slim

# 2. 크롬 설치에 필요한 시스템 도구들을 먼저 설치합니다.
RUN apt-get update && apt-get install -y curl gnupg wget

# 3. 구글 크롬 브라우저를 설치합니다.
#    - 키를 받고, 저장소를 추가한 뒤, 크롬 안정화 버전을 설치합니다.
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable

# 4. 파이썬 라이브러리를 설치할 준비를 합니다.
#    - 작업 폴더를 만들고, requirements.txt 파일을 복사합니다.
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 나머지 모든 소스 코드를 복사합니다.
COPY . .

# 6. 이 환경이 시작될 때 실행할 기본 명령어를 설정합니다.
#    - Render 대시보드의 Command와 동일한 역할을 합니다.
# GEMINI 사용
CMD ["python3", "최종_국내뉴스요약_jsw.py"]

