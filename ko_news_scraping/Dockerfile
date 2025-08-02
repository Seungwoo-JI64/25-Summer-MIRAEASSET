# Docker 이미지 생성

# Docker 작동 환경
FROM python:3.12-slim

# 크롬 브라우저 다운로드 (웹크롤링용)
## 크롬 설치를 위한 시스템 설치
RUN apt-get update && apt-get install -y curl gnupg wget
## 크롬 브라우저 설치
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable

# 애플리케이션 설정
## 작업 디렉토리 설정
WORKDIR /app
## 필수 패키지 설치 항목(txt파일)을 작업 디렉토리로 복사
COPY requirements.txt .
# 필수 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 현재 모든 파일과 폴더(소스 코드)를 전부 작업 디렉토리로 복사
COPY . .

# 파이썬3을 사용하여 실행시킬 파일 지정
CMD ["python3", "최종_국내뉴스요약_jsw.py"]

