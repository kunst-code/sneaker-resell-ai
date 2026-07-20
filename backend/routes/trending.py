"""
트렌딩/인기 스니커즈 API 라우트
로컬 DB 기반 - RapidAPI 하루 1회 수집 데이터 제공
"""
from flask import Blueprint, request, jsonify
from db.database import get_db
from services.collector_service import (
    get_trending_from_db,
    get_price_history_30d,
    get_last_collection_info,
    collect_trending_data,
)

trending_bp = Blueprint('trending', __name__)


@trending_bp.route('/popular', methods=['GET'])
def popular():
    """
    실시간 인기 스니커즈 목록
    1시간 DB 캐시 → 즉시 로드, 만료 시 백그라운드 갱신
    """
    limit = request.args.get('limit', 20, type=int)
    brand = request.args.get('brand', '').strip() or None
    size = request.args.get('size', '').strip() or None
    gender = request.args.get('gender', '').strip() or None
    sort = request.args.get('sort', 'rank').strip()
    order = request.args.get('order', 'asc').strip()

    valid_sorts = ['rank', 'min_price', 'avg_price', 'max_price']
    if sort not in valid_sorts:
        sort = 'rank'

    # 캐시 키 생성
    import hashlib
    cache_key = hashlib.md5(f"{brand}:{gender}:{size}:{sort}:{order}:{limit}".encode()).hexdigest()

    # DB 캐시 확인 (1시간)
    cached = _get_popular_cache(cache_key)
    if cached:
        return jsonify(cached)

    # KicksDB에서 실시간 조회
    from services.kicksdb_service import get_trending_sneakers
    kicksdb_result = get_trending_sneakers(limit=limit, brand=brand, gender=gender, sort=sort, order=order, size=size)

    if kicksdb_result.get('success') and kicksdb_result.get('trending'):
        from services.exchange_rate import get_usd_krw
        kicksdb_result['exchange_rate'] = get_usd_krw()
        _save_popular_cache(cache_key, kicksdb_result)
        return jsonify(kicksdb_result)

    # 폴백: 로컬 DB
    result = get_trending_from_db(limit=limit)
    return jsonify(result)


