#!/bin/bash
# SneakerAI 서버 실행 스크립트

cd "$(dirname "$0")"

# 가상환경이 없으면 생성
if [ ! -d "venv" ]; then
    echo "📦 가상환경 생성 중..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

echo ""
echo "👟 SneakerAI 서버를 시작합니다..."
echo "📍 브라우저에서 http://localhost:8000 접속하세요"
echo "🛑 종료: Ctrl+C"
echo ""

cd backend
python3 app.py
