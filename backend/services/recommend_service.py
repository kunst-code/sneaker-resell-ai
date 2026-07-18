"""
LLM 기반 최종 추천 리포트 생성 서비스
"""
import os
import json
import httpx

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')


def generate_recommendation(sneaker_info: dict, price_data: dict, forecast_data: dict) -> dict:
    """LLM을 사용하여 종합 추천 리포트 생성"""
    context = _build_context(sneaker_info, price_data, forecast_data)

    openai_key = os.getenv('OPENAI_API_KEY', '')
    anthropic_key = os.getenv('ANTHROPIC_API_KEY', '')

    if anthropic_key:
        return _recommend_with_claude(context, anthropic_key)
    elif openai_key:
        return _recommend_with_openai(context, openai_key)
    else:
        return _generate_demo_recommendation(sneaker_info, price_data, forecast_data)


def _build_context(sneaker_info: dict, price_data: dict, forecast_data: dict) -> str:
    """LLM에게 전달할 컨텍스트 구성"""
    def fmt_price(val, suffix='원'):
        """숫자면 쉼표 포맷, 아니면 그대로"""
        if isinstance(val, (int, float)) and val != 0:
            return f"{int(val):,}{suffix}"
        return 'N/A'

    def fmt_usd(val):
        if isinstance(val, (int, float)) and val != 0:
            return f"${val:,.0f}"
        return 'N/A'

    cp = price_data.get('current_price', {})
    stats = price_data.get('statistics', {})
    summary = forecast_data.get('summary', {})

    context = f"""## 분석 대상 스니커즈 정보
- 브랜드: {sneaker_info.get('brand', 'N/A')}
- 모델명: {sneaker_info.get('model_name', 'N/A')}
- 품번: {sneaker_info.get('style_code', 'N/A')}
- 컬러웨이: {sneaker_info.get('colorway', 'N/A')}
- 별명: {sneaker_info.get('nickname', 'N/A')}
- 분석 사이즈: {sneaker_info.get('selected_size', '전체 (최저가 기준)')}

## 현재 시세 데이터 (StockX 기준)
- StockX 최저가: {fmt_usd(cp.get('stockx_usd'))} (원화: {fmt_price(cp.get('stockx_krw'))})
- StockX 평균가: {fmt_usd(cp.get('avg_price_usd'))} (원화: {fmt_price(cp.get('avg_price_krw'))})
- StockX 최고가: {fmt_usd(cp.get('max_price_usd'))}
- GOAT 현재가: {fmt_usd(cp.get('goat_usd'))}
- FlightClub 현재가: {fmt_usd(cp.get('flightclub_usd'))}
- 주간 거래량: {stats.get('weekly_orders', stats.get('total_sales_30d', 'N/A'))}건
- 최근 추세: {stats.get('price_trend', 'N/A')}
- 인기 순위: {stats.get('trending_rank', 'N/A')}위 (거래량 기준)
- 수집된 데이터 일수: {stats.get('data_days', 'N/A')}일

## 시계열 예측 결과
- 예측 모델: {forecast_data.get('model', 'N/A')}
- 현재 가격: {fmt_price(forecast_data.get('current_price'))}
- 30일 후 예측가: {fmt_price(summary.get('predicted_30d_price'))}
- 예상 변동률: {summary.get('change_pct', 'N/A')}%
- 예측 추세: {summary.get('trend', 'N/A')}

## 참고사항
- 가격은 StockX(해외) 기준입니다. 국내 KREAM 가격은 이보다 낮거나 높을 수 있습니다.
- 인기 순위가 높을수록(1위에 가까울수록) 시장에서 활발히 거래되는 상품입니다.
- 데이터 수집일이 1일인 경우, 아직 추세 판단이 어려우므로 보수적으로 분석해주세요.
- 주간 거래량이 높으면 유동성이 높아 매도/매수가 용이합니다.
"""
    return context


def _recommend_with_claude(context: str, api_key: str) -> dict:
    """Claude API로 추천 생성"""
    prompt = f"""당신은 전문 스니커즈 리셀 투자 분석가입니다. 아래 데이터를 기반으로 리셀 투자 추천 리포트를 작성해주세요.

{context}

다음 JSON 형식으로 응답해주세요:
{{
    "recommendation": "BUY 또는 SELL 또는 HOLD 중 하나",
    "confidence_score": 0.0~1.0 사이의 확신도,
    "summary": "한 줄 요약 (한국어)",
    "detailed_report": "전문가 수준의 상세 분석 리포트 (한국어, 3~5문장)",
    "key_factors": ["판단 근거 1", "판단 근거 2", "판단 근거 3"],
    "risk_level": "LOW 또는 MEDIUM 또는 HIGH",
    "arbitrage_opportunity": "해외 직구 마진 거래 가능성 분석 (한국어)"
}}

JSON만 응답하세요."""

    response = httpx.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': api_key,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01'
        },
        json={
            'model': 'claude-sonnet-4-20250514',
            'max_tokens': 1000,
            'messages': [{'role': 'user', 'content': prompt}]
        },
        timeout=30.0
    )

    if response.status_code != 200:
        return {"error": f"Claude API 오류: {response.status_code}"}

    result_text = response.json()['content'][0]['text']
    try:
        cleaned = result_text.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[1]
            cleaned = cleaned.rsplit('```', 1)[0]
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"raw_response": result_text}


