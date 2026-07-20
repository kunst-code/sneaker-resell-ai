"""
기본 추천 데이터 시딩 — 서버 시작 시 캐시가 비어있으면 기본값 저장
첫 접속자도 즉시 목록을 볼 수 있도록
"""
import json
from datetime import datetime
from db.database import get_db


DEFAULT_RECOMMENDATIONS = {
    "success": True,
    "trend_analysis": "한국 스니커즈 시장은 뉴발란스 990/992 시리즈와 나이키 덩크 로우가 꾸준한 인기를 유지하고 있으며, 아식스 겔카야노/젤1130이 MZ세대 사이에서 급부상 중입니다. Jordan 4 시리즈의 신규 컬러웨이 출시가 활발하며, 살로몬 XT-6 등 고프코어 트렌드도 지속되고 있습니다.",
    "recommendations": [
        {"rank": 1, "model_name": "New Balance 992 Made in USA Grey", "brand": "New Balance", "style_code": "U992GY", "colorway": "Grey Silver Metallic", "reason": "국내 인기 1위 뉴발란스 모델. 가격 안정적이며 꾸준한 수요 존재.", "trend_source": "KREAM", "buy_signal": "BUY", "price_usd": 130, "avg_price_usd": 156, "price_krw": 189000, "weekly_orders": 0, "price_trend": "보합", "image": ""},
        {"rank": 2, "model_name": "Nike Dunk Low Retro White Black Panda", "brand": "Nike", "style_code": "DD1391-100", "colorway": "White Black", "reason": "국민 스니커즈. 언더 리테일 가격으로 저점 매수 기회.", "trend_source": "커뮤니티", "buy_signal": "BUY", "price_usd": 56, "avg_price_usd": 75, "price_krw": 89000, "weekly_orders": 2429, "price_trend": "보합", "image": ""},
        {"rank": 3, "model_name": "Jordan 4 Retro Bred Reimagined", "brand": "Jordan", "style_code": "FQ1759-002", "colorway": "Black Cement", "reason": "클래식 컬러웨이 리이매진드. 출시 후 프리미엄 유지 중.", "trend_source": "유튜브", "buy_signal": "HOLD", "price_usd": 230, "avg_price_usd": 280, "price_krw": 310000, "weekly_orders": 0, "price_trend": "상승", "image": ""},
        {"rank": 4, "model_name": "Asics Gel-Kayano 14 White Sage", "brand": "Asics", "style_code": "1201A019-108", "colorway": "White Sage", "reason": "MZ세대 필수 아이템. 수요 급증으로 가격 상승 추세.", "trend_source": "인스타그램", "buy_signal": "BUY", "price_usd": 95, "avg_price_usd": 120, "price_krw": 145000, "weekly_orders": 0, "price_trend": "상승", "image": ""},
        {"rank": 5, "model_name": "New Balance 1906R Silver Metallic", "brand": "New Balance", "style_code": "M1906RXA", "colorway": "Silver Metallic", "reason": "1906 시리즈 대표 컬러. 꾸준한 인기와 리셀 가치.", "trend_source": "KREAM", "buy_signal": "BUY", "price_usd": 85, "avg_price_usd": 110, "price_krw": 159000, "weekly_orders": 0, "price_trend": "보합", "image": ""},
        {"rank": 6, "model_name": "Adidas Samba OG White", "brand": "Adidas", "style_code": "BZ0057", "colorway": "Cloud White", "reason": "레트로 트렌드 지속. 품절 사이즈 프리미엄 존재.", "trend_source": "커뮤니티", "buy_signal": "HOLD", "price_usd": 80, "avg_price_usd": 100, "price_krw": 129000, "weekly_orders": 0, "price_trend": "보합", "image": ""},
        {"rank": 7, "model_name": "Salomon XT-6 Black", "brand": "Salomon", "style_code": "L41086600", "colorway": "Black/Black", "reason": "고프코어 대표 모델. 아웃도어 트렌드와 함께 인기 지속.", "trend_source": "유튜브", "buy_signal": "HOLD", "price_usd": 120, "avg_price_usd": 150, "price_krw": 179000, "weekly_orders": 0, "price_trend": "보합", "image": ""},
        {"rank": 8, "model_name": "New Balance 990v6 Grey", "brand": "New Balance", "style_code": "M990GL6", "colorway": "Grey", "reason": "990 시리즈 최신 버전. 기능성과 스타일 모두 갖춘 인기 모델.", "trend_source": "KREAM", "buy_signal": "BUY", "price_usd": 140, "avg_price_usd": 175, "price_krw": 269000, "weekly_orders": 0, "price_trend": "상승", "image": ""},
        {"rank": 9, "model_name": "Jordan 1 Low Travis Scott Reverse Mocha", "brand": "Jordan", "style_code": "DM7866-162", "colorway": "Sail/Ridgerock", "reason": "트래비스 스캇 콜라보의 대표작. 높은 프리미엄 유지.", "trend_source": "유튜브", "buy_signal": "HOLD", "price_usd": 975, "avg_price_usd": 1100, "price_krw": 1350000, "weekly_orders": 292, "price_trend": "보합", "image": ""},
        {"rank": 10, "model_name": "Nike Air Force 1 '07 White", "brand": "Nike", "style_code": "CW2288-111", "colorway": "White/White", "reason": "영원한 클래식. 언더 리테일로 일상화 구매 적합.", "trend_source": "커뮤니티", "buy_signal": "BUY", "price_usd": 55, "avg_price_usd": 70, "price_krw": 89000, "weekly_orders": 0, "price_trend": "보합", "image": ""},
    ],
    "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M'),
}


def seed_recommendations_if_empty():
    """캐시가 비어있으면 기본 추천 데이터 시딩"""
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

        # 캐시 있는지 확인
        cursor.execute('SELECT COUNT(*) as cnt FROM trend_cache')
        row = cursor.fetchone()
        if row['cnt'] == 0:
            cursor.execute('INSERT INTO trend_cache (data) VALUES (?)',
                           (json.dumps(DEFAULT_RECOMMENDATIONS, ensure_ascii=False),))
            conn.commit()
            print("📋 기본 추천 데이터 시딩 완료")

        conn.close()
    except Exception as e:
        print(f"⚠️ 추천 시딩 실패: {e}")
