"""
KREAM 가격 수동 입력 스크립트
크롤링이 차단될 때 직접 가격을 입력하여 DB에 저장

사용법:
  python manual_kream_input.py

아래 kream_data 리스트에 데이터를 채운 후 실행하세요.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from db.database import init_db, get_db
from datetime import datetime

# ============================================================
# 여기에 KREAM 가격 데이터를 입력하세요
# 형식: {"sku": "품번", "name": "상품명", "price": 가격(원)}
# ============================================================
kream_data = [
    {"sku": "DD1391-100", "name": "에어 조던 1 레트로 하이 OG 시카고", "price": 89000},
    {"sku": "U992GY", "name": "뉴발란스 992 코어 그레이 실버 메탈릭", "price": 221000},
    {"sku": "M1906AD", "name": "뉴발란스 1906 실버 메탈릭 캐슬락", "price": 129000},
    {"sku": "DZ5485-612", "name": "에어 조던 1 레트로 하이 OG 로스트 앤 파운드", "price": 267000},
    {"sku": "DD1503-100", "name": "나이키 덩크 로우 레트로 화이트 블랙 판다", "price": 130000},
    {"sku": "CW2288-111", "name": "나이키 에어포스1 07 화이트", "price": 96000},
    {"sku": "FQ1759-002", "name": "에어 조던 4 레트로 브레드 리이매진드", "price": 230000},
    {"sku": "1201A019-108", "name": "아식스 겔카야노 14 화이트 세이지", "price": 279000},
    {"sku": "IG7379", "name": "아디다스 삼바 OG 화이트", "price": 89000},
    {"sku": "DM7866-162", "name": "조던 1 로우 트래비스 스캇 리버스 모카", "price": 1465000},
]
# ============================================================


def save_to_db(data_list):
    """수동 입력 데이터를 DB에 저장"""
    init_db()
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

    today = datetime.now().strftime('%Y-%m-%d')
    saved = 0

    for item in data_list:
        if not item.get('price') or item['price'] == 0:
            continue

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO kream_prices 
                (style_code, product_name, kream_price, release_price, trade_volume, kream_url, collected_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                item['sku'],
                item.get('name', ''),
                item['price'],
                item.get('release_price', 0),
                item.get('trade_volume', 0),
                item.get('url', ''),
                today,
            ))
            saved += 1
            print(f"  ✅ {item['sku']}: {item['price']:,}원 — {item.get('name', '')}")
        except Exception as e:
            print(f"  ❌ {item['sku']}: {e}")

    conn.commit()
    conn.close()
    return saved


if __name__ == '__main__':
    print(f"\n{'='*50}")
    print(f"📝 KREAM 가격 수동 입력")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*50}\n")

    active = [d for d in kream_data if d.get('price', 0) > 0]
    print(f"입력 데이터: {len(active)}개\n")

    if not active:
        print("⚠️  kream_data 리스트에 가격을 입력해주세요!")
        print("   파일: backend/manual_kream_input.py")
        sys.exit(1)

    saved = save_to_db(active)
    print(f"\n{'='*50}")
    print(f"✅ {saved}개 저장 완료!")
    print(f"{'='*50}\n")
