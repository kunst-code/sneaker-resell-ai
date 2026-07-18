"""
리셀 가격 조회 서비스
우선순위: 1) KicksDB (kicks.dev) → 2) 로컬 DB → 3) RapidAPI (별도 요청 시에만)
"""
import os
import httpx
from datetime import datetime, timedelta
from db.database import get_db
from services.kicksdb_service import get_price_from_kicksdb


def get_rapidapi_key():
    return os.getenv('RAPIDAPI_KEY', '')


RAPIDAPI_HOST = 'sneaker-database-stockx.p.rapidapi.com'


def search_sneaker_api(style_code: str, force_rapidapi: bool = False) -> dict:
    """
    품번으로 가격 조회
    우선순위: KicksDB(StockX 가격) + KREAM 실시간 가격 병합 → 로컬 DB → RapidAPI
    """
    # 1순위: KicksDB (kicks.dev) - StockX 가격
    result = None
    if not force_rapidapi:
        kicksdb_result = get_price_from_kicksdb(style_code)
        if "error" not in kicksdb_result:
            _save_kicksdb_to_local(style_code, kicksdb_result)
            result = kicksdb_result

    # 2순위: 로컬 DB
    if result is None:
        local_result = get_price_from_local_db(style_code)
        if "error" not in local_result:
            result = local_result

    # 3순위: RapidAPI (별도 요청 시에만)
    if result is None and force_rapidapi:
        result = _search_rapidapi(style_code)

    if result is None:
        return {"error": f"'{style_code}'에 대한 데이터를 찾을 수 없습니다."}

    # KREAM 실시간 가격 추가 (비동기적으로 시도, 실패해도 StockX 데이터 유지)
    try:
        from services.kream_service import get_kream_price_for_analysis
        kream_data = get_kream_price_for_analysis(style_code)
        if "error" not in kream_data and kream_data.get('kream_price', 0) > 0:
            result['current_price']['kream'] = kream_data['kream_price']
            result['current_price']['kream_buy'] = kream_data.get('buy_price', 0)
            result['current_price']['kream_sell'] = kream_data.get('sell_price', 0)
            # 차액 계산
            stockx_krw = result['current_price'].get('stockx_krw', 0)
            if stockx_krw > 0:
                result['current_price']['price_gap_krw'] = kream_data['kream_price'] - stockx_krw
            result['kream_url'] = kream_data.get('url', '')
    except Exception as e:
        print(f"⚠️ KREAM 가격 조회 실패 (StockX 데이터 사용): {e}")

    return result


