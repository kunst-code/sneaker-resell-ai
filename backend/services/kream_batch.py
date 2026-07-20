"""
KREAM 배치 크롤링 서비스
하루 1회 새벽에 실행하여 인기/트렌드 상품의 KREAM 가격을 DB에 저장
로컬에서만 실행 (서버 배포와 분리)
"""
import re
import time
import random
from datetime import datetime, timedelta
from db.database import get_db

try:
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def collect_kream_prices(sku_list: list) -> dict:
    """
    SKU 목록에 대해 KREAM 가격을 배치 수집
    하루 1회 실행용 — 5~15초 간격으로 안전하게 크롤링
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {"error": "playwright 미설치. 로컬에서만 실행 가능합니다."}

    today = datetime.now().strftime('%Y-%m-%d')
    results = []
    errors = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
                viewport={"width": 1440, "height": 900},
                locale="ko-KR",
            )
            page = context.new_page()
            stealth = Stealth()
            stealth.apply_stealth_sync(page)

            # 쿠키 획득: 홈 먼저 방문
            print("  KREAM 홈 방문 (쿠키 획득)...")
            page.goto("https://kream.co.kr", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(3000)

            for i, sku in enumerate(sku_list):
                print(f"  [{i+1}/{len(sku_list)}] {sku} 검색 중...")

                try:
                    price_data = _fetch_kream_price(page, sku)
                    if price_data and price_data.get('price', 0) > 0:
                        _save_kream_price(sku, price_data, today)
                        results.append(price_data)
                        print(f"    ✅ {price_data['name']}: {price_data['price']:,}원")
                    else:
                        errors.append(f"{sku}: 가격 없음")
                        print(f"    ⚠️ 가격 못 찾음")
                except Exception as e:
                    errors.append(f"{sku}: {str(e)}")
                    print(f"    ❌ 에러: {e}")

                # 안전 딜레이 (5~15초 랜덤)
                if i < len(sku_list) - 1:
                    delay = random.uniform(5, 15)
                    print(f"    ⏳ {delay:.1f}초 대기...")
                    time.sleep(delay)

            browser.close()

    except Exception as e:
        return {"error": f"브라우저 실행 실패: {str(e)}"}

    # 수집 로그
    _log_kream_collection(len(results), errors)

    return {
        "status": "success",
        "collected": len(results),
        "errors": len(errors),
        "error_details": errors[:5],
        "date": today,
    }


def _fetch_kream_price(page, sku: str) -> dict:
    """단일 상품 KREAM 가격 조회"""
    # 검색
    search_url = f"https://kream.co.kr/search?keyword={sku}&tab=products"
    page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(3000)

    content = page.content()
    matches = re.findall(r'href="(/products/\d+)"', content)

    if not matches:
        return None

    # 상품 페이지
    product_url = f"https://kream.co.kr{matches[0]}"
    page.goto(product_url, wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(3000)

    content = page.content()

    # 상품명
    title = page.title()
    name = title.split('|')[0].strip() if '|' in title else title

    # 가격 추출
    current_price = 0
    release_price = 0

    # 할인가 (28% 221,000원)
    discount_match = re.search(r'\d+%\s*([\d,]+)\s*원', content)
    if discount_match:
        current_price = int(discount_match.group(1).replace(',', ''))

    # 발매가
    release_match = re.search(r'발매가\s*([\d,]+)\s*원', content)
    if release_match:
        release_price = int(release_match.group(1).replace(',', ''))

    # 할인가 없으면 일반 가격
    if current_price == 0:
        all_prices = re.findall(r'([\d,]+)\s*원', content)
        for p in all_prices:
            val = int(p.replace(',', ''))
            if 10000 < val < 10000000 and val != release_price:
                current_price = val
                break

    # 거래량
    trade_volume = 0
    volume_match = re.search(r'최근\s*([\d,]+)건', content)
    if volume_match:
        trade_volume = int(volume_match.group(1).replace(',', ''))

    return {
        "sku": sku,
        "name": name,
        "price": current_price,
        "release_price": release_price,
        "trade_volume": trade_volume,
        "product_url": product_url,
    }


def _save_kream_price(sku: str, data: dict, date: str):
    """KREAM 가격을 DB에 저장"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kream_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            style_code TEXT NOT NULL,
            product_name TEXT,
            kream_price INTEGER NOT NULL,
            release_price INTEGER DEFAULT 0,
            trade_volume INTEGER DEFAULT 0,
            kream_url TEXT,
            collected_date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(style_code, collected_date)
        )
    ''')

    cursor.execute('''
        INSERT OR REPLACE INTO kream_prices 
        (style_code, product_name, kream_price, release_price, trade_volume, kream_url, collected_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (sku, data['name'], data['price'], data.get('release_price', 0),
          data.get('trade_volume', 0), data.get('product_url', ''), date))

    conn.commit()
    conn.close()


