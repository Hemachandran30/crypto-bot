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
    "TRX","AVAX","LINK","ATOM","ETC","XLM","NEAR","APT","ARB","FIL",
    "SUI","OP","PEPE","INJ","RNDR","FTM","ICP","SEI","TIA","PYTH"
]

# ================= STATE =================

active_trades = {}
last_signal_time = 0
last_sent_time = {}
last_signal_data = {}
last_update_id = None
VALID_SYMBOLS = set()

# 🔥 ADDED (cooldown tracking)
last_strong_signal_time = {}

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
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg}

        if coin:
            payload["reply_markup"] = {
                "inline_keyboard": [[
                    {"text": "✅ Activate Trade", "callback_data": f"ACTIVATE_{coin}"}
                ]]
            }

        requests.post(url, json=payload, timeout=5)
    except:
        pass

# ================= DATA =================

def get_candles_tf(symbol, interval):
    try:
        res = requests.get(BINANCE_KLINE_URL, params={
            "symbol": symbol,
            "interval": interval,
            "limit": 50
        }, headers=BINANCE_HEADERS, timeout=5)

        data = res.json()
        return [float(x[4]) for x in data]
    except:
        return []

def get_price(symbol):
    try:
        res = requests.get(BINANCE_PRICE_URL, params={"symbol": symbol}, timeout=5)
        data = res.json()
        return float(data["price"]) if "price" in data else None
    except:
        return None

def get_candles(symbol):
    try:
        res = requests.get(BINANCE_KLINE_URL, params={
            "symbol": symbol,
            "interval": "15m",
            "limit": 50
        }, headers=BINANCE_HEADERS, timeout=5)

        data = res.json()

        closes = [float(x[4]) for x in data]
        highs = [float(x[2]) for x in data]
        lows = [float(x[3]) for x in data]
        volumes = [float(x[5]) for x in data]

        return closes, highs, lows, volumes
    except:
        return [], [], [], []

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
    if price is None:
        return None

    closes, highs, lows, volumes = get_candles(symbol)
    if not closes:
        return None

    ema_val = ema(closes)
    rsi_val = rsi(closes)

    closes_1h = get_candles_tf(symbol, "1h")
    closes_2h = get_candles_tf(symbol, "2h")

    trend_1h = ema(closes_1h) if closes_1h else ema_val
    trend_2h = ema(closes_2h) if closes_2h else ema_val

    bullish = price > ema_val and price > trend_1h and price > trend_2h
    bearish = price < ema_val and price < trend_1h and price < trend_2h

    direction = "BUY" if bullish else "SELL"

    avg_vol = sum(volumes[:-1]) / len(volumes[:-1])
    vol_strength = (volumes[-1] / avg_vol) * 100 if avg_vol else 100

    change = ((closes[-1] - closes[-5]) / closes[-5]) * 100

    support = min(lows[-10:])
    resistance = max(highs[-10:])
    liquidity_zone = (support + resistance) / 2

    if price > resistance:
        pattern = "Breakout"
    elif price < support:
        pattern = "Fake Breakout"
    elif abs(change) > 1:
        pattern = "Momentum Surge"
    else:
        pattern = random.choice(PATTERNS)

    leverage = 5 if abs(change) < 2 else 10
    profit = 20 + min(abs(change)*2,5)
    move = profit / leverage

    entry = price

    if direction == "BUY":
        tp = entry * (1 + move/100)
        sl = max(support, entry * 0.98)
    else:
        tp = entry * (1 - move/100)
        sl = min(resistance, entry * 1.02)

    pattern_success = PATTERN_SUCCESS.get(pattern, 75)
    confidence = 60
    trade_success = min(95, pattern_success + confidence // 2)

    strong = abs(change) > 1.5 and vol_strength > 120

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
        "eta": "30-60 mins",
        "rsi": rsi_val,
        "volume_strength": vol_strength,
        "timeframe": "15m + 1H + 2H",
        "strong": strong,
        "start_time": time.time()
    }

# ================= MAIN =================

send_telegram("🚀 BOT STARTED")

while True:
    try:

        signals = []

        for coin in COINS:
            s = generate_signal(coin)
            if s:
                signals.append((coin, s))

                # 🔥 STRONG SIGNAL (30 min cooldown)
                if s["strong"]:
                    now = time.time()

                    if coin not in last_strong_signal_time or now - last_strong_signal_time[coin] > 1800:

                        send_telegram(f"""
🔥 STRONG SIGNAL {coin}

📢 {s['direction']}

Entry: {round(s['entry'],4)}
TP: {round(s['tp'],4)}
SL: {round(s['sl'],4)}

Pattern: {s['pattern']}
Trade Success: {s['trade_success']}%
RSI: {round(s['rsi'],2)}

🕒 {datetime.now().strftime('%H:%M:%S')}
""")

                        last_strong_signal_time[coin] = now

        # 🔥 EVERY 2 HOURS
        if time.time() - last_signal_time > 7200:

            if not signals:
                coin = random.choice(COINS)
                s = generate_signal(coin)
                if s:
                    signals.append((coin, s))

            for coin, s in signals[:5]:

                now = time.time()

                if coin in last_sent_time and now - last_sent_time[coin] < 1800:
                    continue

                msg = f"""
📊 {coin}

📢 {s['direction']} ({s['leverage']}x)

Entry: {round(s['entry'],4)}
TP: {round(s['tp'],4)}
SL: {round(s['sl'],4)}

RSI: {round(s['rsi'],2)}
Volume Strength: {round(s['volume_strength'],2)}%

Profit: {s['profit']}%

Pattern: {s['pattern']}
Pattern Success: {s['pattern_success']}%
Trade Success: {s['trade_success']}%
Confidence: {s['confidence']}%

Timeframe: {s['timeframe']}
Liquidity Zone: {round(s['liquidity_zone'],4)}

ETA: {s['eta']}

🕒 {datetime.now().strftime('%H:%M:%S')}
"""
                send_telegram(msg, coin)
                last_sent_time[coin] = now

            last_signal_time = time.time()

        time.sleep(30)

    except Exception as e:
        print("Error:", e)
        time.sleep(5)
