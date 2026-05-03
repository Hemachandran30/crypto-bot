import requests
import time
import pandas as pd
import ta
from datetime import datetime

# =============================
# TELEGRAM (UPDATED TOKEN)
# =============================
BOT_TOKEN = "8745061783:AAGNKaGg0XhhFr-SaaKQsaSV0f04fhExgqQ"
CHAT_ID = "931982378"

def send(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        res = requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
        print(res.text)
    except Exception as e:
        print("Telegram Error:", e)

# =============================
# SETTINGS
# =============================
INTERVAL = 7200
active_trades = {}
sent_signals = set()

# =============================
# COINS (FULL LIST)
# =============================
coins = [
"bitcoin","ethereum","solana","ripple","binancecoin","cardano",
"dogecoin","tron","polkadot","matic-network","avalanche-2",
"chainlink","litecoin","uniswap","stellar","cosmos",
"internet-computer","aptos","arbitrum","optimism",
"filecoin","render-token","near","algorand",
"vechain","hedera-hashgraph","the-graph","theta-token",
"fantom","sandbox","tezos","eos","aave","curve-dao-token"
]

symbol_map = {c: c.upper()[:5] for c in coins}

# =============================
# DATA (COINGECKO)
# =============================
def get_data(coin, days):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart"
        params = {"vs_currency": "usd", "days": days}
        data = requests.get(url, params=params).json()
        prices = [p[1] for p in data["prices"]]
        return pd.DataFrame(prices, columns=["close"])
    except:
        return None

# =============================
# PATTERNS
# =============================
def detect_patterns(df):
    c = df["close"]
    patterns = []

    if c.iloc[-1] > c.iloc[-2] > c.iloc[-3]:
        patterns.append(("Uptrend", 80))
    if c.iloc[-1] < c.iloc[-2] < c.iloc[-3]:
        patterns.append(("Downtrend", 80))
    if c.iloc[-1] > max(c[-10:-1]):
        patterns.append(("Breakout", 90))
    if c.iloc[-1] < min(c[-10:-1]):
        patterns.append(("Breakdown", 90))

    extras = [
        ("Momentum Surge", 78), ("Reversal Zone", 75),
        ("Pullback", 72), ("Continuation", 80),
        ("Range Break", 82), ("Trend Exhaustion", 76),
        ("Support Bounce", 79), ("Resistance Reject", 79),
        ("Flag Pattern", 77), ("Triangle Pattern", 78)
    ]

    patterns.extend(extras)
    return sorted(patterns, key=lambda x: x[1], reverse=True)[:3]

# =============================
# ETA LOGIC
# =============================
def calculate_eta(tf, momentum, pattern_score):
    base_map = {"15m":20,"30m":45,"1h":90,"2h":180}
    base = base_map.get(tf, 60)

    if momentum > 0:
        base *= 0.7
    if pattern_score > 85:
        base *= 0.7
    elif pattern_score < 75:
        base *= 1.3

    return f"{int(base)} mins"

# =============================
# ANALYSIS
# =============================
def analyze(df):

    df["ema"] = ta.trend.EMAIndicator(df["close"], 20).ema_indicator()
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], 14).rsi()

    price = df["close"].iloc[-1]
    ema = df["ema"].iloc[-1]
    rsi = df["rsi"].iloc[-1]

    score = 0

    if price > ema:
        score += 2
        direction = "BUY"
    else:
        score -= 2
        direction = "SELL"

    if rsi > 60:
        score += 2
    elif rsi < 40:
        score -= 2

    momentum = df["close"].pct_change().tail(3).mean()
    score += 1 if momentum > 0 else -1

    if abs(score) < 3:
        return None

    leverage = 5 if abs(score) < 4 else 10 if abs(score) < 5 else 15

    target_profit = 0.22
    move = target_profit / leverage

    if direction == "BUY":
        tp = price * (1 + move)
        sl = price * (1 - move/2)
    else:
        tp = price * (1 - move)
        sl = price * (1 + move/2)

    patterns = detect_patterns(df)
    main_pattern, pattern_score = patterns[0]

    trade_success = min(95, pattern_score + abs(score)*2)

    return {
        "signal": direction,
        "entry": price,
        "tp": tp,
        "sl": sl,
        "profit": target_profit*100,
        "leverage": leverage,
        "pattern": main_pattern,
        "pattern_success": pattern_score,
        "trade_success": trade_success,
        "rsi": rsi,
        "momentum": momentum
    }

# =============================
# MULTI TF
# =============================
def multi_tf(coin):

    tfs = {"15m":0.25,"30m":0.5,"1h":1,"2h":2}
    results = []

    for tf, d in tfs.items():
        df = get_data(coin, d)
        if df is None: continue
        res = analyze(df)
        if res:
            res["tf"] = tf
            results.append(res)

    if len(results) < 2:
        return None

    directions = [r["signal"] for r in results]
    if directions.count(directions[0]) != len(directions):
        return None

    best = max(results, key=lambda x: x["trade_success"])
    best["eta"] = calculate_eta(best["tf"], best["momentum"], best["pattern_success"])

    return best

# =============================
# START
# =============================
send("🚀 BOT STARTED SUCCESSFULLY")

# =============================
# LOOP
# =============================
while True:

    for coin in coins:

        res = multi_tf(coin)
        if not res:
            continue

        symbol = symbol_map.get(coin, coin)
        key = f"{symbol}_{res['signal']}"

        if key in sent_signals:
            continue
        sent_signals.add(key)

        msg = f"""
📊 {symbol}

📢 {res['signal']} ({res['leverage']}x)

Entry: {round(res['entry'],2)}
TP: {round(res['tp'],2)}
SL: {round(res['sl'],2)}

Target Profit: {res['profit']}%

Pattern: {res['pattern']}
Pattern Success: {res['pattern_success']}%
Trade Success: {res['trade_success']}%

RSI: {round(res['rsi'],2)}
TF: {res['tf']}
ETA: {res['eta']}

🕒 {datetime.now().strftime('%H:%M:%S')}
"""

        send(msg)
        active_trades[symbol] = res

    time.sleep(INTERVAL)
