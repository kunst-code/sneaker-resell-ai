"""
KicksDB (kicks.dev) API v3 서비스
Base URL: https://api.kicks.dev/v3
응답 구조: {"$schema": ..., "data": [...]}
"""
import os
import httpx

KICKSDB_API_BASE = "https://api.kicks.dev/v3"


def get_api_key():
    return os.getenv('KICKSDB_API_KEY', '')


def _headers():
    return {
        'Authorization': f'Bearer {get_api_key()}',
        'Content-Type': 'application/json'
    }


def _extract_data(response_json):
    """v3 응답에서 data 배열 추출"""
    if isinstance(response_json, dict) and 'data' in response_json:
        return response_json['data']
    elif isinstance(response_json, list):
        return response_json
    return []


def search_sneakers(query: str, limit: int = 20) -> dict:
    """스니커즈 검색 (모델명, 품번/SKU)"""
    api_key = get_api_key()
    if not api_key:
        return {"error": "KICKSDB_API_KEY가 설정되지 않았습니다."}

    # 한글 키워드 → 영문 변환 (KicksDB는 영문만 지원)
    translated_query, expected_brand = _translate_query(query)

    try:
        response = httpx.get(
            f"{KICKSDB_API_BASE}/stockx/products",
            headers=_headers(),
            params={'query': translated_query, 'limit': limit},
            timeout=15.0
        )

        if response.status_code == 200:
            products = _extract_data(response.json())

            # 브랜드 필터링 (엉뚱한 결과 방지)
            if expected_brand and products:
                filtered = [p for p in products if expected_brand.lower() in (p.get('brand', '') or '').lower() or expected_brand.lower() in (p.get('title', '') or '').lower()]
                if filtered:
                    products = filtered

            return {"success": True, "products": products, "count": len(products)}
        else:
            return {"error": f"KicksDB API 오류: {response.status_code}", "details": response.text[:200]}
    except Exception as e:
        return {"error": f"KicksDB 요청 실패: {str(e)}"}


def _translate_query(query: str) -> tuple:
    """한글 검색어를 영문으로 변환, 예상 브랜드 반환"""
    translations = {
        '뉴발란스': ('New Balance', 'New Balance'),
        '나이키': ('Nike', 'Nike'),
        '조던': ('Jordan', 'Jordan'),
        '아디다스': ('adidas', 'adidas'),
        '아식스': ('Asics', 'Asics'),
        '컨버스': ('Converse', 'Converse'),
        '살로몬': ('Salomon', 'Salomon'),
        '반스': ('Vans', 'Vans'),
        '푸마': ('Puma', 'Puma'),
        '에어포스': ('Air Force', 'Nike'),
        '덩크': ('Dunk', 'Nike'),
        '겔카야노': ('Gel Kayano', 'Asics'),
        '삼바': ('Samba', 'adidas'),
        '가젤': ('Gazelle', 'adidas'),
        '척70': ('Chuck 70', 'Converse'),
        '이지': ('Yeezy', 'adidas'),
        '트래비스': ('Travis Scott', 'Jordan'),
    }

    result_query = query
    expected_brand = None

    for kr, (en, brand) in translations.items():
        if kr in query:
            result_query = query.replace(kr, en)
            expected_brand = brand
            break

    return result_query.strip(), expected_brand


