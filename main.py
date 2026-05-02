import requests
import time
import pandas as pd
import ta
from datetime import datetime

# ==============================
# 🔐 TELEGRAM
# ==============================
BOT_TOKEN = "8745061783:AAFu0AGFMONUiEw3KAkZlDgzKSq2jBdW0Sc"
CHAT_ID = "931982378"

def send(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
        print("Sent:", msg)
    except Exception as e:
        print("Telegram Error:", e)

# ==============================
# 💰 COINS
# ==============================
coins = [
    "BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT",
    "BNBUSDT","ADAUSDT","DOGEUSDT","MATICUSDT",
    "AVAXUSDT","DOTUSDT"
]

# ==============================
# 📊 GET DATA
# ==============================
def get_data(symbol):
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": symbol, "interval": "15m", "limit": 120}
        headers = {"User-Agent": "Mozilla/5.0"}

        res = requests.get(url, params=params, headers=headers, timeout=10)
        data = res.json()

        if not isinstance(data, list) or len(data) == 0:
            return None

        df = pd.DataFrame(data, columns=[
            "time","open","high","low","close","volume",
            "close_time","qav","trades","tbbav","tbqav","ignore"
        ])

        df["close"] = df["close"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)

        return df

    except:
        return None

# ==============================
# 📈 PATTERN DETECTION (10 TYPES)
# ==============================
def detect_patterns(df):
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values

    patterns = []

    # 1. Double Top
    if abs(highs[-1] - highs[-3]) < 0.3:
        patterns.append(("Double Top", 70))

    # 2. Double Bottom
    if abs(lows[-1] - lows[-3]) < 0.3:
        patterns.append(("Double Bottom", 75))

    # 3. Head & Shoulders
    if highs[-3] > highs[-2] and highs[-3] > highs[-4]:
        patterns.append(("Head & Shoulders", 80))

    # 4. Inverse H&S
    if lows[-3] < lows[-2] and lows[-3] < lows[-4]:
        patterns.append(("Inverse Head & Shoulders", 82))

    # 5. Ascending Triangle
    if highs[-1] <= highs[-2] and lows[-1] > lows[-2]:
        patterns.append(("Ascending Triangle", 78))

    # 6. Descending Triangle
    if lows[-1] >= lows[-2] and highs[-1] < highs[-2]:
        patterns.append(("Descending Triangle", 78))

    # 7. Bull Flag
    if closes[-1] > closes[-5] and closes[-2] < closes[-1]:
        patterns.append(("Bull Flag", 76))

    # 8. Bear Flag
    if closes[-1] < closes[-5] and closes[-2] > closes[-1]:
        patterns.append(("Bear Flag", 76))

    # 9. Breakout
    if closes[-1] > max(closes[-10:-1]):
        patterns.append(("Breakout", 85))

    # 10. Breakdown
    if closes[-1] < min(closes[-10:-1]):
        patterns.append(("Breakdown", 85))

    if len(patterns) == 0:
        return ("No Pattern", 60)

    # choose strongest
    best = max(patterns, key=lambda x: x[1])
    return best

# ==============================
# 🧠 ANALYSIS ENGINE
# ==============================
def analyze(df):
    try:
        df["rsi"] = ta.momentum.RSIIndicator(df["close"]).rsi()
        df["ema"] = ta.trend.EMAIndicator(df["close"], window=20).ema_indicator()
        macd = ta.trend.MACD(df["close"])
        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()

        last = df.iloc[-1]

        price = last["close"]
        rsi = last["rsi"]
        ema = last["ema"]
        macd_val = last["macd"]
        macd_sig = last["macd_signal"]

        pattern, pattern_score = detect_patterns(df)

        trend = "UP" if price > ema else "DOWN"

        score = pattern_score

        if rsi < 40:
            score += 5
        if rsi > 60:
            score += 5

        if macd_val > macd_sig:
            score += 5
        else:
            score += 3

        if trend == "UP":
            signal = "BUY"
        else:
            signal = "SELL"

        entry = round(price, 4)
        sl = round(price * 0.97, 4)
        tp = round(price * 1.05, 4)

        return signal, entry, sl, tp, score, pattern

    except:
        return None

# ==============================
# 🚀 BOT START
# ==============================
send("🚀 BOT STARTED - AI TRADING ENGINE LIVE")

# ==============================
# 🔁 LOOP
# ==============================
while True:
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

    time.sleep(900)  # 15 minutes
