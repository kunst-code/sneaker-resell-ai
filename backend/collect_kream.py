"""
KREAM 배치 크롤링 스크립트
로컬에서 하루 1회 실행 (cron 등록 권장)

사용법:
  python collect_kream.py          # 일반 실행 (인기+트렌드 상품)
  python collect_kream.py --force   # 오늘 이미 수집했어도 재실행

cron 등록 예시 (매일 새벽 3시):
  0 3 * * * cd /Users/heedae/sneaker-resell-ai/backend && /Users/heedae/sneaker-resell-ai/venv/bin/python collect_kream.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from db.database import init_db
from services.kream_batch import collect_kream_prices, get_target_skus, get_kream_price_from_db
from datetime import datetime

if __name__ == '__main__':
    init_db()
    force = '--force' in sys.argv

    print(f"\n{'='*50}")
    print(f"🛍️  KREAM 배치 크롤링 시작")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    # 오늘 이미 수집했는지 확인
    if not force:
        test_sku = 'DD1391-100'
        cached = get_kream_price_from_db(test_sku)
        if cached and cached.get('collected_date') == datetime.now().strftime('%Y-%m-%d'):
            print("⏭️  오늘 이미 수집 완료. --force로 재실행 가능")
            sys.exit(0)

    # 수집 대상 SKU 목록
    skus = get_target_skus()
    print(f"📋 수집 대상: {len(skus)}개 상품")
    print(f"   {', '.join(skus[:10])}{'...' if len(skus) > 10 else ''}\n")

    # 수집 실행
    result = collect_kream_prices(skus)

    print(f"\n{'='*50}")
    if result.get('status') == 'success':
        print(f"✅ 수집 완료! {result['collected']}개 성공, {result['errors']}개 실패")
    else:
        print(f"❌ 수집 실패: {result.get('error')}")

    if result.get('error_details'):
        print(f"⚠️  실패 목록: {result['error_details']}")
    print(f"{'='*50}\n")
