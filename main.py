import requests
import time
import pandas as pd
import ta
from datetime import datetime

# ==============================
# 🔐 TELEGRAM (YOUR REAL TOKEN ADDED)
# ==============================
BOT_TOKEN = "8745061783:AAFu0AGFM0NUIEw3KAkZIDgzKSq2jBdW0Sc"
CHAT_ID = "931982378"

def send(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
        print("Sent:", msg)
    except Exception as e:
        print("Telegram Error:", e)

# ==============================
# 🪙 COINS (10 coins)
# ==============================
coins = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT",
    "ADAUSDT", "DOGEUSDT", "MATICUSDT", "AVAXUSDT", "DOTUSDT"
]

# ==============================
# 📊 GET MARKET DATA
# ==============================
def get_data(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=15m&limit=100"
    res = requests.get(url).json()

    if isinstance(res, list):
        df = pd.DataFrame(res)
        df = df[[0,1,2,3,4,5]]
        df.columns = ["time","open","high","low","close","volume"]

        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)

        return df
    return None

# ==============================
# 🧠 ANALYSIS
# ==============================
def analyze(df):
    df["rsi"] = ta.momentum.RSIIndicator(df["close"]).rsi()
    df["ema"] = ta.trend.EMAIndicator(df["close"], window=20).ema_indicator()

    price = df["close"].iloc[-1]
    rsi = df["rsi"].iloc[-1]
    ema = df["ema"].iloc[-1]
    volume = df["volume"].iloc[-1]

    trend = "UP" if price > ema else "DOWN"

    if trend == "UP" and rsi < 45:
        signal = "BUY"
        confidence = round(70 + (45 - rsi), 2)
    elif trend == "DOWN" and rsi > 55:
        signal = "SELL"
        confidence = round(70 + (rsi - 55), 2)
    else:
        return None

    entry = price
    sl = round(price * 0.97, 4)
    tp = round(price * 1.05, 4)

    eta = "2-6 Hours"

    return {
        "signal": signal,
        "price": price,
        "rsi": round(rsi, 2),
        "ema": round(ema, 2),
        "volume": round(volume, 2),
        "trend": trend,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "confidence": confidence,
        "eta": eta
    }

# ==============================
# 🚀 MAIN LOOP
# ==============================
send("🚀 BOT STARTED — Monitoring Market")

while True:
    print("Checking market...")

    for coin in coins:
        try:
            df = get_data(coin)

            if df is None:
                print("No data:", coin)
                continue

            result = analyze(df)

            if result:
                msg = f"""
🔥 {coin} SIGNAL

Type: {result['signal']}
Trend: {result['trend']}
RSI: {result['rsi']}
EMA: {result['ema']}

📍 Entry: {result['entry']}
🎯 Take Profit: {result['tp']}
🛑 Stop Loss: {result['sl']}

📊 Confidence: {result['confidence']}%
⏱ ETA: {result['eta']}
"""
                send(msg)

        except Exception as e:
            print("Error:", coin, e)

    send("✅ Bot Running — Next check in 2 hours")

    time.sleep(7200)
