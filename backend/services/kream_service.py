"""
KREAM 실시간 가격 크롤링 서비스
Playwright (headless Chrome + stealth)로 KREAM에서 가격 추출
"""
import re
import json
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth


def _create_stealth_page(playwright):
    """봇 탐지 우회용 stealth 브라우저/페이지 생성"""
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        viewport={"width": 1440, "height": 900},
        locale="ko-KR",
    )
    page = context.new_page()
    stealth = Stealth()
    stealth.apply_stealth_sync(page)
    return browser, page


def search_kream(query: str) -> dict:
    """
    KREAM에서 품번/모델명으로 검색 → 상품 페이지 → 가격 추출
    """
    try:
        with sync_playwright() as p:
            browser, page = _create_stealth_page(p)

            # 홈 먼저 방문 (쿠키 획득 필요)
            page.goto("https://kream.co.kr", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(2000)

            # 검색
            search_url = f"https://kream.co.kr/search?keyword={query}&tab=products"
            page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(4000)

            # 상품 링크 추출
            content = page.content()
            matches = re.findall(r'href="(/products/\d+)"', content)

            if not matches:
                browser.close()
                return {"error": f"KREAM에서 '{query}' 검색 결과 없음"}

            # 첫 상품 페이지 이동
            product_url = f"https://kream.co.kr{matches[0]}"
            page.goto(product_url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(4000)

            result = _extract_from_html(page)
            result['url'] = product_url
            browser.close()
            return result

    except Exception as e:
        return {"error": f"KREAM 크롤링 실패: {str(e)}"}


def get_kream_price(product_id: str) -> dict:
    """KREAM 상품 ID로 직접 가격 조회"""
    try:
        with sync_playwright() as p:
            browser, page = _create_stealth_page(p)

            url = f"https://kream.co.kr/products/{product_id}"
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(4000)

            result = _extract_from_html(page)
            result['url'] = url
            browser.close()
            return result

    except Exception as e:
        return {"error": f"KREAM 크롤링 실패: {str(e)}"}


def _extract_from_html(page) -> dict:
    """KREAM 상품 페이지 HTML에서 가격/정보 추출"""
    data = {
        "source": "kream",
        "name": "",
        "style_code": "",
        "current_price": 0,
        "release_price": 0,
        "trade_volume": "",
    }

    content = page.content()

    # 상품명 추출 (title 태그에서)
    title = page.title()
    if title and '|' in title:
        data['name'] = title.split('|')[0].strip()
    elif title:
        data['name'] = title

    # 모델번호/품번 추출
    model_match = re.search(r'모델번호\s*</[^>]+>\s*<[^>]+>([^<]+)', content)
    if model_match:
        data['style_code'] = model_match.group(1).strip()

    # 가격 추출: "NNN,NNN원" 패턴
    # KREAM 페이지에서 가격은 보통 발매가, 현재 거래가, 구매가 순서
    all_prices = re.findall(r'([\d,]+)\s*원', content)
    numeric_prices = []
    for p in all_prices:
        try:
            val = int(p.replace(',', ''))
            if 10000 < val < 100000000:  # 1만원~1억원
                numeric_prices.append(val)
        except ValueError:
            pass

    if numeric_prices:
        # 발매가 패턴 (보통 "발매가 NNN,NNN원")
        release_match = re.search(r'발매가\s*([\d,]+)\s*원', content)
        if release_match:
            data['release_price'] = int(release_match.group(1).replace(',', ''))

        # 현재 거래가: 발매가가 아닌 가격 중 가장 처음 나오는 것
        # 또는 할인가 표시된 가격 (28% 221,000원 같은)
        discount_match = re.search(r'\d+%\s*([\d,]+)\s*원', content)
        if discount_match:
            data['current_price'] = int(discount_match.group(1).replace(',', ''))
        else:
            # 발매가 제외한 나머지 가격
            non_release = [p for p in numeric_prices if p != data.get('release_price', 0)]
            if non_release:
                data['current_price'] = non_release[0]
            elif numeric_prices:
                data['current_price'] = numeric_prices[0]

    # 거래량
    volume_match = re.search(r'최근\s*([\d,]+)건', content)
    if volume_match:
        data['trade_volume'] = volume_match.group(1)

    # 거래가 (거래 3.9만 ▲ 10,000원)
    trade_match = re.search(r'거래\s*([\d.]+)만', content)
    if trade_match:
        # 거래가가 "만" 단위면 변환
        trade_val = float(trade_match.group(1)) * 10000
        if data['current_price'] == 0:
            data['current_price'] = int(trade_val)

    return data


def get_kream_price_for_analysis(style_code: str) -> dict:
    """
    분석 파이프라인용 - 품번으로 KREAM 가격 조회
    """
    result = search_kream(style_code)

    if "error" in result:
        return result

    kream_price = result.get('current_price', 0)
    if kream_price == 0:
        return {"error": "KREAM 가격을 가져올 수 없습니다."}

    return {
        "source": "kream_live",
        "kream_price": kream_price,
        "name": result.get('name', ''),
        "style_code": result.get('style_code', style_code),
        "release_price": result.get('release_price', 0),
        "trade_volume": result.get('trade_volume', ''),
        "url": result.get('url', ''),
    }
