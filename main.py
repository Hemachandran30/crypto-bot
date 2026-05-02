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

coins = [
    "BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT",
    "BNBUSDT","ADAUSDT","DOGEUSDT","MATICUSDT",
    "AVAXUSDT","DOTUSDT"
]

# ✅ FIXED DATA FUNCTION
def get_data(symbol):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=15m&limit=100"

        res = requests.get(url, timeout=10)

        if res.status_code != 200:
            print("API ERROR:", res.text)
            return None

        data = res.json()

        if not isinstance(data, list) or len(data) == 0:
            print("Empty data:", symbol)
            return None

        df = pd.DataFrame(data)

        df["close"] = df[4].astype(float)
        df["high"] = df[2].astype(float)
        df["low"] = df[3].astype(float)

        return df

    except Exception as e:
        print("Fetch error:", e)
        return None

def detect_patterns(df):
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values

    patterns = []

    if abs(highs[-1] - highs[-3]) < 0.3:
        patterns.append(("Double Top", 70))

    if abs(lows[-1] - lows[-3]) < 0.3:
        patterns.append(("Double Bottom", 75))

    if highs[-3] > highs[-2] and highs[-3] > highs[-4]:
        patterns.append(("Head & Shoulders", 80))

    if lows[-3] < lows[-2] and lows[-3] < lows[-4]:
        patterns.append(("Inverse Head & Shoulders", 82))

    if closes[-1] > max(closes[-10:-1]):
        patterns.append(("Breakout", 85))

    if closes[-1] < min(closes[-10:-1]):
        patterns.append(("Breakdown", 85))

    if len(patterns) == 0:
        return ("No Pattern", 60)

    return max(patterns, key=lambda x: x[1])

def analyze(df):
    try:
        df["rsi"] = ta.momentum.RSIIndicator(close=df["close"], window=14).rsi()
        df["ema"] = ta.trend.EMAIndicator(close=df["close"], window=20).ema_indicator()

        last = df.iloc[-1]

        price = last["close"]
        rsi = last["rsi"]
        ema = last["ema"]

        pattern, score = detect_patterns(df)

        signal = "BUY" if price > ema else "SELL"

        entry = round(price, 4)
        sl = round(price * 0.97, 4)
        tp = round(price * 1.05, 4)

        return signal, entry, sl, tp, score, pattern

    except Exception as e:
        print("Analysis error:", e)
        return None

send("🚀 BOT STARTED - AI TRADING ENGINE LIVE")

while True:
    print("Checking market...")

    for coin in coins:
        df = get_data(coin)

        if df is None:
            continue

        result = analyze(df)

        if result:
            signal, entry, sl, tp, score, pattern = result

            msg = f"""
📊 {coin}

📢 Signal: {signal}
💰 Entry: {entry}
🎯 TP: {tp}
🛑 SL: {sl}

🧠 Pattern: {pattern}
📈 Confidence: {score}%

⏱ Time: {datetime.now().strftime('%H:%M:%S')}
"""

            send(msg)

    time.sleep(60)
