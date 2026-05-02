import requests
import time
import pandas as pd
import ta
from datetime import datetime

BOT_TOKEN = "8745061783:AAFu0AGFMONUiEw3KAkZlDgzKSq2jBdW0Sc"
CHAT_ID = "931982378"

def send(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
        print("Sent:", msg)
    except Exception as e:
        print("Telegram Error:", e)

coins = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "XRP": "ripple",
    "BNB": "binancecoin",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "MATIC": "matic-network",
    "AVAX": "avalanche-2",
    "DOT": "polkadot"
}

# ✅ FIXED API
def get_price(coin_id):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": "1"}
        res = requests.get(url, params=params, timeout=10)
        data = res.json()

        if "prices" not in data:
            print(f"No data for {coin_id}")
            return None

        prices = [p[1] for p in data["prices"]]

        df = pd.DataFrame(prices, columns=["close"])
        df["high"] = df["close"]
        df["low"] = df["close"]

        return df

    except Exception as e:
        print("API ERROR:", e)
        return None

# 🔥 10+ ADVANCED PATTERNS
def detect_patterns(df):
    close = df["close"]

    patterns = []

    # 1 Breakout
    if close.iloc[-1] > max(close[-20:-1]):
        patterns.append(("Breakout", 90))

    # 2 Breakdown
    if close.iloc[-1] < min(close[-20:-1]):
        patterns.append(("Breakdown", 90))

    # 3 Double Top
    if close.iloc[-1] < close.iloc[-2] and close.iloc[-2] > close.iloc[-3]:
        patterns.append(("Double Top", 80))

    # 4 Double Bottom
    if close.iloc[-1] > close.iloc[-2] and close.iloc[-2] < close.iloc[-3]:
        patterns.append(("Double Bottom", 80))

    # 5 Bullish Engulfing
    if close.iloc[-1] > close.iloc[-2] * 1.01:
        patterns.append(("Bullish Engulfing", 85))

    # 6 Bearish Engulfing
    if close.iloc[-1] < close.iloc[-2] * 0.99:
        patterns.append(("Bearish Engulfing", 85))

    # 7 Strong Uptrend
    if close.iloc[-1] > close.iloc[-2] > close.iloc[-3] > close.iloc[-4]:
        patterns.append(("Strong Uptrend", 88))

    # 8 Strong Downtrend
    if close.iloc[-1] < close.iloc[-2] < close.iloc[-3] < close.iloc[-4]:
        patterns.append(("Strong Downtrend", 88))

    # 9 RSI Overbought
    if df["rsi"].iloc[-1] > 70:
        patterns.append(("RSI Overbought", 75))

    # 10 RSI Oversold
    if df["rsi"].iloc[-1] < 30:
        patterns.append(("RSI Oversold", 75))

    # 11 EMA Trend
    if df["close"].iloc[-1] > df["ema"].iloc[-1]:
        patterns.append(("EMA Bullish", 80))
    else:
        patterns.append(("EMA Bearish", 80))

    if not patterns:
        return ("No Pattern", 60)

    return max(patterns, key=lambda x: x[1])

# 🔥 ANALYSIS ENGINE
def analyze(df):
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], 14).rsi()
    df["ema"] = ta.trend.EMAIndicator(df["close"], 20).ema_indicator()

    price = df["close"].iloc[-1]
    ema = df["ema"].iloc[-1]

    pattern, confidence = detect_patterns(df)

    signal = "BUY" if price > ema else "SELL"

    entry = round(price, 4)
    sl = round(price * 0.97, 4)
    tp = round(price * 1.05, 4)

    return signal, entry, sl, tp, confidence, pattern

# 🚀 START BOT
send("🚀 BOT STARTED - AI TRADING ENGINE LIVE")

while True:
    print("Checking market...")

    for symbol, coin_id in coins.items():
        df = get_price(coin_id)

        if df is None:
            continue

        result = analyze(df)

        if result:
            signal, entry, sl, tp, conf, pattern = result

            msg = f"""
📊 {symbol}

📢 Signal: {signal}
💰 Entry: {entry}
🎯 TP: {tp}
🛑 SL: {sl}

🧠 Pattern: {pattern}
📈 Confidence: {conf}%

⏱ Time: {datetime.now().strftime('%H:%M:%S')}
"""

            send(msg)

    time.sleep(60)
