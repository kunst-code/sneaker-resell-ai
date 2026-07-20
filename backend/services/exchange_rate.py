"""
실시간 환율 서비스
무료 API로 USD/KRW 당일 환율 조회, 1시간 캐시
"""
import httpx
from datetime import datetime, timedelta

_cached_rate = None
_cached_at = None


def get_usd_krw() -> float:
    """USD/KRW 환율 반환 (1시간 캐시)"""
    global _cached_rate, _cached_at

    # 캐시 유효하면 바로 반환
    if _cached_rate and _cached_at and (datetime.now() - _cached_at) < timedelta(hours=1):
        return _cached_rate

    # 실시간 환율 조회
    rate = _fetch_rate()
    if rate:
        _cached_rate = rate
        _cached_at = datetime.now()
        return rate

    # 실패 시 캐시 또는 기본값
    return _cached_rate or 1380.0


def _fetch_rate() -> float:
    """무료 환율 API에서 USD/KRW 조회"""
    apis = [
        _fetch_from_exchangerate_api,
        _fetch_from_open_exchange,
    ]

    for api_func in apis:
        try:
            rate = api_func()
            if rate and 1000 < rate < 2000:  # 합리적 범위 체크
                return rate
        except Exception:
            continue

    return None


def _fetch_from_exchangerate_api() -> float:
    """exchangerate-api.com (무료, 키 불필요)"""
    r = httpx.get(
        "https://open.er-api.com/v6/latest/USD",
        timeout=5
    )
    if r.status_code == 200:
        data = r.json()
        return data.get('rates', {}).get('KRW')
    return None


def _fetch_from_open_exchange() -> float:
    """폴백: 다른 무료 환율 API"""
    r = httpx.get(
        "https://api.exchangerate.host/latest?base=USD&symbols=KRW",
        timeout=5
    )
    if r.status_code == 200:
        data = r.json()
        return data.get('rates', {}).get('KRW')
    return None
