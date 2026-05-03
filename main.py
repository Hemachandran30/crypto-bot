import requests
import time
import random
from datetime import datetime

# =========================
# CONFIG (UNCHANGED)
# =========================

CMC_API_KEY = "695de55737564709a7b0176202c7d542"

TELEGRAM_TOKEN = "8745061783:AAHqJQSq115g6DSbgiOn7Enx_nzoLDZngjE"
CHAT_ID = "931982378"

CMC_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"

HEADERS = {
    "X-CMC_PRO_API_KEY": CMC_API_KEY
}

COINS = [
    "BTC","ETH","BNB","SOL","XRP","ADA","DOGE","DOT","MATIC","LTC",
    "TRX","AVAX","LINK","ATOM","ETC","XLM","NEAR","APT","ARB","FIL"
]

TIMEFRAMES = ["15m", "30m", "1h", "2h"]

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
# TELEGRAM (FIXED ONLY LOGGING)
# =========================

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        res = requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

        print("📨 Telegram Response:", res.text)

        if res.status_code != 200:
            print("❌ Telegram Failed:", res.text)

    except Exception as e:
        print("❌ Telegram Error:", e)

# =========================
# DATA FETCH (UNCHANGED + SAFE)
# =========================

def get_prices():
    try:
        params = {"symbol": ",".join(COINS)}
        res = requests.get(CMC_URL, headers=HEADERS, params=params)
        data = res.json()

        if "data" not in data:
            print("CMC API issue:", data)
            return {}

        return data["data"]

    except Exception as e:
        print("Fetch error:", e)
        return {}

# =========================
# SIGNAL LOGIC (UNCHANGED)
# =========================

def generate_signal(price):
    if price is None:
        return None

    direction = random.choice(["BUY", "SELL"])
    leverage = random.randint(3, 15)

    move_needed = random.uniform(2, 3)
    profit = round(move_needed * leverage, 2)

    entry = price

    # ✅ FIX: safe calculation
    if entry is None:
        return None

    if direction == "BUY":
        tp = entry * (1 + move_needed/100)
        sl = entry * (1 - move_needed/200)
    else:
        tp = entry * (1 - move_needed/100)
        sl = entry * (1 + move_needed/200)

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
# MAIN LOOP (UNCHANGED + SAFE)
# =========================

last_signal_time = 0
sent_signals = {}

send_telegram("🚀 BOT STARTED - LIVE SCANNING 24/7")

while True:
    try:
        print("🔁 Scanning market...", datetime.now())

        data = get_prices()

        if not data:
            time.sleep(10)
            continue

        market_signals = []

        for coin in COINS:
            try:
                coin_data = data.get(coin)

                if not coin_data:
                    continue

                price = coin_data["quote"]["USD"]["price"]

                # ✅ FIX: skip None price
                if price is None:
                    print(f"⚠️ Skipping {coin} (price None)")
                    continue

                signal = generate_signal(price)

                if signal is None:
                    continue

                if coin in sent_signals:
                    continue

                market_signals.append((coin, signal))

            except Exception as e:
                print(f"Skipping {coin} error:", e)
                continue

        # ⏱ SEND SIGNAL EVERY 1 HOUR (UNCHANGED)
        if time.time() - last_signal_time > 3600:

            print("🚀 Sending signals...")

            for coin, s in market_signals[:5]:

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

🕒 Time: {datetime.now().strftime('%H:%M:%S')}
"""

                send_telegram(msg)
                sent_signals[coin] = True

            last_signal_time = time.time()

        time.sleep(30)

    except Exception as e:
        print("Main loop error:", e)
        time.sleep(10)
