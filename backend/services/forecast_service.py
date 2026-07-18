"""
시계열 예측 서비스 - Prophet 기반 가격 예측
Prophet 미설치 시 간단한 선형 회귀 대체 모델 사용
"""
import os
import json
from datetime import datetime, timedelta
from db.database import get_db

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    print("⚠️ Prophet 미설치 - 간단한 대체 예측 모델 사용")

import numpy as np


def forecast_price_prophet(style_code: str, periods: int = 30) -> dict:
    """Prophet을 사용한 가격 예측"""
    conn = get_db()
    cursor = conn.cursor()

    # 1차: price_history에서 KREAM 데이터
    cursor.execute('''
        SELECT recorded_date as ds, price as y
        FROM price_history 
        WHERE style_code = ? AND platform = 'KREAM'
        ORDER BY recorded_date ASC
    ''', (style_code,))
    rows = cursor.fetchall()

    # 2차: price_history에 없으면 daily_prices에서 가져오기
    if len(rows) < 10:
        cursor.execute('''
            SELECT collected_date as ds, avg_price_krw as y
            FROM daily_prices
            WHERE style_code = ? AND avg_price_krw > 0
            ORDER BY collected_date ASC
        ''', (style_code,))
        daily_rows = cursor.fetchall()
        if daily_rows:
            rows = daily_rows

    # 3차: daily_prices도 없으면 StockX USD 가격 사용
    if len(rows) < 2:
        cursor.execute('''
            SELECT collected_date as ds, stockx_price_usd as y
            FROM daily_prices
            WHERE style_code = ? AND stockx_price_usd > 0
            ORDER BY collected_date ASC
        ''', (style_code,))
        usd_rows = cursor.fetchall()
        if usd_rows:
            rows = usd_rows

    conn.close()

    if len(rows) < 2:
        # 데이터가 1~2개뿐이면 현재가 기반 보합 예측 생성
        if len(rows) >= 1:
            current_price = rows[-1]['y']
            return _generate_flat_forecast(style_code, current_price, periods)
        return {"error": "예측을 위한 충분한 데이터가 없습니다 (최소 10일 필요)"}

    history = [{'ds': row['ds'], 'y': row['y']} for row in rows]

    if PROPHET_AVAILABLE and len(history) >= 10:
        return _prophet_forecast(history, style_code, periods)
    else:
        return _simple_forecast(history, style_code, periods)


def _generate_flat_forecast(style_code: str, current_price: float, periods: int) -> dict:
    """데이터가 부족할 때 현재가 기반 보합 예측 (±5% 범위)"""
    last_date = datetime.now()
    predictions = []
    for i in range(1, periods + 1):
        predictions.append({
            'date': (last_date + timedelta(days=i)).strftime('%Y-%m-%d'),
            'predicted_price': round(current_price),
            'lower_bound': round(current_price * 0.95),
            'upper_bound': round(current_price * 1.05),
        })

    return {
        "model": "flat_estimate (데이터 부족)",
        "style_code": style_code,
        "current_price": current_price,
        "predictions": predictions,
        "summary": {
            "predicted_30d_price": round(current_price),
            "change_amount": 0,
            "change_pct": 0.0,
            "trend": "보합",
            "confidence": "low"
        }
    }


def _prophet_forecast(history: list, style_code: str, periods: int) -> dict:
    """Prophet 모델 예측"""
    import pandas as pd

    df = pd.DataFrame(history)
    df['ds'] = pd.to_datetime(df['ds'])

    model = Prophet(
        daily_seasonality=False,
        weekly_seasonality=True,
        yearly_seasonality=False,
        changepoint_prior_scale=0.05
    )
    model.fit(df)

    future = model.make_future_dataframe(periods=periods)
    forecast = model.predict(future)

    # 예측 결과 추출
    predictions = []
    for _, row in forecast.tail(periods).iterrows():
        predictions.append({
            'date': row['ds'].strftime('%Y-%m-%d'),
            'predicted_price': round(row['yhat']),
            'lower_bound': round(row['yhat_lower']),
            'upper_bound': round(row['yhat_upper']),
        })

    # 예측 저장
    _save_predictions(style_code, predictions)

    current_price = history[-1]['y']
    predicted_final = predictions[-1]['predicted_price']
    change_pct = ((predicted_final - current_price) / current_price) * 100

    return {
        "model": "prophet",
        "style_code": style_code,
        "current_price": current_price,
        "predictions": predictions,
        "summary": {
            "predicted_30d_price": predicted_final,
            "change_amount": predicted_final - current_price,
            "change_pct": round(change_pct, 2),
            "trend": "상승" if change_pct > 0 else "하락",
            "confidence": "high" if abs(change_pct) > 3 else "medium"
        }
    }


def _simple_forecast(history: list, style_code: str, periods: int) -> dict:
    """Prophet 미설치 시 간단한 선형 회귀 기반 예측"""
    prices = [h['y'] for h in history]
    dates = list(range(len(prices)))

    # 간단 선형 회귀
    n = len(prices)
    x_mean = sum(dates) / n
    y_mean = sum(prices) / n
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(dates, prices))
    denominator = sum((x - x_mean) ** 2 for x in dates)
    slope = numerator / denominator if denominator != 0 else 0
    intercept = y_mean - slope * x_mean

    # 변동성 계산
    residuals = [prices[i] - (slope * i + intercept) for i in range(n)]
    std_dev = (sum(r ** 2 for r in residuals) / n) ** 0.5

    # 미래 예측
    last_date_str = history[-1]['ds']
    last_date = datetime.strptime(last_date_str, '%Y-%m-%d')

    predictions = []
    for i in range(1, periods + 1):
        future_x = n + i
        predicted = slope * future_x + intercept
        predictions.append({
            'date': (last_date + timedelta(days=i)).strftime('%Y-%m-%d'),
            'predicted_price': round(predicted),
            'lower_bound': round(predicted - 1.96 * std_dev),
            'upper_bound': round(predicted + 1.96 * std_dev),
        })

    _save_predictions(style_code, predictions)

    current_price = prices[-1]
    predicted_final = predictions[-1]['predicted_price']
    change_pct = ((predicted_final - current_price) / current_price) * 100

    return {
        "model": "linear_regression_fallback",
        "style_code": style_code,
        "current_price": current_price,
        "predictions": predictions,
        "summary": {
            "predicted_30d_price": predicted_final,
            "change_amount": predicted_final - current_price,
            "change_pct": round(change_pct, 2),
            "trend": "상승" if change_pct > 0 else "하락",
            "confidence": "medium"
        }
    }


def _save_predictions(style_code: str, predictions: list):
    """예측 결과를 DB에 저장"""
    conn = get_db()
    cursor = conn.cursor()

    for pred in predictions:
        cursor.execute('''
            INSERT INTO predictions (style_code, predicted_date, predicted_price, lower_bound, upper_bound, model_used)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (style_code, pred['date'], pred['predicted_price'],
              pred.get('lower_bound'), pred.get('upper_bound'), 'prophet'))

    conn.commit()
    conn.close()
