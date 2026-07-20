FROM python:3.11-slim

# 시스템 의존성 (Playwright용)
RUN apt-get update && apt-get install -y \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxshmfence1 \
    libglib2.0-0 \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright 브라우저 설치
RUN playwright install chromium

# 앱 복사
COPY . .

# 데이터 디렉토리 생성
RUN mkdir -p data backend/uploads

EXPOSE 8000

CMD ["gunicorn", "--chdir", "backend", "app:app", "--bind", "0.0.0.0:8000", "--timeout", "120", "--workers", "2"]
