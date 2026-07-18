"""
데이터 수집 CLI 스크립트
수동 실행: python collect_data.py
강제 수집: python collect_data.py --force

cron 등록 예시 (매일 오전 9시):
0 9 * * * cd /path/to/sneaker-resell-ai/backend && /path/to/venv/bin/python collect_data.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from db.database import init_db
from services.collector_service import collect_trending_data, get_last_collection_info

if __name__ == '__main__':
    init_db()

    force = '--force' in sys.argv
    print(f"\n📦 스니커즈 데이터 수집 시작{'(강제)' if force else ''}...")

    # 마지막 수집 정보
    info = get_last_collection_info()
    if info.get('last_collected'):
        print(f"   마지막 수집: {info['last_collected']} ({info['items']}개)")

    # 수집 실행
    result = collect_trending_data(force=force)

    if result.get('status') == 'skipped':
        print(f"⏭️  {result['message']}")
        print("   강제 수집하려면: python collect_data.py --force")
    elif result.get('status') == 'success':
        print(f"✅ 수집 완료! {result['collected']}개 스니커즈 저장")
        if result.get('errors'):
            print(f"⚠️  일부 에러: {result['errors']}")
    elif result.get('error'):
        print(f"❌ 에러: {result['error']}")

    print()
