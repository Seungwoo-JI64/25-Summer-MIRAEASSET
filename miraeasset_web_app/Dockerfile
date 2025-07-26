# 사용할 파이썬 기본 이미지 (경량 버전 권장)
FROM python:3.12

# 컨테이너 내 작업 디렉토리 설정
WORKDIR /app

# 시스템에 필요한 의존성 설치 (일반적으로 없지만, 필요한 경우 여기에 추가)
# 예: RUN apt-get update && apt-get install -y some-package-name && rm -rf /var/lib/apt/lists/*

# 파이썬 의존성 파일 먼저 복사하여 Docker 캐시 활용
COPY requirements.txt .

# 파이썬 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 파일들 복사
# .env 파일은 민감 정보 포함 가능성이 있어 컨테이너에 직접 복사하지 않는 것이 일반적입니다.
# 환경 변수는 'docker run' 시 -e 옵션으로 전달합니다.
COPY app.py .
COPY portfolio.json .
COPY templates/ templates/
COPY analysis_model/ analysis_model/

# Flask 애플리케이션이 실행될 포트 노출
# app.py에서 socketio.run(app, debug=True)를 사용할 때 기본 포트는 5000입니다.
EXPOSE 5000

# 애플리케이션 실행 명령어 정의
# SocketIO와 함께 Eventlet을 사용하도록 명시적으로 지정
# Eventlet은 Flask-SocketIO가 비동기적으로 작동하도록 돕는 WSGI 서버입니다.
# Gunicorn을 사용하려면 `gunicorn --worker-class eventlet -w 1 app:app -b 0.0.0.0:5000` 와 같이 복잡해지므로,
# 여기서는 app.py의 socketio.run()을 직접 실행하는 방식을 사용합니다.
# debug=True는 프로덕션 환경에 적합하지 않으니 실제 배포 시 app.py에서 해당 부분을 조정하거나,
# Flask 환경 변수를 사용하여 제어하는 것이 좋습니다.
CMD ["python", "app.py"]