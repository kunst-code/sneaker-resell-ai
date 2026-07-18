"""
데이터 수집 서비스 - RapidAPI에서 하루 1회 인기 스니커즈 데이터를 수집하여 로컬 DB에 저장
호출 최소화: 마지막 수집 후 24시간 이내면 스킵
"""
import os
import httpx
from datetime import datetime, timedelta
from db.database import get_db

RAPIDAPI_HOST = 'sneaker-database-stockx.p.rapidapi.com'


def get_rapidapi_key():
    return os.getenv('RAPIDAPI_KEY', '')


def should_collect() -> bool:
    """마지막 수집으로부터 24시간이 지났는지 확인"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT collected_at FROM collection_log 
        WHERE collection_type = 'trending' AND status = 'success'
        ORDER BY collected_at DESC LIMIT 1
    ''')
    row = cursor.fetchone()
    conn.close()

    if not row:
        return True

    last_collected = datetime.fromisoformat(row['collected_at'])
    return datetime.now() - last_collected > timedelta(hours=24)


def collect_trending_data(force: bool = False) -> dict:
    """
    RapidAPI에서 인기 스니커즈 데이터 수집 → 로컬 DB 저장
    force=True: 24시간 체크 무시하고 강제 수집
    """
    if not force and not should_collect():
        return {"status": "skipped", "message": "마지막 수집 후 24시간이 지나지 않았습니다."}

    api_key = get_rapidapi_key()
    if not api_key:
        return {"error": "RAPIDAPI_KEY가 설정되지 않았습니다."}

    today = datetime.now().strftime('%Y-%m-%d')
    collected_items = []
    errors = []

    # RapidAPI에서 인기 상품 목록 가져오기 (파라미터 없이 호출 = 인기순)
    try:
        results = _fetch_trending_from_rapidapi(api_key)
        for rank, sneaker in enumerate(results, 1):
            saved = _save_trending_item(sneaker, rank, today)
            if saved:
                collected_items.append(saved)
                _save_daily_price(sneaker, today)
    except Exception as e:
        errors.append(f"trending fetch: {str(e)}")

    # 수집 로그 기록
    _log_collection(len(collected_items), errors)

    return {
        "status": "success",
        "collected": len(collected_items),
        "errors": errors,
        "date": today,
    }


def _fetch_trending_from_rapidapi(api_key: str) -> list:
    """RapidAPI에서 인기 스니커즈 목록 가져오기 (파라미터 없이 = 인기순 반환)"""
    response = httpx.get(
        f'https://{RAPIDAPI_HOST}/getproducts',
        headers={
            'X-RapidAPI-Key': api_key,
            'X-RapidAPI-Host': RAPIDAPI_HOST
        },
        timeout=20.0
    )

    if response.status_code != 200:
        print(f"⚠️ RapidAPI 오류: {response.status_code}")
        return []

    data = response.json()
    if isinstance(data, list):
        return data[:30]  # 최대 30개
    return []


def _save_trending_item(sneaker: dict, rank: int, date: str) -> dict:
    """트렌딩 스니커즈를 DB에 저장"""
    style_code = sneaker.get('styleID', '')
    if not style_code:
        return None

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT OR REPLACE INTO trending_sneakers 
            (style_code, brand, model_name, colorway, release_date, retail_price, image_url, rank, collected_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            style_code,
            sneaker.get('brand', ''),
            sneaker.get('shoeName', ''),
            sneaker.get('colorway', ''),
            sneaker.get('releaseDate', ''),
            sneaker.get('retailPrice', 0),
            sneaker.get('thumbnail', ''),
            rank,
            date,
        ))

        # sneakers 테이블에도 추가/업데이트
        cursor.execute('''
            INSERT OR REPLACE INTO sneakers 
            (style_code, brand, model_name, colorway, release_date, retail_price, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            style_code,
            sneaker.get('brand', ''),
            sneaker.get('shoeName', ''),
            sneaker.get('colorway', ''),
            sneaker.get('releaseDate', ''),
            sneaker.get('retailPrice', 0),
            sneaker.get('thumbnail', ''),
        ))

        conn.commit()
        conn.close()

        return {
            "style_code": style_code,
            "model_name": sneaker.get('shoeName', ''),
            "brand": sneaker.get('brand', ''),
        }
    except Exception as e:
        conn.close()
        print(f"⚠️ DB 저장 실패 ({style_code}): {e}")
        return None


def _save_daily_price(sneaker: dict, date: str):
    """일별 가격 저장"""
    style_code = sneaker.get('styleID', '')
    if not style_code:
        return

    resell_prices = sneaker.get('lowestResellPrice', {})
    stockx = resell_prices.get('stockX', 0) or 0
    goat = resell_prices.get('goat', 0) or 0
    flightclub = resell_prices.get('flightClub', 0) or 0

    # 평균 KRW 계산
    prices = [p for p in [stockx, goat, flightclub] if p > 0]
    avg_usd = sum(prices) / len(prices) if prices else 0
    avg_krw = round(avg_usd * 1350)

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT OR REPLACE INTO daily_prices 
            (style_code, stockx_price_usd, goat_price_usd, flightclub_price_usd, avg_price_krw, collected_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (style_code, stockx, goat, flightclub, avg_krw, date))
        conn.commit()
    except Exception as e:
        print(f"⚠️ 가격 저장 실패 ({style_code}): {e}")
    finally:
        conn.close()


def _log_collection(count: int, errors: list):
    """수집 로그 저장"""
    conn = get_db()
    cursor = conn.cursor()
    status = 'success' if count > 0 else ('error' if errors else 'empty')
    cursor.execute('''
        INSERT INTO collection_log (collection_type, status, items_collected)
        VALUES (?, ?, ?)
    ''', ('trending', status, count))
    conn.commit()
    conn.close()


def get_trending_from_db(limit: int = 20) -> dict:
    """로컬 DB에서 최신 트렌딩 목록 조회 (트렌딩 테이블 비면 sneakers 테이블 폴백)"""
    conn = get_db()
    cursor = conn.cursor()

    # 가장 최근 수집일의 데이터 가져오기
    cursor.execute('''
        SELECT ts.*, dp.stockx_price_usd, dp.goat_price_usd, dp.flightclub_price_usd, dp.avg_price_krw
        FROM trending_sneakers ts
        LEFT JOIN daily_prices dp ON ts.style_code = dp.style_code 
            AND dp.collected_date = (SELECT MAX(collected_date) FROM daily_prices WHERE style_code = ts.style_code)
        WHERE ts.collected_date = (SELECT MAX(collected_date) FROM trending_sneakers)
        ORDER BY ts.rank ASC
        LIMIT ?
    ''', (limit,))

    rows = cursor.fetchall()

    # 트렌딩 데이터가 없으면 sneakers 테이블에서 폴백
    if not rows:
        cursor.execute('''
            SELECT s.style_code, s.brand, s.model_name, s.colorway, s.release_date, 
                   s.retail_price, s.image_url,
                   (SELECT ph.price FROM price_history ph WHERE ph.style_code = s.style_code AND ph.platform = 'StockX' ORDER BY ph.recorded_date DESC LIMIT 1) as stockx_price_usd,
                   NULL as goat_price_usd, 
                   NULL as flightclub_price_usd,
                   (SELECT ph2.price FROM price_history ph2 WHERE ph2.style_code = s.style_code AND ph2.platform = 'KREAM' ORDER BY ph2.recorded_date DESC LIMIT 1) as avg_price_krw
            FROM sneakers s
            ORDER BY s.id ASC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()

    conn.close()

    if not rows:
        return {"success": False, "trending": [], "message": "수집된 데이터가 없습니다. '데이터 수집하기' 버튼을 눌러주세요."}

    trending = []
    for row in rows:
        row_dict = dict(row)
        trending.append({
            "style_code": row_dict.get('style_code', ''),
            "brand": row_dict.get('brand', ''),
            "model_name": row_dict.get('model_name', ''),
            "colorway": row_dict.get('colorway', ''),
            "release_date": row_dict.get('release_date', ''),
            "release_year": (row_dict.get('release_date') or '')[:4] or 'N/A',
            "retail_price": row_dict.get('retail_price', 0),
            "image": row_dict.get('image_url', ''),
            "rank": row_dict.get('rank', 0),
            "stockx_price_usd": row_dict.get('stockx_price_usd'),
            "goat_price_usd": row_dict.get('goat_price_usd'),
            "avg_price_krw": row_dict.get('avg_price_krw'),
            "collected_date": row_dict.get('collected_date', ''),
        })

    return {"success": True, "trending": trending, "count": len(trending)}


def get_price_history_30d(style_code: str) -> dict:
    """특정 스니커즈의 최근 30일 가격 이력 조회"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT style_code, stockx_price_usd, goat_price_usd, flightclub_price_usd, avg_price_krw, collected_date
        FROM daily_prices
        WHERE style_code = ?
        ORDER BY collected_date DESC
        LIMIT 30
    ''', (style_code,))

    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not rows:
        return {"error": f"'{style_code}'의 가격 이력이 없습니다."}

    # 오래된 순서로 정렬
    rows.reverse()

    current = rows[-1] if rows else {}
    first = rows[0] if rows else {}
    change_pct = 0
    if first.get('avg_price_krw') and current.get('avg_price_krw') and first['avg_price_krw'] > 0:
        change_pct = round((current['avg_price_krw'] - first['avg_price_krw']) / first['avg_price_krw'] * 100, 1)

    return {
        "success": True,
        "style_code": style_code,
        "history": rows,
        "summary": {
            "current_price_krw": current.get('avg_price_krw', 0),
            "current_stockx_usd": current.get('stockx_price_usd', 0),
            "days_tracked": len(rows),
            "change_pct_30d": change_pct,
            "trend": "상승" if change_pct > 0 else ("하락" if change_pct < 0 else "보합"),
        }
    }


def get_last_collection_info() -> dict:
    """마지막 수집 정보"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM collection_log 
        ORDER BY collected_at DESC LIMIT 1
    ''')
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"last_collected": None, "message": "아직 수집된 적 없음"}

    row_dict = dict(row)
    return {
        "last_collected": row_dict['collected_at'],
        "status": row_dict['status'],
        "items": row_dict['items_collected'],
    }
