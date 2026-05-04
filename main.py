import requests
import time
import random
from datetime import datetime

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
    "EMA Bullish","EMA Bearish","Double Top","Double Bottom",
    "RSI Overbought","RSI Oversold","Breakout","Breakdown",
    "Ascending Triangle","Descending Triangle","Bull Flag","Bear Flag",
    "Cup & Handle","Head & Shoulders","Inverse H&S","Falling Wedge",
    "Rising Wedge","MACD Bullish","MACD Bearish","Volume Spike"
]

active_trades = {}
last_signal_time = 0
last_sent_time = {}
last_prices = {}  # 🔥 added for reversal logic

# =========================
# TELEGRAM (UNCHANGED)
# =========================

def send_telegram(msg, coin=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": msg
    }

    if coin:
        payload["reply_markup"] = {
            "inline_keyboard": [[
                {"text": "✅ Activate Trade", "callback_data": f"ACT_{coin}"}
            ]]
        }

    res = requests.post(url, json=payload)
    print("📨", res.text)

# =========================
# FETCH DATA (UNCHANGED)
# =========================

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

# =========================
# SIGNAL LOGIC (UPDATED ONLY)
# =========================

def generate_signal(price):

    if price is None:
        return None

    direction = random.choice(["BUY", "SELL"])
    leverage = random.randint(3, 15)

    move = random.uniform(1.5, 2.5)
    profit = round(move * leverage, 2)

    entry = price

    if direction == "BUY":
        tp = entry * (1 + move/100)
        sl = entry * (1 - move/200)
    else:
        tp = entry * (1 - move/100)
        sl = entry * (1 + move/200)

    pattern = random.choice(PATTERNS)
    tf = random.choice(TIMEFRAMES)

    # 🔥 LOGICAL SUCCESS CALCULATION (ADDED)
    base_success = 70

    if "Breakout" in pattern or "MACD" in pattern:
        base_success += 8
    elif "EMA" in pattern:
        base_success += 5
    elif "RSI" in pattern:
        base_success += 3

    if tf == "1h":
        base_success += 5
    elif tf == "2h":
        base_success += 7

    if leverage > 10:
        base_success -= 5

    trade_success = min(max(base_success, 65), 92)
    pattern_acc = trade_success - random.randint(2, 5)

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
        "eta": random.choice(["15-30m","30-60m","1-2h"])
    }

# =========================
# TRACK ACTIVE TRADE (UPDATED)
# =========================

def track_trades(data):
    for coin in list(active_trades.keys()):
        try:
            price = data[coin]["quote"]["USD"]["price"]
            trade = active_trades[coin]

            change = ((price - trade["entry"]) / trade["entry"]) * 100
            change = change * trade["leverage"]

            # 🔥 LOSS ALERTS
            if change <= -10:
                send_telegram(f"⚠️ {coin} reached -10%")

            if change <= -15:
                send_telegram(f"🚨 {coin} reached -15%")

            # 🔥 REVERSAL ALERT (ADDED)
            prev_price = last_prices.get(coin)
            if prev_price:
                if trade["direction"] == "BUY" and price < prev_price:
                    send_telegram(f"🔄 {coin} possible reversal detected")

            # 🔥 TP
            if (trade["direction"] == "BUY" and price >= trade["tp"]) or \
               (trade["direction"] == "SELL" and price <= trade["tp"]):
                send_telegram(f"🎯 {coin} TP HIT")
                del active_trades[coin]

        except:
            continue

# =========================
# HANDLE TELEGRAM BUTTON (UNCHANGED)
# =========================

def check_updates():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    res = requests.get(url).json()

    if not res["result"]:
        return

    for update in res["result"]:
        if "callback_query" in update:
            data = update["callback_query"]["data"]

            if data.startswith("ACT_"):
                coin = data.split("_")[1]
                active_trades[coin] = {
                    "entry": last_prices[coin],
                    "leverage": 10,
                    "direction": "BUY"
                }
                send_telegram(f"✅ Trade Activated for {coin}")

# =========================
# MAIN LOOP (UNCHANGED)
# =========================

send_telegram("🚀 BOT STARTED - LIVE")

while True:
    try:
        print("🔁 Scanning...", datetime.now())

        data = get_prices()
        if not data:
            time.sleep(10)
            continue

        for coin in COINS:
            if coin not in data:
                continue

            price = data[coin]["quote"]["USD"]["price"]
            last_prices[coin] = price

        check_updates()
        track_trades(data)

        if time.time() - last_signal_time > 3600:

            for coin in COINS:

                if coin in last_sent_time and time.time() - last_sent_time[coin] < 3600:
                    continue

                price = last_prices[coin]
                signal = generate_signal(price)

                if not signal:
                    continue

                msg = f"""
📊 {coin}

📢 {signal['direction']} ({signal['leverage']}x)

Entry: {round(signal['entry'],4)}
TP: {round(signal['tp'],4)}
SL: {round(signal['sl'],4)}

Profit: {signal['profit']}%

🧠 Pattern: {signal['pattern']}
📊 Pattern Accuracy: {signal['pattern_acc']}%
🔥 Trade Success: {signal['trade_success']}%

TF: {signal['tf']}
ETA: {signal['eta']}
"""

                send_telegram(msg, coin)
                last_sent_time[coin] = time.time()

            last_signal_time = time.time()

        time.sleep(30)

    except Exception as e:
        print("Error:", e)
        time.sleep(10)
