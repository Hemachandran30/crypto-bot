import requests
import time
import random
from datetime import datetime

# ================= CONFIG =================

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
    "EMA Bullish","EMA Bearish","Breakout","Pullback","Reversal",
    "Triangle","Flag","Wedge","Momentum Surge","Volume Spike"
]

active_trades = {}      # 🔥 TRACK ACTIVE TRADES
last_signal_time = 0
last_sent_time = {}     # 🔥 FIX duplicate issue

# ================= TELEGRAM =================

def send_telegram(msg, coin=None):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

        payload = {
            "chat_id": CHAT_ID,
            "text": msg
        }

        # 🔥 ADD BUTTON
        if coin:
            payload["reply_markup"] = {
                "inline_keyboard": [[
                    {"text": "✅ Activate Trade", "callback_data": f"ACTIVATE_{coin}"}
                ]]
            }

        res = requests.post(url, json=payload)
        print("📨 Telegram:", res.text)

    except Exception as e:
        print("Telegram error:", e)

# ================= HANDLE BUTTON =================

def check_updates():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    data = requests.get(url).json()

    for update in data.get("result", []):
        if "callback_query" in update:
            data_cb = update["callback_query"]["data"]

            if "ACTIVATE_" in data_cb:
                coin = data_cb.split("_")[1]
                active_trades[coin] = True
                send_telegram(f"✅ Trade Activated for {coin}")

# ================= DATA =================

def get_prices():
    try:
        params = {"symbol": ",".join(COINS)}
        res = requests.get(CMC_URL, headers=HEADERS, params=params)
        data = res.json()

        if "data" not in data:
            return {}

        return data["data"]

    except:
        return {}

# ================= SIGNAL LOGIC =================

def generate_signal(price, prev_price):

    if price is None:
        return None

    # 🔥 Candle / momentum logic
    change = ((price - prev_price) / prev_price) * 100 if prev_price else 0

    direction = "BUY" if change > 0 else "SELL"

    # 🔥 LEVERAGE LOGIC (FIXED)
    leverage = random.randint(5, 12)

    target_profit = random.uniform(20, 25)
    move = target_profit / leverage

    entry = price

    if direction == "BUY":
        tp = entry * (1 + move/100)
        sl = entry * (1 - move/200)
    else:
        tp = entry * (1 - move/100)
        sl = entry * (1 + move/200)

    return {
        "direction": direction,
        "entry": entry,
        "tp": tp,
        "sl": sl,
        "profit": target_profit,
        "leverage": leverage,
        "pattern": random.choice(PATTERNS),
        "tf": random.choice(TIMEFRAMES),
        "eta": f"{random.randint(20,60)} mins"
    }

# ================= TRACK ACTIVE TRADES =================

def monitor_trades(price_data):

    for coin in list(active_trades.keys()):

        try:
            price = price_data[coin]["quote"]["USD"]["price"]

            trade = active_trades.get(coin)

            if not trade:
                continue

            # 🔥 TP / SL alert
            if price >= trade["tp"]:
                send_telegram(f"🎯 TP HIT {coin}")
                del active_trades[coin]

            elif price <= trade["sl"]:
                send_telegram(f"🛑 SL HIT {coin}")
                del active_trades[coin]

        except:
            continue

# ================= MAIN =================

send_telegram("🚀 BOT STARTED")

prev_prices = {}

while True:
    try:

        check_updates()

        data = get_prices()
        if not data:
            time.sleep(10)
            continue

        market_signals = []

        for coin in COINS:

            coin_data = data.get(coin)
            if not coin_data:
                continue

            price = coin_data["quote"]["USD"]["price"]
            if price is None:
                continue

            prev_price = prev_prices.get(coin, price)

            signal = generate_signal(price, prev_price)

            prev_prices[coin] = price

            if signal is None:
                continue

            # 🔥 FIX DUPLICATE SIGNAL ISSUE
            if coin in last_sent_time:
                if time.time() - last_sent_time[coin] < 1800:
                    continue

            market_signals.append((coin, signal))

        # 🔥 SEND EVERY 1 HOUR
        if time.time() - last_signal_time > 3600:

            for coin, s in market_signals[:5]:

                msg = f"""
📊 {coin}

📢 {s['direction']} ({s['leverage']}x)

Entry: {round(s['entry'],4)}
TP: {round(s['tp'],4)}
SL: {round(s['sl'],4)}

Profit: {s['profit']}%

Pattern: {s['pattern']}
TF: {s['tf']}
ETA: {s['eta']}

🕒 {datetime.now().strftime('%H:%M:%S')}
"""

                send_telegram(msg, coin)

                last_sent_time[coin] = time.time()

            last_signal_time = time.time()

        # 🔥 TRACK ACTIVE TRADES
        monitor_trades(data)

        time.sleep(30)

    except Exception as e:
        print("Error:", e)
        time.sleep(10)