def _save_kicksdb_to_local(style_code: str, kicksdb_data: dict):
    """KicksDB 데이터를 로컬 DB에 캐시"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        sneaker = kicksdb_data.get("sneaker", {})
        price = kicksdb_data.get("current_price", {})
        today = datetime.now().strftime('%Y-%m-%d')

        cursor.execute('''
            INSERT OR REPLACE INTO sneakers (style_code, brand, model_name, colorway, release_date, retail_price, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            sneaker.get('style_code', style_code),
            sneaker.get('brand', ''),
            sneaker.get('model_name', ''),
            sneaker.get('colorway', ''),
            sneaker.get('release_date', ''),
            0,
            sneaker.get('image', '')
        ))

        avg_usd = price.get('avg_price_usd') or 0
        if avg_usd > 0:
            cursor.execute('''
                INSERT INTO price_history (style_code, platform, price, currency, recorded_date)
                VALUES (?, ?, ?, ?, ?)
            ''', (style_code, 'KicksDB', avg_usd, 'USD', today))

            cursor.execute('''
                INSERT INTO price_history (style_code, platform, price, currency, recorded_date)
                VALUES (?, ?, ?, ?, ?)
            ''', (style_code, 'KREAM', price.get('avg_price_krw', avg_usd * 1350), 'KRW', today))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ 로컬 DB 캐시 저장 실패: {e}")


def _search_rapidapi(style_code: str) -> dict:
    """RapidAPI로 검색 (별도 요청 시에만 사용)"""
    rapidapi_key = get_rapidapi_key()
    if not rapidapi_key:
        return {"error": "RAPIDAPI_KEY가 설정되지 않았습니다."}

    try:
        response = httpx.get(
            f'https://{RAPIDAPI_HOST}/search',
            params={'query': style_code, 'limit': '5'},
            headers={
                'X-RapidAPI-Key': rapidapi_key,
                'X-RapidAPI-Host': RAPIDAPI_HOST
            },
            timeout=15.0
        )

        if response.status_code == 200:
            results = response.json()

            if isinstance(results, list) and len(results) > 0:
                sneaker = results[0]
            elif isinstance(results, dict) and results.get('results'):
                sneaker = results['results'][0]
            elif isinstance(results, dict) and results.get('shoeName'):
                sneaker = results
            else:
                return get_price_from_local_db(style_code)

            return _format_api_response(sneaker, style_code)

        elif response.status_code == 429:
            return get_price_from_local_db(style_code)
        else:
            return get_price_from_local_db(style_code)

    except Exception as e:
        print(f"⚠️ RapidAPI 조회 실패: {e}")
        return get_price_from_local_db(style_code)


def _format_api_response(sneaker: dict, style_code: str) -> dict:
    """API 응답을 표준 형식으로 변환"""
    resell_prices = sneaker.get('lowestResellPrice', {})
    stockx_price = resell_prices.get('stockX', 0) or 0
    flightclub_price = resell_prices.get('flightClub', 0) or 0
    goat_price = resell_prices.get('goat', 0) or 0
    stadium_goods_price = resell_prices.get('stadiumGoods', 0) or 0

    # USD → KRW 변환 (환율 1,350원)
    exchange_rate = 1350
    stockx_krw = stockx_price * exchange_rate

    # 최저 해외 가격 (USD)
    overseas_prices = [p for p in [stockx_price, flightclub_price, goat_price, stadium_goods_price] if p > 0]
    lowest_overseas_usd = min(overseas_prices) if overseas_prices else 0
    lowest_overseas_krw = lowest_overseas_usd * exchange_rate

    # KREAM 예상가 (StockX 대비 ±10% 범위로 추정, 실제 KREAM API 없으므로)
    estimated_kream = int(stockx_krw * 1.05) if stockx_krw > 0 else 0

    # 차액 계산
    price_gap = estimated_kream - lowest_overseas_krw if estimated_kream > 0 and lowest_overseas_krw > 0 else 0

    # DB에 가격 이력 저장
    _save_price_to_db(style_code, sneaker, resell_prices, exchange_rate)

    return {
        "source": "rapidapi_sneaker_database_stockx",
        "sneaker": {
            "style_code": sneaker.get('styleID', style_code),
            "brand": sneaker.get('brand', 'N/A'),
            "model_name": sneaker.get('shoeName', 'N/A'),
            "silhouette": sneaker.get('silhouette', ''),
            "colorway": sneaker.get('colorway', 'N/A'),
            "retail_price": sneaker.get('retailPrice', 0),
            "release_date": sneaker.get('releaseDate', ''),
            "thumbnail": sneaker.get('thumbnail', ''),
            "image_links": sneaker.get('imageLinks', []),
        },
        "current_price": {
            "kream": estimated_kream,
            "stockx_usd": stockx_price,
            "stockx_krw": stockx_krw,
            "flightclub_usd": flightclub_price,
            "goat_usd": goat_price,
            "stadium_goods_usd": stadium_goods_price,
            "lowest_overseas_usd": lowest_overseas_usd,
            "lowest_overseas_krw": lowest_overseas_krw,
            "price_gap_krw": price_gap,
            "exchange_rate": exchange_rate,
        },
        "resell_links": sneaker.get('resellLinks', {}),
        "statistics": {
            "avg_price_30d": estimated_kream,
            "total_sales_30d": 0,
            "price_trend": "N/A (실시간 단일 조회)",
        },
        "price_history": {
            "kream": [],
            "stockx": [],
        }
    }


def _save_price_to_db(style_code: str, sneaker: dict, resell_prices: dict, exchange_rate: int):
    """API로 가져온 가격을 로컬 DB에 저장"""
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')

    # 스니커즈 기본 정보 저장
    cursor.execute('''
        INSERT OR IGNORE INTO sneakers (style_code, brand, model_name, colorway, release_date, retail_price, image_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        sneaker.get('styleID', style_code),
        sneaker.get('brand', ''),
        sneaker.get('shoeName', ''),
        sneaker.get('colorway', ''),
        sneaker.get('releaseDate', ''),
        sneaker.get('retailPrice', 0),
        sneaker.get('thumbnail', '')
    ))

    # StockX 가격 저장
    stockx_price = resell_prices.get('stockX', 0)
    if stockx_price:
        cursor.execute('''
            INSERT INTO price_history (style_code, platform, price, currency, recorded_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (style_code, 'StockX', stockx_price, 'USD', today))

        # KRW 환산 가격도 저장
        cursor.execute('''
            INSERT INTO price_history (style_code, platform, price, currency, recorded_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (style_code, 'KREAM', stockx_price * exchange_rate * 1.05, 'KRW', today))

    conn.commit()
    conn.close()


def get_price_from_local_db(style_code: str) -> dict:
    """로컬 SQLite DB에서 가격 이력 조회 (price_history + daily_prices 통합)"""
    conn = get_db()
    cursor = conn.cursor()

    # 스니커즈 기본 정보
    cursor.execute('SELECT * FROM sneakers WHERE style_code = ?', (style_code,))
    sneaker = cursor.fetchone()

    if not sneaker:
        conn.close()
        return {"error": f"품번 '{style_code}'에 대한 데이터를 찾을 수 없습니다."}

    # KREAM 최근 가격
    cursor.execute('''
        SELECT price, number_of_sales, recorded_date 
        FROM price_history 
        WHERE style_code = ? AND platform = 'KREAM'
        ORDER BY recorded_date DESC 
        LIMIT 30
    ''', (style_code,))
    kream_prices = [dict(row) for row in cursor.fetchall()]

    # StockX 최근 가격
    cursor.execute('''
        SELECT price, number_of_sales, recorded_date 
        FROM price_history 
        WHERE style_code = ? AND platform = 'StockX'
        ORDER BY recorded_date DESC 
        LIMIT 30
    ''', (style_code,))
    stockx_prices = [dict(row) for row in cursor.fetchall()]

    # price_history에 데이터가 없으면 daily_prices 테이블에서 가져오기
    if not kream_prices and not stockx_prices:
        cursor.execute('''
            SELECT stockx_price_usd, goat_price_usd, flightclub_price_usd, avg_price_krw, collected_date
            FROM daily_prices
            WHERE style_code = ?
            ORDER BY collected_date DESC
            LIMIT 30
        ''', (style_code,))
        daily_rows = [dict(row) for row in cursor.fetchall()]

        # trending 순위 정보도 가져오기
        cursor.execute('''
            SELECT rank FROM trending_sneakers
            WHERE style_code = ? 
            ORDER BY collected_date DESC LIMIT 1
        ''', (style_code,))
        rank_row = cursor.fetchone()
        trending_rank = dict(rank_row)['rank'] if rank_row else 0

        if daily_rows:
            conn.close()
            # daily_prices 기반 응답
            current = daily_rows[0]
            current_stockx = current.get('stockx_price_usd') or 0
            current_goat = current.get('goat_price_usd') or 0
            current_flightclub = current.get('flightclub_price_usd') or 0
            current_krw = current.get('avg_price_krw') or 0
            exchange_rate = 1350
            stockx_krw = current_stockx * exchange_rate

            # 30일 이력 구성
            history_krw = [{"price": r.get('avg_price_krw', 0), "number_of_sales": 0, "recorded_date": r['collected_date']} for r in daily_rows if r.get('avg_price_krw')]
            history_usd = [{"price": r.get('stockx_price_usd', 0), "number_of_sales": 0, "recorded_date": r['collected_date']} for r in daily_rows if r.get('stockx_price_usd')]

            avg_krw = sum(r.get('avg_price_krw', 0) for r in daily_rows if r.get('avg_price_krw')) / max(len([r for r in daily_rows if r.get('avg_price_krw')]), 1)

            # 거래량 추정: 인기 순위가 높으면 거래 활발로 간주
            estimated_sales = max(100 - (trending_rank - 1) * 10, 10) if trending_rank > 0 else 0
            trend_note = f"인기 순위 {trending_rank}위" if trending_rank > 0 else ""

            return {
                "source": "local_db",
                "sneaker": {
                    "style_code": dict(sneaker)['style_code'],
                    "brand": dict(sneaker)['brand'],
                    "model_name": dict(sneaker)['model_name'],
                    "colorway": dict(sneaker)['colorway'],
                    "retail_price": dict(sneaker)['retail_price'],
                },
                "current_price": {
                    "kream": current_krw,
                    "stockx_usd": current_stockx,
                    "goat_usd": current_goat,
                    "flightclub_usd": current_flightclub,
                    "stockx_krw": stockx_krw,
                    "price_gap_krw": current_krw - stockx_krw if current_krw and stockx_krw else 0,
                    "exchange_rate": exchange_rate,
                },
                "statistics": {
                    "avg_price_30d": round(avg_krw),
                    "total_sales_30d": estimated_sales,
                    "price_trend": trend_note if trend_note else ("상승" if len(daily_rows) > 1 and (daily_rows[0].get('avg_price_krw') or 0) > (daily_rows[-1].get('avg_price_krw') or 0) else "보합"),
                    "trending_rank": trending_rank,
                    "data_days": len(daily_rows),
                },
                "price_history": {
                    "kream": history_krw,
                    "stockx": history_usd,
                }
            }

    conn.close()

    # 현재 시세 및 차액 계산
    current_kream = kream_prices[0]['price'] if kream_prices else 0
    current_stockx = stockx_prices[0]['price'] if stockx_prices else 0
    exchange_rate = 1350
    stockx_krw = current_stockx * exchange_rate
    price_gap = current_kream - stockx_krw

    # 거래량 합산
    total_sales_30d = sum(p.get('number_of_sales', 0) for p in kream_prices)

    # 30일 평균가 계산
    avg_price_30d = sum(p['price'] for p in kream_prices) / len(kream_prices) if kream_prices else 0

    return {
        "source": "local_db",
        "sneaker": {
            "style_code": dict(sneaker)['style_code'],
            "brand": dict(sneaker)['brand'],
            "model_name": dict(sneaker)['model_name'],
            "colorway": dict(sneaker)['colorway'],
            "retail_price": dict(sneaker)['retail_price'],
        },
        "current_price": {
            "kream": current_kream,
            "stockx_usd": current_stockx,
            "stockx_krw": stockx_krw,
            "price_gap_krw": price_gap,
            "exchange_rate": exchange_rate,
        },
        "statistics": {
            "avg_price_30d": round(avg_price_30d),
            "total_sales_30d": total_sales_30d,
            "price_trend": "상승" if kream_prices and kream_prices[0]['price'] > avg_price_30d else "하락",
        },
        "price_history": {
            "kream": kream_prices[:30],
            "stockx": stockx_prices[:30],
        }
    }


def get_full_price_history(style_code: str) -> list:
    """예측 모델용 전체 가격 이력 반환"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT recorded_date as ds, price as y
        FROM price_history 
        WHERE style_code = ? AND platform = 'KREAM'
        ORDER BY recorded_date ASC
    ''', (style_code,))

    history = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return history
