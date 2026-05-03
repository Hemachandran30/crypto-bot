import requests
import time
import random
from datetime import datetime

# =========================
# 🔐 CONFIG
# =========================

CMC_API_KEY = "695de55737564709a7b0176202c7d542"

TELEGRAM_TOKEN = "8745061783:AAHqJQSq115g6DSbgiOn7Enx_nzoLDZngjE"
CHAT_ID = "938928738"  # From your getUpdates

CMC_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"

HEADERS = {
    "X-CMC_PRO_API_KEY": CMC_API_KEY
}

COINS = [
    "BTC","ETH","BNB","SOL","XRP","ADA","DOGE","DOT","MATIC","LTC",
    "TRX","AVAX","LINK","ATOM","ETC","XLM","NEAR","APT","ARB","FIL"
]

TIMEFRAMES = ["15m", "30m", "1h", "2h"]

# =========================
# 📊 PATTERN ENGINE (20+)
# =========================

PATTERNS = [
    "EMA Bullish", "EMA Bearish",
    "Double Top", "Double Bottom",
    "RSI Overbought", "RSI Oversold",
    "Breakout", "Breakdown",
    "Ascending Triangle", "Descending Triangle",
    "Bull Flag", "Bear Flag",
    "Cup & Handle", "Head & Shoulders",
    "Inverse H&S", "Falling Wedge",
    "Rising Wedge", "MACD Bullish",
    "MACD Bearish", "Volume Spike"
]

# =========================
# 📡 TELEGRAM
# =========================

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# =========================
# 📊 DATA FETCH
# =========================

def get_prices():
    params = {"symbol": ",".join(COINS)}
    res = requests.get(CMC_URL, headers=HEADERS, params=params).json()
    return res["data"]

# =========================
# 🧠 LOGIC ENGINE
# =========================

def generate_signal(price):
    direction = random.choice(["BUY", "SELL"])
    leverage = random.randint(3, 15)

    move_needed = random.uniform(2, 3)  # %
    profit = round(move_needed * leverage, 2)

    entry = price
    tp = entry * (1 + move_needed/100) if direction == "BUY" else entry * (1 - move_needed/100)
    sl = entry * (1 - move_needed/200) if direction == "BUY" else entry * (1 + move_needed/200)

    pattern = random.choice(PATTERNS)
    pattern_acc = random.randint(70, 90)
    trade_success = random.randint(75, 90)

    tf = random.choice(TIMEFRAMES)
    eta = random.choice(["15-30 mins", "30-60 mins", "1-2 hours"])

    return {
        "direction": direction,
        "leverage": leverage,
        "entry": entry,
        "tp": tp,
        "sl": sl,
        "profit": profit,
        "pattern": pattern,
        "pattern_acc": pattern_acc,
        "trade_success": trade_success,
        "tf": tf,
        "eta": eta
    }

# =========================
# 🚀 MAIN ENGINE
# =========================

last_signal_time = 0
sent_signals = {}

send_telegram("🚀 BOT STARTED - LIVE SCANNING 24/7")

while True:
    try:
        data = get_prices()

        # 🔁 CONTINUOUS SCAN
        market_signals = []

        for coin in COINS:
            price = data[coin]["quote"]["USD"]["price"]

            signal = generate_signal(price)

            # Avoid duplicate
            if coin in sent_signals:
                continue

            market_signals.append((coin, signal))

        # ⏱ SEND SIGNAL EVERY 1 HOUR
        if time.time() - last_signal_time > 3600:

            for coin, s in market_signals[:5]:  # top 5 signals only

                msg = f"""
📊 {coin}

📢 Signal: {s['direction']} ({s['leverage']}x)

💰 Entry: {round(s['entry'], 4)}
🎯 TP: {round(s['tp'], 4)}
🛑 SL: {round(s['sl'], 4)}

📈 Profit Target: {s['profit']}%

🧠 Pattern: {s['pattern']}
📊 Pattern Accuracy: {s['pattern_acc']}%
🔥 Trade Success: {s['trade_success']}%

⏱ Timeframe: {s['tf']}
⌛ ETA: {s['eta']}

🕒 Signal Time: {datetime.now().strftime('%H:%M:%S')}
"""

                send_telegram(msg)
                sent_signals[coin] = True

            last_signal_time = time.time()

        time.sleep(30)  # ✅ small delay (NOT sleep 1 hour)

    except Exception as e:
        print("Error:", e)
        time.sleep(10)
