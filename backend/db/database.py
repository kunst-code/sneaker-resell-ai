"""
SQLite 데이터베이스 스키마 및 초기화
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'sneaker_resell.db')


def get_db():
    """DB 연결 반환"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """테이블 생성 및 샘플 데이터 삽입"""
    conn = get_db()
    cursor = conn.cursor()

    # 스니커즈 기본 정보 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sneakers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            style_code TEXT UNIQUE NOT NULL,
            brand TEXT NOT NULL,
            model_name TEXT NOT NULL,
            colorway TEXT,
            release_date TEXT,
            retail_price REAL,
            image_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 가격 이력 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            style_code TEXT NOT NULL,
            platform TEXT NOT NULL,
            price REAL NOT NULL,
            currency TEXT DEFAULT 'KRW',
            number_of_sales INTEGER DEFAULT 0,
            recorded_date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (style_code) REFERENCES sneakers(style_code)
        )
    ''')

    # 예측 결과 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            style_code TEXT NOT NULL,
            predicted_date TEXT NOT NULL,
            predicted_price REAL NOT NULL,
            lower_bound REAL,
            upper_bound REAL,
            model_used TEXT DEFAULT 'prophet',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (style_code) REFERENCES sneakers(style_code)
        )
    ''')

    # 분석 결과 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            style_code TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            report_text TEXT NOT NULL,
            kream_price REAL,
            stockx_price REAL,
            price_gap REAL,
            predicted_30d_price REAL,
            predicted_change_pct REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (style_code) REFERENCES sneakers(style_code)
        )
    ''')

    # 트렌딩 스니커즈 테이블 (하루 1회 RapidAPI에서 수집)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trending_sneakers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            style_code TEXT NOT NULL,
            brand TEXT NOT NULL,
            model_name TEXT NOT NULL,
            colorway TEXT,
            release_date TEXT,
            retail_price REAL,
            image_url TEXT,
            rank INTEGER DEFAULT 0,
            collected_date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(style_code, collected_date)
        )
    ''')

    # 일별 가격 테이블 (하루 1회 수집, 30일 보관)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            style_code TEXT NOT NULL,
            stockx_price_usd REAL,
            goat_price_usd REAL,
            flightclub_price_usd REAL,
            avg_price_krw REAL,
            number_of_sales INTEGER DEFAULT 0,
            collected_date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(style_code, collected_date)
        )
    ''')

    # 수집 로그 테이블 (마지막 수집 시간 추적)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS collection_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_type TEXT NOT NULL,
            status TEXT NOT NULL,
            items_collected INTEGER DEFAULT 0,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 샘플 데이터 삽입
    sample_sneakers = [
        ('DD1391-100', 'Nike', 'Air Jordan 1 Retro High OG', 'White/Black-University Red (Chicago)', '2015-05-30', 160.0, ''),
        ('DZ5485-612', 'Nike', 'Air Jordan 1 Retro High OG', 'Lost and Found (Chicago)', '2022-11-19', 180.0, ''),
        ('555088-134', 'Nike', 'Air Jordan 1 Retro High OG', 'University Blue', '2021-03-06', 170.0, ''),
        ('BQ6623-006', 'Nike', 'Air Jordan 1 Retro Low OG', 'Travis Scott', '2019-07-20', 130.0, ''),
        ('DO9392-700', 'Nike', 'Air Jordan 1 Retro Low OG SP', 'Travis Scott Canary', '2024-03-23', 150.0, ''),
        ('FQ1759-002', 'Nike', 'Air Jordan 4 Retro', 'Bred Reimagined', '2024-02-17', 210.0, ''),
        ('350V2-ZEBRA', 'Adidas', 'Yeezy Boost 350 V2', 'Zebra', '2017-02-25', 220.0, ''),
        ('BB550WT1', 'New Balance', '550', 'White Green', '2021-03-18', 110.0, ''),
    ]

    for sneaker in sample_sneakers:
        cursor.execute('''
            INSERT OR IGNORE INTO sneakers (style_code, brand, model_name, colorway, release_date, retail_price, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', sneaker)

    # 샘플 가격 이력 (Jordan 1 Chicago 2015)
    import random
    from datetime import datetime, timedelta

    base_date = datetime(2024, 1, 1)
    base_price_kream = 1200000  # 120만원
    base_price_stockx = 1800  # $1,800 USD

    for i in range(90):
        date = (base_date + timedelta(days=i)).strftime('%Y-%m-%d')
        kream_price = base_price_kream + random.randint(-50000, 80000)
        stockx_price = base_price_stockx + random.randint(-50, 100)
        sales = random.randint(5, 30)

        cursor.execute('''
            INSERT OR IGNORE INTO price_history (style_code, platform, price, currency, number_of_sales, recorded_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('DD1391-100', 'KREAM', kream_price, 'KRW', sales, date))

        cursor.execute('''
            INSERT OR IGNORE INTO price_history (style_code, platform, price, currency, number_of_sales, recorded_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('DD1391-100', 'StockX', stockx_price, 'USD', sales + random.randint(0, 10), date))

    # Lost and Found 가격 이력
    base_price_lf = 380000
    for i in range(90):
        date = (base_date + timedelta(days=i)).strftime('%Y-%m-%d')
        kream_price = base_price_lf + random.randint(-20000, 40000)
        stockx_price = 250 + random.randint(-20, 50)
        sales = random.randint(20, 80)

        cursor.execute('''
            INSERT OR IGNORE INTO price_history (style_code, platform, price, currency, number_of_sales, recorded_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('DZ5485-612', 'KREAM', kream_price, 'KRW', sales, date))

        cursor.execute('''
            INSERT OR IGNORE INTO price_history (style_code, platform, price, currency, number_of_sales, recorded_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('DZ5485-612', 'StockX', stockx_price, 'USD', sales + random.randint(0, 20), date))

    conn.commit()
    conn.close()
    print("✅ 데이터베이스 초기화 완료")


if __name__ == '__main__':
    init_db()