def _get_popular_cache(cache_key: str):
    """1시간 이내 캐시 반환"""
    from datetime import datetime, timedelta
    import json as json_lib
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS popular_cache (
                cache_key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        cutoff = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('SELECT data FROM popular_cache WHERE cache_key = ? AND created_at > ?', (cache_key, cutoff))
        row = cursor.fetchone()
        conn.close()
        if row:
            result = json_lib.loads(row['data'])
            result['from_cache'] = True
            return result
    except Exception:
        pass
    return None


def _save_popular_cache(cache_key: str, data: dict):
    """캐시 저장"""
    import json as json_lib
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS popular_cache (
                cache_key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('INSERT OR REPLACE INTO popular_cache (cache_key, data) VALUES (?, ?)',
                       (cache_key, json_lib.dumps(data, ensure_ascii=False)))
        conn.commit()
        conn.close()
    except Exception:
        pass


@trending_bp.route('/search', methods=['GET'])
def search():
    """로컬 DB에서 스니커즈 검색 (모델명 또는 품번)"""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({"error": "검색어(q)를 입력해주세요."}), 400

    limit = request.args.get('limit', 20, type=int)

    conn = get_db()
    cursor = conn.cursor()
    search_term = f'%{query}%'

    cursor.execute('''
        SELECT s.style_code, s.brand, s.model_name, s.colorway, s.release_date,
               s.retail_price, s.image_url,
               (SELECT ph.price FROM price_history ph WHERE ph.style_code = s.style_code AND ph.platform = 'StockX' ORDER BY ph.recorded_date DESC LIMIT 1) as stockx_price_usd,
               (SELECT ph2.price FROM price_history ph2 WHERE ph2.style_code = s.style_code AND ph2.platform = 'KREAM' ORDER BY ph2.recorded_date DESC LIMIT 1) as avg_price_krw
        FROM sneakers s
        WHERE s.style_code LIKE ? OR s.model_name LIKE ? OR s.brand LIKE ? OR s.colorway LIKE ?
        LIMIT ?
    ''', (search_term, search_term, search_term, search_term, limit))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return jsonify({"success": True, "products": [], "count": 0})

    products = []
    for row in rows:
        r = dict(row)
        products.append({
            "style_code": r.get('style_code', ''),
            "brand": r.get('brand', ''),
            "model_name": r.get('model_name', ''),
            "colorway": r.get('colorway', ''),
            "release_date": r.get('release_date', ''),
            "release_year": (r.get('release_date') or '')[:4] or 'N/A',
            "retail_price": r.get('retail_price', 0),
            "image": r.get('image_url', ''),
            "stockx_price_usd": r.get('stockx_price_usd'),
            "avg_price_krw": r.get('avg_price_krw'),
        })

    return jsonify({"success": True, "products": products, "count": len(products)})


@trending_bp.route('/history/<style_code>', methods=['GET'])
def price_history(style_code):
    """특정 스니커즈의 최근 30일 가격 변동"""
    result = get_price_history_30d(style_code)

    if "error" in result:
        return jsonify(result), 404

    return jsonify(result)


@trending_bp.route('/recommendations', methods=['GET'])
def trend_recommendations():
    """트렌드 분석 기반 구매 추천 Top 10"""
    from services.trend_service import get_trend_recommendations
    result = get_trend_recommendations()

    if "error" in result:
        return jsonify(result), 500

    return jsonify(result)


@trending_bp.route('/keywords', methods=['GET'])
def trend_keywords():
    """트렌드 키워드 Top 20 (워드클라우드용)"""
    # 기본 트렌드 키워드 (스니커즈 모델명만)
    keywords = [
        {"text": "New Balance 992", "size": 100},
        {"text": "Nike Dunk Low", "size": 95},
        {"text": "Jordan 1 Low OG", "size": 90},
        {"text": "Asics Gel-Kayano 14", "size": 88},
        {"text": "New Balance 990v6", "size": 85},
        {"text": "Adidas Samba OG", "size": 82},
        {"text": "Air Force 1 '07", "size": 80},
        {"text": "Salomon XT-6", "size": 78},
        {"text": "New Balance 2002R", "size": 75},
        {"text": "Jordan 4 Bred", "size": 72},
        {"text": "New Balance 1906R", "size": 70},
        {"text": "Adidas Gazelle", "size": 68},
        {"text": "Converse Chuck 70", "size": 65},
        {"text": "Nike SB Dunk", "size": 62},
        {"text": "Asics Gel-1130", "size": 60},
        {"text": "Jordan 1 Chicago", "size": 55},
        {"text": "Yeezy Slide", "size": 52},
        {"text": "New Balance 530", "size": 50},
        {"text": "Nike Cortez", "size": 48},
        {"text": "Puma Suede", "size": 45},
    ]

    # 인기 목록에서 동적 키워드 추가 시도
    try:
        from services.kicksdb_service import get_trending_sneakers, get_api_key
        if get_api_key():
            result = get_trending_sneakers(limit=10)
            if result.get('success') and result.get('trending'):
                dynamic_keywords = []
                for i, item in enumerate(result['trending'][:10]):
                    brand = item.get('brand', '')
                    model = item.get('model', '') or item.get('title', '').split(' ')[0]
                    if brand:
                        dynamic_keywords.append({"text": brand, "size": 90 - i * 5})
                    if model and len(model) < 20:
                        dynamic_keywords.append({"text": model, "size": 85 - i * 5})
                # 중복 제거 후 병합
                existing = {k['text'].lower() for k in keywords}
                for dk in dynamic_keywords:
                    if dk['text'].lower() not in existing:
                        keywords.append(dk)
                        existing.add(dk['text'].lower())
    except Exception:
        pass

    return jsonify({"keywords": keywords[:20]})


@trending_bp.route('/collect', methods=['POST'])
def trigger_collection():
    """
    데이터 수집 트리거 (수동 실행)
    ?force=true 로 24시간 체크 무시 가능
    """
    force = request.args.get('force', 'false').lower() == 'true'
    result = collect_trending_data(force=force)

    if "error" in result:
        return jsonify(result), 500

    return jsonify(result)


@trending_bp.route('/status', methods=['GET'])
def collection_status():
    """마지막 수집 상태 확인"""
    info = get_last_collection_info()
    return jsonify(info)
