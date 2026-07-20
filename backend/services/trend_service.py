"""
트렌드 분석 기반 구매 추천 서비스
유튜브/구글 트렌드 분석 + KicksDB 실시간 가격을 결합하여 Top 10 구매 추천
1시간 단위로 캐싱하여 DB에 저장
"""
import os
import json
import httpx
from datetime import datetime, timedelta
from db.database import get_db
from services.kicksdb_service import search_sneakers, get_api_key

KICKSDB_API_BASE = "https://api.kicks.dev/v3"
CACHE_HOURS = 24  # 24시간 캐싱


def get_trend_recommendations() -> dict:
    """
    트렌드 분석 기반 스니커즈 구매 추천 Top 10
    1시간 이내 캐시 있으면 DB에서 반환, 없으면 새로 생성
    """
    # 캐시 확인
    cached = _get_cached_recommendations()
    if cached:
        return cached

    # 새로 생성
    openai_key = os.getenv('OPENAI_API_KEY', '')
    if not openai_key:
        return {"error": "OPENAI_API_KEY가 설정되지 않았습니다."}

    # Step 1: GPT에게 트렌드 분석 + 추천 요청
    trend_picks = _get_ai_trend_picks(openai_key)
    if "error" in trend_picks:
        return trend_picks

    # Step 2: 각 추천 모델의 실시간 가격 조회
    recommendations = []
    for pick in trend_picks.get('picks', []):
        sku = pick.get('style_code', '')
        model_name = pick.get('model_name', '')

        # KicksDB에서 가격 조회
        price_info = _get_price_for_pick(sku or model_name)

        recommendations.append({
            "rank": pick.get('rank', 0),
            "model_name": pick.get('model_name', ''),
            "brand": pick.get('brand', ''),
            "style_code": sku,
            "colorway": pick.get('colorway', ''),
            "reason": pick.get('reason', ''),
            "trend_source": pick.get('trend_source', ''),
            "buy_signal": pick.get('buy_signal', 'HOLD'),
            "price_usd": price_info.get('min_price'),
            "avg_price_usd": price_info.get('avg_price'),
            "price_krw": round((price_info.get('min_price') or 0) * 1350),
            "weekly_orders": price_info.get('weekly_orders', 0),
            "price_trend": pick.get('price_trend', '보합'),
            "image": price_info.get('image', ''),
        })

    result = {
        "success": True,
        "trend_analysis": trend_picks.get('analysis', ''),
        "recommendations": recommendations,
        "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M'),
    }

    # DB에 캐시 저장
    _save_recommendations_cache(result)

    return result


def _get_cached_recommendations() -> dict:
    """1시간 이내 캐시된 추천 결과 반환"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trend_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

        cutoff = (datetime.now() - timedelta(hours=CACHE_HOURS)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            SELECT data FROM trend_cache
            WHERE created_at > ?
            ORDER BY created_at DESC LIMIT 1
        ''', (cutoff,))
        row = cursor.fetchone()
        conn.close()

        if row:
            cached = json.loads(row['data'])
            cached['from_cache'] = True
            return cached
    except Exception as e:
        print(f"⚠️ 캐시 조회 실패: {e}")
    return None


def _save_recommendations_cache(result: dict):
    """추천 결과를 DB에 캐시"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trend_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # 오래된 캐시 삭제 (24시간 이상)
        cutoff = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('DELETE FROM trend_cache WHERE created_at < ?', (cutoff,))
        # 새 캐시 저장
        cursor.execute('INSERT INTO trend_cache (data) VALUES (?)', (json.dumps(result, ensure_ascii=False),))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ 캐시 저장 실패: {e}")


def _get_ai_trend_picks(api_key: str) -> dict:
    """GPT-4o에게 한국 KREAM 시장 기준 트렌드 분석 + 추천 Top 10 요청"""
    prompt = """당신은 한국 스니커즈 리셀 시장(KREAM, 솔드아웃) 전문가입니다.
2026년 7월 현재 한국에서 인기 있는 스니커즈 트렌드를 분석하고, KREAM에서 구매/리셀 수익이 기대되는 스니커즈 Top 10을 추천해주세요.

중요: 반드시 한국 KREAM에서 실제 거래되는 모델만 추천해주세요.
해외 전용 모델(미국/유럽 한정)은 제외합니다.

한국 KREAM 시장 현황:
- New Balance 992, 990v6, 2002R, 1906 시리즈: 국내 최고 인기, 가격 꾸준히 상승
- Nike Dunk Low: 파스텔/클래식 컬러웨이 여전히 인기
- Asics Gel-Kayano 14, Gel-1130: MZ세대 선호, 가격 상승
- Jordan 1 Low: Travis Scott 콜라보 + 클래식 컬러 인기
- Adidas Samba, Gazelle: 레트로 무드 지속
- Nike Air Force 1: 발매가 이하 거래 (저점 매수 기회)
- Salomon XT-6: 고프코어 트렌드 지속
- 뉴발란스 x JJJJound, WTAPS 콜라보: 프리미엄 유지
- Jordan 4 Bred Reimagined, Military Blue: 국내 인기 높음
- Converse Chuck 70: 기본템 수요 꾸준

반드시 아래 JSON 형식으로 응답해주세요:
{
    "analysis": "현재 한국 KREAM 시장 트렌드 요약 (3~4문장, 한국어)",
    "generated_at": "2026-07-18",
    "picks": [
        {
            "rank": 1,
            "model_name": "정식 모델명 (한국에서 통용되는 이름)",
            "brand": "브랜드",
            "style_code": "품번 (KREAM에서 검색 가능한 모델번호)",
            "colorway": "컬러웨이",
            "reason": "추천 이유 (1~2문장, 한국어, KREAM 시장 관점)",
            "trend_source": "KREAM/인스타그램/유튜브/커뮤니티 중 출처",
            "buy_signal": "BUY 또는 HOLD",
            "price_trend": "상승/하락/보합"
        }
    ]
}

10개를 추천해주세요.
- 반드시 KREAM에서 검색 가능한 실제 품번(모델번호)을 사용하세요
- 예: M992GR, U990GL6, M2002RXA, 1201A019, DD1391-100
- 한국 소비자가 실제로 구매하는 모델 위주
JSON만 출력하세요."""

    try:
        response = httpx.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'gpt-4o',
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 2000,
                'temperature': 0.5
            },
            timeout=30.0
        )

        if response.status_code != 200:
            return {"error": f"OpenAI API 오류: {response.status_code}"}

        result_text = response.json()['choices'][0]['message']['content']
        cleaned = result_text.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[1]
            cleaned = cleaned.rsplit('```', 1)[0]

        return json.loads(cleaned)

    except json.JSONDecodeError as e:
        return {"error": f"AI 응답 파싱 실패: {str(e)}"}
    except Exception as e:
        return {"error": f"트렌드 분석 실패: {str(e)}"}


def _get_price_for_pick(query: str) -> dict:
    """KicksDB에서 모델 가격 조회"""
    if not query or not get_api_key():
        return {}

    try:
        result = search_sneakers(query, limit=1)
        if result.get('success') and result.get('products'):
            p = result['products'][0]
            return {
                "min_price": p.get('min_price'),
                "avg_price": p.get('avg_price'),
                "max_price": p.get('max_price'),
                "weekly_orders": p.get('weekly_orders', 0),
                "image": p.get('image', ''),
            }
    except Exception:
        pass
    return {}
