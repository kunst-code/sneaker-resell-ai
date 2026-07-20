"""
스니커즈 리셀러 AI 추천 프로그램 - Flask 백엔드 메인 서버
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

app = Flask(__name__)
CORS(app)

# 업로드 폴더 설정
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# 프론트엔드 정적 파일 경로 (절대 경로)
FRONTEND_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))

# Blueprint 등록
from routes.vision import vision_bp
from routes.price import price_bp
from routes.forecast import forecast_bp
from routes.recommend import recommend_bp
from routes.trending import trending_bp

app.register_blueprint(vision_bp, url_prefix='/api/vision')
app.register_blueprint(price_bp, url_prefix='/api/price')
app.register_blueprint(forecast_bp, url_prefix='/api/forecast')
app.register_blueprint(recommend_bp, url_prefix='/api/recommend')
app.register_blueprint(trending_bp, url_prefix='/api/trending')


@app.route('/')
def index():
    return send_from_directory(FRONTEND_FOLDER, 'index.html')


@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(FRONTEND_FOLDER, filename)


@app.route('/health')
def health():
    return jsonify({"status": "ok", "message": "스니커즈 리셀러 AI 서버 정상 작동 중"})


if __name__ == '__main__':
    from db.database import init_db
    init_db()
    from seed_recommendations import seed_recommendations_if_empty, seed_popular_if_empty
    seed_recommendations_if_empty()
    seed_popular_if_empty()

    # 서버 시작 시 데이터 수집 (24시간 지났으면 자동 수집)
    from services.collector_service import collect_trending_data, should_collect
    if should_collect():
        print("📦 트렌딩 데이터 수집 중 (하루 1회)...")
        result = collect_trending_data()
        if result.get('status') == 'success':
            print(f"✅ {result['collected']}개 스니커즈 수집 완료")
        elif result.get('error'):
            print(f"⚠️ 수집 스킵: {result.get('error', result.get('message', ''))}")
    else:
        print("📋 트렌딩 데이터: 캐시 사용 (24시간 이내 수집됨)")

    port = int(os.environ.get('PORT', 8000))
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'

    print(f"\n🚀 스니커즈 리셀러 AI 서버 시작!")
    print(f"📍 http://localhost:{port}\n")
    app.run(debug=debug, host='0.0.0.0', port=port)
else:
    # gunicorn 등 WSGI 서버로 실행 시
    from db.database import init_db
    init_db()
    from seed_recommendations import seed_recommendations_if_empty, seed_popular_if_empty
    seed_recommendations_if_empty()
    seed_popular_if_empty()
