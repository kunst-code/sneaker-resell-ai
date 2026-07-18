"""
시계열 예측 API 라우트
"""
from flask import Blueprint, request, jsonify
from services.forecast_service import forecast_price_prophet

forecast_bp = Blueprint('forecast', __name__)


@forecast_bp.route('/predict', methods=['GET'])
def predict():
    """품번 기반 가격 예측"""
    style_code = request.args.get('style_code', '').strip()
    periods = request.args.get('periods', 30, type=int)

    if not style_code:
        return jsonify({"error": "style_code 파라미터가 필요합니다."}), 400

    if periods < 7 or periods > 90:
        return jsonify({"error": "periods는 7~90일 사이여야 합니다."}), 400

    result = forecast_price_prophet(style_code, periods)

    if "error" in result:
        return jsonify(result), 400

    return jsonify({"success": True, "data": result})