def get_trending_sneakers(limit: int = 20, brand: str = None, gender: str = None, sort: str = 'rank', order: str = 'asc', size: str = None) -> dict:
    """인기 스니커즈 목록 (필터/정렬 지원)"""
    api_key = get_api_key()
    if not api_key:
        return {"error": "KICKSDB_API_KEY가 설정되지 않았습니다."}

    try:
        # KicksDB는 sort=rank, release_date만 지원
        # 가격 정렬은 서버에서 처리
        api_sort = 'rank' if sort in ('rank', 'min_price', 'avg_price', 'max_price') else sort
        api_order = 'asc' if api_sort == 'rank' else order

        params = {
            'sort': api_sort,
            'order': api_order,
            'limit': max(limit, 50) if sort in ('min_price', 'avg_price', 'max_price') else limit,
        }
        if brand:
            params['brand'] = brand
        if gender:
            params['gender'] = gender
        if size:
            params['size'] = size

        response = httpx.get(
            f"{KICKSDB_API_BASE}/stockx/products",
            headers=_headers(),
            params=params,
            timeout=15.0
        )

        if response.status_code == 200:
            products = _extract_data(response.json())
            trending = []
            for p in products:
                # description에서 출시가/출시일 파싱
                desc = p.get("description", "")
                retail_price = 0
                release_info = ""
                import re as _re
                retail_match = _re.search(r'retailed for \$(\d+)', desc)
                if retail_match:
                    retail_price = int(retail_match.group(1))
                release_match = _re.search(r'released in (\w+ (?:of )?\d{4})', desc)
                if release_match:
                    release_info = release_match.group(1)

                trending.append({
                    "id": p.get("id", ""),
                    "title": p.get("title", ""),
                    "brand": p.get("brand", ""),
                    "model": p.get("model", ""),
                    "sku": p.get("sku", ""),
                    "image": p.get("image", ""),
                    "release_date": release_info or p.get("release_date", ""),
                    "release_year": (p.get("release_date") or "")[:4] or "N/A",
                    "retail_price": retail_price,
                    "gender": p.get("gender", ""),
                    "min_price": p.get("min_price"),
                    "max_price": p.get("max_price"),
                    "avg_price": p.get("avg_price"),
                    "weekly_orders": p.get("weekly_orders", 0),
                    "rank": p.get("rank", 0),
                    "colorway": p.get("secondary_title", ""),
                })

            # 가격 기준 정렬 (API에서 지원하지 않으므로 서버 사이드)
            if sort in ('min_price', 'avg_price', 'max_price'):
                reverse = (order == 'desc')
                trending.sort(key=lambda x: x.get(sort) or 0, reverse=reverse)

            # limit 적용
            trending = trending[:limit]

            return {"success": True, "trending": trending, "count": len(trending)}
        else:
            return {"error": f"KicksDB API 오류: {response.status_code}", "details": response.text[:200]}
    except Exception as e:
        return {"error": f"KicksDB 요청 실패: {str(e)}"}


def get_price_from_kicksdb(style_code: str) -> dict:
    """
    품번으로 검색하여 실시간 가격 정보 반환
    price_service.py에서 1순위로 호출
    """
    api_key = get_api_key()
    if not api_key:
        return {"error": "KICKSDB_API_KEY가 설정되지 않았습니다."}

    try:
        response = httpx.get(
            f"{KICKSDB_API_BASE}/stockx/products",
            headers=_headers(),
            params={'query': style_code, 'limit': 5},
            timeout=15.0
        )

        if response.status_code != 200:
            return {"error": f"KicksDB API 오류: {response.status_code}"}

        products = _extract_data(response.json())
        if not products:
            return {"error": f"'{style_code}' 검색 결과 없음"}

        # SKU가 정확히 일치하는 상품 우선 선택
        product = None
        for p in products:
            if p.get('sku', '').upper() == style_code.upper():
                product = p
                break
        if not product:
            product = products[0]

        # 가격 데이터 구성
        min_price = product.get('min_price') or 0
        avg_price = product.get('avg_price') or 0
        max_price = product.get('max_price') or 0

        from services.exchange_rate import get_usd_krw
        exchange_rate = get_usd_krw()

        # StockX 기준 가격 (USD)
        stockx_usd = min_price
        stockx_krw = round(stockx_usd * exchange_rate)
        avg_krw = round(avg_price * exchange_rate)

        # 참고: StockX 가격과 KREAM 가격은 다릅니다
        # KREAM API가 없으므로 StockX 가격만 제공
        # KREAM은 보통 StockX보다 낮은 경우가 많음 (국내 유통)

        return {
            "source": "kicksdb_v3",
            "sneaker": {
                "brand": product.get("brand", ""),
                "model_name": product.get("title", ""),
                "style_code": product.get("sku", style_code),
                "colorway": product.get("secondary_title", ""),
                "release_date": product.get("release_date", ""),
                "image": product.get("image", ""),
                "gender": product.get("gender", ""),
            },
            "current_price": {
                "kream": 0,
                "stockx_usd": stockx_usd,
                "stockx_krw": stockx_krw,
                "avg_price_usd": avg_price,
                "avg_price_krw": avg_krw,
                "min_price_usd": min_price,
                "max_price_usd": max_price,
                "price_gap_krw": 0,
                "exchange_rate": exchange_rate,
            },
            "statistics": {
                "avg_price_30d": avg_krw,
                "total_sales_30d": product.get("weekly_orders", 0) * 4,
                "weekly_orders": product.get("weekly_orders", 0),
                "trending_rank": product.get("rank", 0),
                "price_trend": "활발" if product.get("weekly_orders", 0) > 500 else "보합",
            },
            "price_history": {
                "kream": [],
                "stockx": [{"price": stockx_usd, "number_of_sales": product.get("weekly_orders", 0), "recorded_date": "현재"}],
            }
        }

    except Exception as e:
        return {"error": f"KicksDB 요청 실패: {str(e)}"}


def search_by_sku(sku: str) -> dict:
    """품번(SKU)으로 검색"""
    return search_sneakers(sku, limit=5)