def _log_kream_collection(count: int, errors: list):
    """수집 로그"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS collection_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_type TEXT NOT NULL,
            status TEXT NOT NULL,
            items_collected INTEGER DEFAULT 0,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    status = 'success' if count > 0 else 'error'
    cursor.execute('INSERT INTO collection_log (collection_type, status, items_collected) VALUES (?, ?, ?)',
                   ('kream_batch', status, count))
    conn.commit()
    conn.close()


def get_kream_price_from_db(style_code: str) -> dict:
    """DB에서 KREAM 가격 조회 (웹 서비스용 — 크롤링 없이 즉시 반환)"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kream_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            style_code TEXT NOT NULL,
            product_name TEXT,
            kream_price INTEGER NOT NULL,
            release_price INTEGER DEFAULT 0,
            trade_volume INTEGER DEFAULT 0,
            kream_url TEXT,
            collected_date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(style_code, collected_date)
        )
    ''')
    conn.commit()

    cursor.execute('''
        SELECT * FROM kream_prices 
        WHERE style_code = ?
        ORDER BY collected_date DESC LIMIT 1
    ''', (style_code,))
    row = cursor.fetchone()

    # 30일 이력
    cursor.execute('''
        SELECT kream_price, collected_date FROM kream_prices
        WHERE style_code = ?
        ORDER BY collected_date DESC LIMIT 30
    ''', (style_code,))
    history = [dict(r) for r in cursor.fetchall()]

    conn.close()

    if not row:
        return None

    row_dict = dict(row)
    return {
        "kream_price": row_dict['kream_price'],
        "release_price": row_dict.get('release_price', 0),
        "trade_volume": row_dict.get('trade_volume', 0),
        "product_name": row_dict.get('product_name', ''),
        "kream_url": row_dict.get('kream_url', ''),
        "collected_date": row_dict.get('collected_date', ''),
        "history": history,
    }


def get_target_skus() -> list:
    """수집 대상 SKU 목록 (인기 + 트렌드)"""
    skus = set()

    # 1. KicksDB 인기 목록에서 SKU 가져오기
    try:
        from services.kicksdb_service import get_trending_sneakers, get_api_key
        if get_api_key():
            result = get_trending_sneakers(limit=20)
            if result.get('trending'):
                for item in result['trending']:
                    sku = item.get('sku', '')
                    if sku:
                        skus.add(sku)
    except Exception:
        pass

    # 2. DB에 있는 기존 스니커즈
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT style_code FROM sneakers LIMIT 20')
        for row in cursor.fetchall():
            if row['style_code']:
                skus.add(row['style_code'])
        conn.close()
    except Exception:
        pass

    # 3. 기본 인기 품번
    default_skus = [
        'DD1391-100', 'DZ5485-612', 'FQ8138-600', 'DM7866-162',
        'HQ6448', 'CW2288-111', 'U992GY', 'M1906AD',
    ]
    skus.update(default_skus)

    return list(skus)[:30]  # 최대 30개
