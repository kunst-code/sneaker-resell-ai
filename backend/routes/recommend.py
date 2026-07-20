"""
종합 추천 API 라우트 - 전체 파이프라인 통합
"""
import os
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from services.vision_service import identify_sneaker
from services.price_service import get_price_from_local_db, search_sneaker_api
from services.forecast_service import forecast_price_prophet
from services.recommend_service import generate_recommendation

recommend_bp = Blueprint('recommend', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@recommend_bp.route('/analyze', methods=['POST'])
def full_analysis():
    """
    전체 분석 파이프라인:
    1. 이미지 업로드 → 비전 모델 인식
    2. 품번으로 시세 조회
    3. 시계열 예측
    4. LLM 추천 리포트 생성
    """
    if 'image' not in request.files:
        return jsonify({"error": "이미지 파일이 필요합니다."}), 400

    file = request.files['image']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({"error": "올바른 이미지 파일을 업로드해주세요."}), 400

    # Step 1: 이미지 저장 및 인식
    filename = secure_filename(file.filename)
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    sneaker_info = identify_sneaker(filepath)
    if "error" in sneaker_info and "style_code" not in sneaker_info:
        print(f"[ERROR] Vision 인식 실패: {sneaker_info}")
        return jsonify({"error": "스니커즈 인식에 실패했습니다.", "details": sneaker_info}), 500

    style_code = sneaker_info.get('style_code', '')

    # Step 2: 가격 데이터 조회 (KicksDB 1순위 → 로컬 DB 폴백)
    price_data = search_sneaker_api(style_code)
    if "error" in price_data:
        # 인식된 품번이 없으면 기본 데모 데이터 사용
        price_data = get_price_from_local_db('DD1391-100')

    # Step 3: 시계열 예측
    forecast_data = forecast_price_prophet(style_code, periods=30)
    if "error" in forecast_data:
        forecast_data = forecast_price_prophet('DD1391-100', periods=30)

    # Step 4: LLM 추천 생성
    recommendation = generate_recommendation(sneaker_info, price_data, forecast_data)

    return jsonify({
        "success": True,
        "pipeline": {
            "step1_identification": sneaker_info,
            "step2_price_data": price_data,
            "step3_forecast": forecast_data,
            "step4_recommendation": recommendation,
        }
    })


@recommend_bp.route('/analyze-by-code', methods=['POST'])
def analyze_by_code():
    """품번으로 직접 분석 (이미지 업로드 없이)"""
    data = request.get_json()
    if not data or 'style_code' not in data:
        return jsonify({"error": "style_code가 필요합니다."}), 400

    style_code = data['style_code'].strip()
    size = data.get('size', '').strip()  # 사이즈 (선택)

    # 가격 데이터 조회 (KicksDB → 로컬 DB)
    price_data = search_sneaker_api(style_code)
    if "error" in price_data:
        return jsonify({"error": f"품번 '{style_code}'에 대한 데이터를 찾을 수 없습니다."}), 404

    # 시계열 예측
    forecast_data = forecast_price_prophet(style_code, periods=30)

    # 스니커즈 정보
    sneaker_info = price_data.get('sneaker', {})
    if size:
        sneaker_info['selected_size'] = size
        price_data['selected_size'] = size

    # AI 추천은 명시적 요청 시에만 (use_ai=true 파라미터)
    use_ai = data.get('use_ai', False)
    if use_ai:
        recommendation = generate_recommendation(sneaker_info, price_data, forecast_data)
    else:
        recommendation = {"recommendation": "N/A", "summary": "AI 분석 미사용", "key_factors": [], "detailed_report": ""}

    return jsonify({
        "success": True,
        "selected_size": size or "전체 (최저가 기준)",
        "pipeline": {
            "step1_identification": sneaker_info,
            "step2_price_data": price_data,
            "step3_forecast": forecast_data,
            "step4_recommendation": recommendation,
        }
    })
