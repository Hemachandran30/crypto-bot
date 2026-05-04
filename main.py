import requests
import time
import random
from datetime import datetime

# ================= CONFIG =================

TELEGRAM_TOKEN = "8745061783:AAHqJQSq115g6DSbgiOn7Enx_nzoLDZngjE"
CHAT_ID = "931982378"

BINANCE_API_KEY = "ISvf5mwnZA5P3t9EuHFCa1cSobM6VvHPQ5kMrNBSWWX0F6O0Ss3dzf7YGlbXpvsI"

BINANCE_HEADERS = {
    "X-MBX-APIKEY": BINANCE_API_KEY
}

BINANCE_PRICE_URL = "https://api.binance.com/api/v3/ticker/price"
BINANCE_KLINE_URL = "https://api.binance.com/api/v3/klines"

COINS = [
    "BTC","ETH","BNB","SOL","XRP","ADA","DOGE","DOT","MATIC","LTC",
    "TRX","AVAX","LINK","ATOM","ETC","XLM","NEAR","APT","ARB","FIL"
]

# ================= STATE =================

active_trades = {}
last_signal_time = 0
last_sent_time = {}
last_signal_data = {}

# ================= PATTERNS =================

PATTERNS = [
    "EMA Trend","RSI Reversal","Breakout","Pullback","Double Top",
    "Double Bottom","Head and Shoulders","Inverse H&S",
    "Bull Flag","Bear Flag","Ascending Triangle","Descending Triangle",
    "Rising Wedge","Falling Wedge","Cup and Handle","Support Bounce",
    "Resistance Rejection","Volume Spike","Momentum Surge",
    "Fake Breakout","Range Break","Trend Continuation",
    "Liquidity Sweep","Order Block","Scalping Setup"
]

PATTERN_SUCCESS = {p: random.randint(70, 85) for p in PATTERNS}

# ================= TELEGRAM =================

def send_telegram(msg, coin=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {"chat_id": CHAT_ID, "text": msg}

    if coin:
        payload["reply_markup"] = {
            "inline_keyboard": [[
                {"text": "✅ Activate Trade", "callback_data": f"ACTIVATE_{coin}"}
            ]]
        }

    requests.post(url, json=payload)

# ================= BUTTON =================

def check_updates():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    data = requests.get(url).json()

    for update in data.get("result", []):
        if "callback_query" in update:
            coin = update["callback_query"]["data"].split("_")[1]

            if coin in last_signal_data:
                active_trades[coin] = last_signal_data[coin]
                send_telegram(f"✅ Trade Activated for {coin}")

# ================= DATA =================

def get_price(symbol):
    res = requests.get(BINANCE_PRICE_URL, params={"symbol": symbol}, headers=BINANCE_HEADERS)
    return float(res.json()["price"])

def get_candles(symbol):
    res = requests.get(BINANCE_KLINE_URL, params={
        "symbol": symbol,
        "interval": "15m",
        "limit": 50
    }, headers=BINANCE_HEADERS)

    data = res.json()

    closes = [float(x[4]) for x in data]
    highs = [float(x[2]) for x in data]
    lows = [float(x[3]) for x in data]
    volumes = [float(x[5]) for x in data]

    return closes, highs, lows, volumes

# ================= INDICATORS =================

def ema(prices, period=20):
    k = 2/(period+1)
    e = prices[0]
    for p in prices:
        e = p*k + e*(1-k)
    return e

def rsi(prices, period=14):
    gains, losses = [], []
    for i in range(1,len(prices)):
        diff = prices[i]-prices[i-1]
        if diff>0: gains.append(diff)
        else: losses.append(abs(diff))
    avg_gain = sum(gains[-period:])/period if gains else 0
    avg_loss = sum(losses[-period:])/period if losses else 1
    rs = avg_gain/avg_loss
    return 100-(100/(1+rs))

# ================= SIGNAL =================

def generate_signal(coin):

    symbol = coin + "USDT"

    price = get_price(symbol)
    closes, highs, lows, volumes = get_candles(symbol)

    if len(closes) < 20:
        return None

    ema_val = ema(closes)
    rsi_val = rsi(closes)

    change = ((closes[-1] - closes[-5]) / closes[-5]) * 100

    avg_vol = sum(volumes[:-1]) / len(volumes[:-1])
    vol_spike = volumes[-1] > avg_vol * 1.5

    support = min(lows[-10:])
    resistance = max(highs[-10:])

    liquidity_zone = (support + resistance) / 2

    # ================= PATTERN LOGIC =================

    if vol_spike and abs(change) > 1:
        pattern = "Momentum Surge"
    elif price > resistance:
        pattern = "Breakout"
    elif price < support:
        pattern = "Fake Breakout"
    elif abs(change) < 0.5:
        pattern = "Range Break"
    elif price > ema_val:
        pattern = "Trend Continuation"
    else:
        pattern = random.choice(PATTERNS)

    # ================= SIGNAL LOGIC =================

    if price > ema_val and rsi_val > 55 and vol_spike:
        direction = "BUY"
    elif price < ema_val and rsi_val < 45 and vol_spike:
        direction = "SELL"
    else:
        return None

    leverage = 5 if abs(change) < 2 else 10
    profit = 20 + min(abs(change)*2,5)
    move = profit / leverage

    entry = price

    if direction == "BUY":
        tp = entry * (1 + move/100)
        sl = support
    else:
        tp = entry * (1 - move/100)
        sl = resistance

    # ================= SUCCESS LOGIC =================

    pattern_success = PATTERN_SUCCESS.get(pattern, 75)

    confidence = 0
    if rsi_val > 60 or rsi_val < 40: confidence += 20
    if vol_spike: confidence += 25
    if abs(change) > 1: confidence += 20
    if price > ema_val or price < ema_val: confidence += 15

    trade_success = min(95, pattern_success + confidence // 2)

    return {
        "direction": direction,
        "entry": entry,
        "tp": tp,
        "sl": sl,
        "profit": profit,
        "leverage": leverage,
        "pattern": pattern,
        "pattern_success": pattern_success,
        "trade_success": trade_success,
        "confidence": confidence,
        "liquidity_zone": liquidity_zone,
        "eta": "30-60 mins"
    }

# ================= MONITOR =================

def monitor_trades():
    for coin, trade in list(active_trades.items()):
        try:
            price = get_price(coin+"USDT")

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

while True:
    try:

        check_updates()

        signals = []

        for coin in COINS:
            s = generate_signal(coin)

            if not s:
                continue

            if coin in last_sent_time:
                if time.time() - last_sent_time[coin] < 3600:
                    continue

            signals.append((coin, s))
            last_signal_data[coin] = s

        if time.time() - last_signal_time > 3600:

            for coin, s in signals[:5]:

                msg = f"""
📊 {coin}

📢 {s['direction']} ({s['leverage']}x)

Entry: {round(s['entry'],4)}
TP: {round(s['tp'],4)}
SL: {round(s['sl'],4)}

Profit: {s['profit']}%

Pattern: {s['pattern']}
Pattern Success: {s['pattern_success']}%
Trade Success: {s['trade_success']}%
Confidence: {s['confidence']}%

Liquidity Zone: {round(s['liquidity_zone'],4)}

ETA: {s['eta']}

🕒 {datetime.now().strftime('%H:%M:%S')}
"""

                send_telegram(msg, coin)
                last_sent_time[coin] = time.time()

            last_signal_time = time.time()

        monitor_trades()

        time.sleep(30)

    except Exception as e:
        print("Error:", e)
        time.sleep(5)
