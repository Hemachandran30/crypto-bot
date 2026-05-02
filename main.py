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
    "bitcoin", "ethereum", "solana", "ripple",
    "binancecoin", "cardano", "dogecoin",
    "matic-network", "avalanche-2", "polkadot"
]

# ✅ COINGECKO (NO BLOCK)
def get_price(coin):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart?vs_currency=usd&days=1"
        res = requests.get(url)
        data = res.json()

        prices = [p[1] for p in data["prices"]]

        df = pd.DataFrame(prices, columns=["close"])
        df["high"] = df["close"]
        df["low"] = df["close"]

        return df

    except Exception as e:
        print("Fetch error:", e)
        return None

def detect_patterns(df):
    closes = df["close"].values

    patterns = []

    if closes[-1] > max(closes[-10:-1]):
        patterns.append(("Breakout", 85))

    if closes[-1] < min(closes[-10:-1]):
        patterns.append(("Breakdown", 85))

    if closes[-1] > closes[-2] > closes[-3]:
        patterns.append(("Strong Uptrend", 80))

    if closes[-1] < closes[-2] < closes[-3]:
        patterns.append(("Strong Downtrend", 80))

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
        df = get_price(coin)

        if df is None:
            continue

        result = analyze(df)

        if result:
            signal, entry, sl, tp, score, pattern = result

            msg = f"""
📊 {coin.upper()}

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
