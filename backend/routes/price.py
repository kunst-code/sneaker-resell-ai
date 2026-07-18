"""
가격 조회 API 라우트
"""
from flask import Blueprint, request, jsonify
from services.price_service import search_sneaker_api, get_price_from_local_db

price_bp = Blueprint('price', __name__)


@price_bp.route('/search', methods=['GET'])
def search_price():
    """품번으로 가격 정보 조회"""
    style_code = request.args.get('style_code', '').strip()
    if not style_code:
        return jsonify({"error": "style_code 파라미터가 필요합니다."}), 400

    result = search_sneaker_api(style_code)

    if "error" in result:
        return jsonify(result), 404

    return jsonify({"success": True, "data": result})


@price_bp.route('/history/<style_code>', methods=['GET'])
def price_history(style_code):
    """특정 품번의 가격 이력 조회"""
    result = get_price_from_local_db(style_code)

    if "error" in result:
        return jsonify(result), 404

    return jsonify({"success": True, "data": result})
