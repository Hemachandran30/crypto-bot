import requests
import time
import pandas as pd
import ta
from datetime import datetime

# =========================
# TELEGRAM
# =========================
BOT_TOKEN = "8745061783:AAHqYr6pE7DRamJssybX_iyMmro7V_gSgrI"
CHAT_ID = "931982378"

def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print("Telegram Error:", e)

# =========================
# SETTINGS
# =========================
LEVERAGE = 10
SEND_INTERVAL = 10800  # 3 hours
SCAN_INTERVAL = 60
MIN_CONFIDENCE = 80

last_sent = 0

# =========================
# COINS (EXPANDED)
# =========================
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
    "DOT": "polkadot",
    "LINK": "chainlink",
    "LTC": "litecoin",
    "ATOM": "cosmos",
    "NEAR": "near",
    "APT": "aptos"
}

# =========================
# TIMEFRAMES
# =========================
timeframes = {
    "15m": "0.25",
    "30m": "0.5",
    "1h": "1",
    "2h": "2"
}

# =========================
# FETCH DATA
# =========================
def get_data(coin_id, hours):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": hours}

        res = requests.get(url, params=params)
        data = res.json()

        if "prices" not in data:
            return None

        prices = [p[1] for p in data["prices"]]

        df = pd.DataFrame(prices, columns=["close"])
        df["high"] = df["close"]
        df["low"] = df["close"]

        return df
    except:
        return None

# =========================
# ANALYSIS
# =========================
def analyze(df):
    df["ema"] = ta.trend.EMAIndicator(df["close"], 20).ema_indicator()
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], 14).rsi()

    price = df["close"].iloc[-1]
    ema = df["ema"].iloc[-1]
    rsi = df["rsi"].iloc[-1]

    # TREND
    if price > ema and rsi > 55:
        signal = "BUY"
        pattern = "EMA Bullish + RSI Strength"
    elif price < ema and rsi < 45:
        signal = "SELL"
        pattern = "EMA Bearish + RSI Weakness"
    else:
        return None

    confidence = 70

    if abs(price - ema) / ema > 0.01:
        confidence += 10
    if rsi > 65 or rsi < 35:
        confidence += 10

    if confidence < MIN_CONFIDENCE:
        return None

    # TP / SL (CORRECTED)
    if signal == "BUY":
        entry = price
        tp = price * 1.04
        sl = price * 0.98
    else:
        entry = price
        tp = price * 0.96
        sl = price * 1.02

    # PROFIT %
    profit_percent = abs((tp - entry) / entry) * 100

    return {
        "signal": signal,
        "entry": round(entry, 4),
        "tp": round(tp, 4),
        "sl": round(sl, 4),
        "confidence": confidence,
        "pattern": pattern,
        "profit": round(profit_percent, 2)
    }

# =========================
# MULTI TF ENGINE
# =========================
def multi_timeframe_analysis(symbol, coin_id):

    best_signal = None

    for tf_name, hours in timeframes.items():

        df = get_data(coin_id, hours)
        if df is None:
            continue

        result = analyze(df)

        if not result:
            continue

        result["timeframe"] = tf_name

        # choose strongest signal
        if not best_signal or result["confidence"] > best_signal["confidence"]:
            best_signal = result

    return best_signal

# =========================
# START
# =========================
send("🚀 BOT STARTED - PRO MODE ACTIVE")

# =========================
# LOOP
# =========================
while True:
    now = time.time()

    if now - last_sent >= SEND_INTERVAL:

        send("📊 SCANNING MARKET (MULTI-TF)...")

        for symbol, coin_id in coins.items():

            result = multi_timeframe_analysis(symbol, coin_id)

            if not result:
                continue

            eta_map = {
                "15m": "15-30 mins",
                "30m": "30-60 mins",
                "1h": "1-2 hours",
                "2h": "2-4 hours"
            }

            eta = eta_map.get(result["timeframe"], "Unknown")

            msg = f"""
📊 {symbol}

📢 Signal: {result['signal']} ({LEVERAGE}x)
💰 Entry: {result['entry']}
🎯 TP: {result['tp']}
🛑 SL: {result['sl']}

📊 Profit: {result['profit']}%
🧠 Pattern: {result['pattern']}
📈 Confidence: {result['confidence']}%

⏱ Timeframe: {result['timeframe']}
⏳ ETA: {eta}

🕒 Signal Time: {datetime.now().strftime('%H:%M:%S')}
"""

            send(msg)

        last_sent = now

    time.sleep(SCAN_INTERVAL)
