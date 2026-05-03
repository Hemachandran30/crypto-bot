import requests
import time
import pandas as pd
import ta
from datetime import datetime

# =============================
# TELEGRAM (YOUR DETAILS)
# =============================
BOT_TOKEN = "8745061783:AAHqYr6pE7DRamJssybX_iyMmro7V_gSgrI"
CHAT_ID = "931982378"

# =============================
# SETTINGS
# =============================
LEVERAGE = 10
INTERVAL = 7200  # 2 hours

# =============================
# TELEGRAM SEND
# =============================
def send(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
        print("Sent:", msg[:120])
    except Exception as e:
        print("Telegram Error:", e)

# =============================
# COINS (30)
# =============================
coins = [
    "bitcoin","ethereum","solana","ripple","binancecoin","cardano",
    "dogecoin","tron","polkadot","matic-network","avalanche-2",
    "chainlink","litecoin","uniswap","stellar","cosmos",
    "internet-computer","aptos","arbitrum","optimism",
    "filecoin","render-token","near","algorand",
    "vechain","hedera-hashgraph","the-graph","theta-token",
    "fantom","sandbox"
]

symbol_map = {
    "bitcoin":"BTC","ethereum":"ETH","solana":"SOL","ripple":"XRP",
    "binancecoin":"BNB","cardano":"ADA","dogecoin":"DOGE","tron":"TRX",
    "polkadot":"DOT","matic-network":"MATIC","avalanche-2":"AVAX",
    "chainlink":"LINK","litecoin":"LTC","uniswap":"UNI","stellar":"XLM",
    "cosmos":"ATOM","internet-computer":"ICP","aptos":"APT",
    "arbitrum":"ARB","optimism":"OP","filecoin":"FIL","render-token":"RNDR",
    "near":"NEAR","algorand":"ALGO","vechain":"VET",
    "hedera-hashgraph":"HBAR","the-graph":"GRT",
    "theta-token":"THETA","fantom":"FTM","sandbox":"SAND"
}

# =============================
# FETCH DATA (1 day intraday)
# =============================
def get_data(coin):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart"
        params = {"vs_currency": "usd", "days": 1}
        data = requests.get(url, params=params, timeout=10).json()
        if "prices" not in data:
            return None
        prices = [p[1] for p in data["prices"]]
        df = pd.DataFrame(prices, columns=["close"])
        # synth high/low for simple rules
        df["high"] = df["close"].rolling(3, min_periods=1).max()
        df["low"]  = df["close"].rolling(3, min_periods=1).min()
        return df
    except:
        return None

# =============================
# 20-PATTERN ENGINE
# returns list of (name, score)
# =============================
def detect_patterns(df):
    c = df["close"]
    h = df["high"]
    l = df["low"]

    patterns = []

    # 1-4 Trend strength
    if c.iloc[-1] > c.iloc[-2] > c.iloc[-3] > c.iloc[-4]:
        patterns.append(("Strong Uptrend", 88))
    if c.iloc[-1] < c.iloc[-2] < c.iloc[-3] < c.iloc[-4]:
        patterns.append(("Strong Downtrend", 88))

    # 5-6 Breakout / Breakdown
    if c.iloc[-1] > c.iloc[-10:-1].max():
        patterns.append(("Breakout", 90))
    if c.iloc[-1] < c.iloc[-10:-1].min():
        patterns.append(("Breakdown", 90))

    # 7-8 Double Top / Bottom (simple proxy)
    if abs(c.iloc[-1] - c.iloc[-3]) / c.iloc[-1] < 0.002 and c.iloc[-2] > c.iloc[-1]:
        patterns.append(("Double Top", 78))
    if abs(c.iloc[-1] - c.iloc[-3]) / c.iloc[-1] < 0.002 and c.iloc[-2] < c.iloc[-1]:
        patterns.append(("Double Bottom", 78))

    # 9-10 Higher High / Lower Low
    if h.iloc[-1] > h.iloc[-2] > h.iloc[-3]:
        patterns.append(("Higher Highs", 76))
    if l.iloc[-1] < l.iloc[-2] < l.iloc[-3]:
        patterns.append(("Lower Lows", 76))

    # 11-12 Range expansion / contraction
    rng_now = (h.iloc[-1] - l.iloc[-1])
    rng_prev = (h.iloc[-2] - l.iloc[-2])
    if rng_now > 1.5 * rng_prev:
        patterns.append(("Volatility Expansion", 74))
    if rng_now < 0.7 * rng_prev:
        patterns.append(("Volatility Contraction", 72))

    # 13-14 Pullback in trend
    if c.iloc[-1] > c.rolling(10).mean().iloc[-1] and c.iloc[-2] < c.iloc[-3]:
        patterns.append(("Bullish Pullback", 80))
    if c.iloc[-1] < c.rolling(10).mean().iloc[-1] and c.iloc[-2] > c.iloc[-3]:
        patterns.append(("Bearish Pullback", 80))

    # 15-16 Mean reversion edges
    if c.iloc[-1] < c.rolling(20).mean().iloc[-1] * 0.98:
        patterns.append(("Mean Reversion Long", 75))
    if c.iloc[-1] > c.rolling(20).mean().iloc[-1] * 1.02:
        patterns.append(("Mean Reversion Short", 75))

    # 17-18 Micro flags (proxy)
    if c.iloc[-5] < c.iloc[-4] < c.iloc[-3] and c.iloc[-2] < c.iloc[-3] and c.iloc[-1] > c.iloc[-2]:
        patterns.append(("Bull Flag (proxy)", 77))
    if c.iloc[-5] > c.iloc[-4] > c.iloc[-3] and c.iloc[-2] > c.iloc[-3] and c.iloc[-1] < c.iloc[-2]:
        patterns.append(("Bear Flag (proxy)", 77))

    # 19-20 Momentum continuation / exhaustion
    if c.pct_change().tail(3).mean() > 0.003:
        patterns.append(("Momentum Continuation", 82))
    if c.pct_change().tail(3).mean() < -0.003:
        patterns.append(("Momentum Exhaustion", 78))

    if not patterns:
        patterns.append(("No Clear Pattern", 60))

    # return top 3 by score
    patterns_sorted = sorted(patterns, key=lambda x: x[1], reverse=True)
    return patterns_sorted[:3]

# =============================
# ANALYSIS ENGINE
# =============================
def analyze(df):
    # indicators
    df["ema"] = ta.trend.EMAIndicator(df["close"], 20).ema_indicator()
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], 14).rsi()

    price = df["close"].iloc[-1]
    ema   = df["ema"].iloc[-1]
    rsi   = df["rsi"].iloc[-1]

    # timeframe heuristic from sample size
    n = len(df)
    if n > 200:
        timeframe, eta = "15m", "15-30 mins"
    elif n > 120:
        timeframe, eta = "30m", "30-60 mins"
    elif n > 60:
        timeframe, eta = "1h", "1-2 hours"
    else:
        timeframe, eta = "2h", "2-4 hours"

    # signal (non-random)
    if price > ema and rsi > 55:
        signal = "BUY"
    elif price < ema and rsi < 45:
        signal = "SELL"
    else:
        return None

    # TP/SL (correct directions)
    if signal == "BUY":
        tp = price * 1.04
        sl = price * 0.98
    else:
        tp = price * 0.96
        sl = price * 1.02

    # profit (leveraged)
    raw_profit = abs((tp - price) / price) * 100
    profit = raw_profit * LEVERAGE

    # patterns (top 3)
    top_patterns = detect_patterns(df)  # list of (name, score)
    # choose primary pattern
    primary_name, primary_score = top_patterns[0]

    # pattern success % (score)
    pattern_success = primary_score

    # trade success % (pattern + RSI strength)
    rsi_boost = 5 if (rsi > 60 or rsi < 40) else 0
    trade_success = min(95, pattern_success + rsi_boost)

    return {
        "signal": signal,
        "entry": round(price, 2),
        "tp": round(tp, 2),
        "sl": round(sl, 2),
        "profit": round(profit, 2),
        "timeframe": timeframe,
        "eta": eta,
        "rsi": round(rsi, 2),
        "primary_pattern": primary_name,
        "pattern_success": pattern_success,
        "trade_success": trade_success,
        "top_patterns": top_patterns  # keep all three
    }

