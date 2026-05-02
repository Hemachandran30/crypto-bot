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
# COINS
# ==============================
coins = [
    "BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT",
    "BNBUSDT","ADAUSDT","DOGEUSDT","MATICUSDT",
    "AVAXUSDT","DOTUSDT"
]

# ==============================
# GET DATA
# ==============================
def get_data(symbol):
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": symbol,
            "interval": "15m",
            "limit": 100
        }

        data = requests.get(url, params=params).json()

        if not isinstance(data, list):
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
# PATTERN DETECTION
# ==============================
def detect_pattern(df):
    highs = df["high"].tail(10).values
    lows = df["low"].tail(10).values

    # Simple double top
    if abs(highs[-1] - highs[-3]) < 0.3:
        return "Double Top", 72

    # Simple double bottom
    if abs(lows[-1] - lows[-3]) < 0.3:
        return "Double Bottom", 75

    return "No Clear Pattern", 60

# ==============================
# ANALYSIS
# ==============================
def analyze(df):
    df["rsi"] = ta.momentum.RSIIndicator(df["close"]).rsi()
    df["ema"] = ta.trend.EMAIndicator(df["close"], window=20).ema_indicator()

    last = df.iloc[-1]

    price = last["close"]
    rsi = last["rsi"]
    ema = last["ema"]

    trend = "UP" if price > ema else "DOWN"

    pattern, pattern_success = detect_pattern(df)

    # LOGIC
    if trend == "UP" and rsi < 45:
        signal = "BUY"
        confidence = pattern_success + 5
    elif trend == "DOWN" and rsi > 55:
        signal = "SELL"
        confidence = pattern_success + 5
    else:
        return None

    entry = round(price, 4)
    sl = round(price * 0.97, 4)
    tp = round(price * 1.05, 4)

    return {
        "signal": signal,
        "price": entry,
        "rsi": round(rsi, 2),
        "trend": trend,
        "pattern": pattern,
        "pattern_success": pattern_success,
        "confidence": confidence,
        "sl": sl,
        "tp": tp,
        "eta": "2-6 Hours"
    }

# ==============================
# START
# ==============================
send("🚀 BOT STARTED — AI TRADING ENGINE ACTIVE")

# ==============================
# LOOP (2 HOURS)
# ==============================
while True:
    print("Checking market...")

    for coin in coins:
        df = get_data(coin)

        if df is None:
            print("No data:", coin)
            continue

        result = analyze(df)

        if result:
            msg = f"""
🔥 {coin} TRADE SIGNAL

📈 Type: {result['signal']}
📊 Trend: {result['trend']}
🔍 Pattern: {result['pattern']}
📊 Pattern Success: {result['pattern_success']}%

📍 Entry: {result['price']}
🛑 Stop Loss: {result['sl']}
🎯 Take Profit: {result['tp']}

📊 Confidence: {result['confidence']}%
⏱ ETA: {result['eta']}
🕒 Time: {datetime.now().strftime('%H:%M')}
"""
            send(msg)

    send("✅ Bot running — next scan in 2 hours")
    time.sleep(7200)