def _recommend_with_openai(context: str, api_key: str) -> dict:
    """OpenAI API로 추천 생성"""
    prompt = f"""당신은 전문 스니커즈 리셀 투자 분석가입니다. 아래 데이터를 기반으로 리셀 투자 추천 리포트를 작성해주세요.

{context}

다음 JSON 형식으로 응답해주세요:
{{
    "recommendation": "BUY 또는 SELL 또는 HOLD 중 하나",
    "confidence_score": 0.0~1.0 사이의 확신도,
    "summary": "한 줄 요약 (한국어)",
    "detailed_report": "전문가 수준의 상세 분석 리포트 (한국어, 3~5문장)",
    "key_factors": ["판단 근거 1", "판단 근거 2", "판단 근거 3"],
    "risk_level": "LOW 또는 MEDIUM 또는 HIGH",
    "arbitrage_opportunity": "해외 직구 마진 거래 가능성 분석 (한국어)"
}}

JSON만 응답하세요."""

    response = httpx.post(
        'https://api.openai.com/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        },
        json={
            'model': 'gpt-4o',
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': 1000,
            'temperature': 0.3
        },
        timeout=30.0
    )

    if response.status_code != 200:
        return {"error": f"OpenAI API 오류: {response.status_code}"}

    result_text = response.json()['choices'][0]['message']['content']
    try:
        cleaned = result_text.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[1]
            cleaned = cleaned.rsplit('```', 1)[0]
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"raw_response": result_text}


def _generate_demo_recommendation(sneaker_info: dict, price_data: dict, forecast_data: dict) -> dict:
    """API 키 미설정 시 데모 추천 결과"""
    current = price_data.get('current_price', {}).get('kream', 1200000)
    predicted = forecast_data.get('summary', {}).get('predicted_30d_price', current * 1.05)
    change_pct = forecast_data.get('summary', {}).get('change_pct', 5.0)
    price_gap = price_data.get('current_price', {}).get('price_gap_krw', 80000)
    model_name = sneaker_info.get('model_name', 'Air Jordan 1 Retro High OG')
    nickname = sneaker_info.get('nickname', 'Chicago')

    if change_pct > 3:
        recommendation = "HOLD"
        summary = f"{model_name} ({nickname})은 향후 가격 상승이 예측되어 보유(Hold)를 추천합니다."
    elif change_pct < -3:
        recommendation = "SELL"
        summary = f"{model_name} ({nickname})은 하락 추세로 판매(Sell)를 추천합니다."
    else:
        recommendation = "BUY"
        summary = f"{model_name} ({nickname})은 현재 적정가 수준으로 매수 기회입니다."

    return {
        "recommendation": recommendation,
        "confidence_score": 0.78,
        "summary": summary,
        "detailed_report": (
            f"인식된 모델은 {model_name} ({nickname})입니다. "
            f"현재 KREAM 시세는 {current:,}원이며, 30일 평균 대비 "
            f"{'상승' if change_pct > 0 else '하락'} 추세입니다. "
            f"시계열 모델 예측 결과 30일 뒤 가격은 {int(predicted):,}원"
            f"({'↑' if change_pct > 0 else '↓'}{abs(change_pct):.1f}%)으로 "
            f"{'우상향' if change_pct > 0 else '하락'}할 가능성이 높습니다. "
            f"해외 StockX와의 차액이 현재 {abs(price_gap):,}원 존재하므로 "
            f"{'구매 대행 마진 거래용으로 적합합니다.' if price_gap > 0 else '해외 구매 차액은 미미합니다.'}"
        ),
        "key_factors": [
            f"30일 예측 가격 변동: {change_pct:+.1f}%",
            f"KREAM-StockX 차액: {price_gap:,}원",
            f"최근 30일 거래량: {price_data.get('statistics', {}).get('total_sales_30d', 'N/A')}건"
        ],
        "risk_level": "MEDIUM" if abs(change_pct) < 5 else "LOW" if change_pct > 5 else "HIGH",
        "arbitrage_opportunity": (
            f"KREAM과 StockX 간 {abs(price_gap):,}원의 차액이 존재합니다. "
            f"{'배송비/관세 고려 시 마진 가능성이 있습니다.' if price_gap > 50000 else '배송비/관세 고려 시 마진이 크지 않습니다.'}"
        ),
        "note": "데모 모드 - API 키 설정 시 실제 AI 분석 결과가 제공됩니다."
    }