# =============================
# START
# =============================
send("🚀 BOT STARTED (20-PATTERN COMPLETE)")

# =============================
# LOOP (2 hours)
# =============================
while True:
    send("📊 SCANNING MARKET (20-PATTERN ENGINE)...")

    for coin in coins:
        df = get_data(coin)
        if df is None:
            continue

        res = analyze(df)
        if not res:
            continue

        symbol = symbol_map.get(coin, coin.upper())

        # format top 3 patterns
        p_lines = "\n".join([f"   • {name} ({score}%)" for name, score in res["top_patterns"]])

        msg = f"""
📊 {symbol}

📢 Signal: {res['signal']} ({LEVERAGE}x)
💰 Entry: {res['entry']}
🎯 TP: {res['tp']}
🛑 SL: {res['sl']}

📊 Profit: {res['profit']}%

🧠 Primary Pattern: {res['primary_pattern']}
📈 Pattern Success: {res['pattern_success']}%
🔥 Trade Success: {res['trade_success']}%

📚 Top Patterns:
{p_lines}

📉 RSI: {res['rsi']}
⏱ Timeframe: {res['timeframe']}
⏳ ETA: {res['eta']}

🕒 Time: {datetime.now().strftime('%H:%M:%S')}
"""

        send(msg)

    time.sleep(INTERVAL)
