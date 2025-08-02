# Docker 이미지 생성

# Docker 작동 환경
FROM python:3.12

# 애플리케이션 설정
## 작업 디렉토리 설정
WORKDIR /app

## 필수 패키지 설치 항목(txt파일)을 작업 디렉토리로 복사
COPY requirements.txt .

# 필수 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 파일들(소스코드) 작업 디렉토리로 복사
# 환경 변수는 'docker run' 시 -e 옵션으로 전달한다
COPY app.py .
COPY portfolio.json .
COPY templates/ templates/
COPY analysis_model/ analysis_model/

# app.py에서 Flask 애플리케이션(socketio.run(app, debug=True))이 실행될 기본 포트는 5000
EXPOSE 5000

# 파이썬을 사용하여 실행시킬 파일 지정
CMD ["python", "app.py"]