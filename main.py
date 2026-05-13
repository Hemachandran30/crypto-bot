# ================= COINDCX + BINANCE VISION - PRODUCTION BOT v4.9 ULTIMATE =================
# STATUS: Full Logic Restored | 15 Detailed Patterns | 2-Hour Batch (Top 3)
# ADDED: Dedicated 1-Hour RIVER Coin Signal | 1x Trend Reversal Alert
# FIX: Persistent Queue remembers trades for the full 2-hour window.

import requests
import time
import json
import os
import threading
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ================= CONFIGURATION =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8265055522:AAGl2v211gtKwqYTmjue_gXW9Vx0dvf8Wes")
CHAT_ID = os.getenv("CHAT_ID", "931982378")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

BINANCE_PRICE_URL = "https://data-api.binance.vision/api/v3/ticker/price"
BINANCE_KLINE_URL = "https://data-api.binance.vision/api/v3/klines"

# FULL 150+ COINS
COINS = [
    "BTC","ETH","BNB","SOL","XRP","DOGE","ADA","TRX","AVAX","SHIB",
    "DOT","LINK","BCH","NEAR","LTC","UNI","APT","ETC","HBAR","FIL",
    "ARB","VET","INJ","OP","ATOM","TIA","SUI","SEI","ALGO","EGLD",
    "FLOW","EOS","XTZ","AAVE","MKR","GRT","SNX","COMP","CRV","SUSHI",
    "LDO","CAKE","1INCH","DYDX","GMX","ENS","PENDLE","RNDR","FET","WLD",
    "AR","THETA","LPT","AKT","SAND","MANA","RIVER","AXS","GALA","CHZ","APE",
    "GMT","ENJ","PEPE","WIF","FLOKI","BONK","ORDI","BOME","NOT","DOGS",
    "CELO","BLUR","MASK","LUNC","ZRX","BAT","RUNE","STX","KAS","CRO",
    "IMX","MINA","CFX","STORJ","BAND","COTI","CHR","CTSI","LRC","API3",
    "BAL","BNT","FLUX","GLM","JASMY","KNC","NKN","OGN","PAXG","PHA",
    "REQ","RLC","TLM","TRB","UMA","XVS","YFI","YGG","ENA","ETHFI",
    "STRK","PIXEL","DYM","ALT","JTO","ZK","ZRO","LISTA","IO","ATH",
    "TAO","TNSR","DRIFT","MEW","1000SATS","1000SHIB","1000PEPE","1000FLOKI",
    "1000LUNC","1000BONK","1000RATS","1000CAT","1MBABYDOGE","ACE","ACH",
    "ACT","AERO","AEVO","AGLD","AIXBT","ALICE","ALPINE","ANKR","ARKM",
    "ASTR","ATOM","AUCTION","AUDIO","AXL","BEL","BERA","BICO","BIGTIME",
    "BIO","BLUR","BMT","BSV","C98","CARV","CATI","CETUS","CGPT","CKB",
    "COMP","COOKIE","COS","COW","CYBER","DASH","DEXE","DIA","DOLO","DYM"
]

PRIMARY_PATTERNS = [
    "EMA Trend", "Breakout", "Pullback to 20 EMA", "RSI Reversal", "Momentum Surge",
    "Volume Spike", "Double Bottom", "Double Top", "Support Bounce", "Resistance Rejection",
    "Bullish Engulfing", "Bearish Engulfing", "Volume Breakout", "Bull Flag Break", "Bear Flag Break"
]
ALL_PATTERNS = PRIMARY_PATTERNS + ["Head and Shoulders", "Inverse H&S", "Bear Flag"]

# ================= STATE =================
active_trades = {}
pending_signals = {}
hourly_queue = {} # This remembers high-quality trades for the 2-hour batch
pattern_stats = {p: {"signals":0,"wins":0,"losses":0,"total_pnl":0} for p in ALL_PATTERNS}
last_update_id = None
last_batch_time = time.time()
last_river_time = time.time()
last_hourly_time = time.time()

IST = ZoneInfo("Asia/Kolkata")
SCAN_INTERVAL = 300 
BATCH_INTERVAL = 7200 # 2-Hour Batch (Top 3 Signals)
RIVER_INTERVAL = 3600 # 1-Hour RIVER Dedicated Signal
TRADE_UPDATE_INTERVAL = 1800 
MAX_SIGNALS_PER_BATCH = 3
MIN_SETUP_SCORE = 85
MIN_PROFIT_TARGET = 20.0
# ================= DATA & UTILS =================
def format_price(price):
    if price >= 1000: return f"{price:.2f}"
    elif price >= 1: return f"{price:.4f}"
    elif price >= 0.01: return f"{price:.6f}"
    else: return f"{price:.8f}"

def get_ist_time(): return datetime.now(IST).strftime("%I:%M:%S %p IST")
def get_ist_datetime(): return datetime.now(IST)

def get_price(symbol):
    try:
        res = requests.get(BINANCE_PRICE_URL, params={"symbol": symbol}, timeout=8)
        return float(res.json()["price"]) if res.status_code == 200 else None
    except: return None

def get_klines(symbol, interval, limit=100):
    try:
        res = requests.get(BINANCE_KLINE_URL, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=8)
        return res.json() if res.status_code == 200 else []
    except: return []

def calculate_ema(closes, period):
    if len(closes) < period: return None
    ema = sum(closes[:period]) / period
    k = 2 / (period + 1)
    for price in closes[period:]: ema = price * k + ema * (1 - k)
    return ema

def calculate_rsi(closes, period=14):
    if len(closes) < period + 1: return 50
    g, l = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        g.append(max(0, diff)); l.append(max(0, -diff))
    ag, al = sum(g[-period:])/period, sum(l[-period:])/period
    return 100 - (100 / (1 + (ag/al))) if al != 0 else 100

def get_news_headlines(coin):
    if not NEWS_API_KEY: return []
    try:
        res = requests.get("https://cryptopanic.com/api/v1/posts/", params={"auth_token": NEWS_API_KEY, "currencies": coin, "kind": "news"}, timeout=5)
        return [p["title"] for p in res.json().get("results", [])[:3]]
    except: return []
  # ================= THE 15 PATTERNS =================
def detect_patterns(symbol, klines, price):
    if len(klines) < 50: return []
    closes = [float(k[4]) for k in klines]
    opens, highs, lows = [float(k[1]) for k in klines], [float(k[2]) for k in klines], [float(k[3]) for k in klines]
    vols = [float(k[5]) for k in klines]
    ema20, ema50 = calculate_ema(closes, 20), calculate_ema(closes, 50)
    rsi, avg_v = calculate_rsi(closes), sum(vols[-20:])/20
    p = []

    # Patterns Detection
    if ema20 and ema50:
        if price > ema20 > ema50: p.append(("EMA Trend", 85, "BUY"))
        elif price < ema20 < ema50: p.append(("EMA Trend", 85, "SELL"))
    if price > max(highs[-20:-1]): p.append(("Breakout", 88, "BUY"))
    elif price < min(lows[-20:-1]): p.append(("Breakout", 88, "SELL"))
    if ema20 and abs(price - ema20)/ema20 < 0.005: p.append(("Pullback to 20 EMA", 82, "BUY" if price > ema20 else "SELL"))
    if rsi < 30: p.append(("RSI Reversal", 80, "BUY"))
    elif rsi > 70: p.append(("RSI Reversal", 80, "SELL"))
    mom = (closes[-1] - closes[-3])/closes[-3]*100 if len(closes) > 3 else 0
    if mom > 3: p.append(("Momentum Surge", 87, "BUY"))
    elif mom < -3: p.append(("Momentum Surge", 87, "SELL"))
    if vols[-1] > avg_v * 3.5: p.append(("Volume Spike", 84, "BUY" if closes[-1] > opens[-1] else "SELL"))
    sup, res = min(lows[-30:-1]), max(highs[-30:-1])
    if price <= sup * 1.005 and closes[-1] > opens[-1]: p.append(("Support Bounce", 88, "BUY"))
    if price >= res * 0.995 and closes[-1] < opens[-1]: p.append(("Resistance Rejection", 88, "SELL"))
    if len(lows) > 40:
        if abs(min(lows[-40:-20]) - min(lows[-10:]))/price < 0.005: p.append(("Double Bottom", 90, "BUY"))
        if abs(max(highs[-40:-20]) - max(highs[-10:]))/price < 0.005: p.append(("Double Top", 90, "SELL"))
    if opens[-2] > closes[-2] and closes[-1] > opens[-1] and closes[-1] > opens[-2]: p.append(("Bullish Engulfing", 89, "BUY"))
    if opens[-2] < closes[-2] and closes[-1] < opens[-1] and closes[-1] < opens[-2]: p.append(("Bearish Engulfing", 89, "SELL"))
    if price > res and vols[-1] > avg_v * 2.5: p.append(("Volume Breakout", 91, "BUY"))
    if ema20 and price > ema20 and price > max(highs[-5:-1]): p.append(("Bull Flag Break", 92, "BUY"))
    if ema20 and price < ema20 and price < min(lows[-5:-1]): p.append(("Bear Flag Break", 92, "SELL"))
    return p

def get_liquidity_zone(symbol, entry, direction):
    klines = get_klines(symbol, "1h", 20)
    if not klines: return None
    h, l = [float(k[2]) for k in klines], [float(k[3]) for k in klines]
    return min(l[-10:]) * 0.998 if direction == "BUY" else max(h[-10:]) * 1.002
# ================= VERIFICATION & SENDING =================
def format_and_send(setup, coin, is_river=False):
    global pending_signals
    p, k = get_price(setup["symbol"]), get_klines(setup["symbol"], "15m")
    if not p or not k: return False
    
    # RE-VALIDATION: Final pattern check
    current_found = detect_patterns(setup["symbol"], k, p)
    if not any(pat[0] == setup["pattern"] and pat[2] == setup["direction"] for pat in current_found):
        return False # Pattern disappeared, skip

    # Real Math for SL/TP
    atr = (max([float(x[2]) for x in k[-10:]]) - min([float(x[3]) for x in k[-10:]])) / 2
    sl = p - (atr * 1.5) if setup["direction"] == "BUY" else p + (atr * 1.5)
    tp = p + (atr * 3.0) if setup["direction"] == "BUY" else p - (atr * 3.0)
    
    closes = [float(x[4]) for x in k]
    mom = (closes[-1] - closes[-3])/closes[-3]*100; velocity = abs(mom/45)
    eta = int(abs(tp-p)/((max(closes[-10:])-min(closes[-10:]))/10)*15)
    liq = get_liquidity_zone(setup["symbol"], p, setup["direction"])
    news = get_news_headlines(coin)

    header = "🌊 <b>DEDICATED RIVER SIGNAL (1-HR)</b>" if is_river else f"🔥 <b>VERIFIED SETUP {coin}</b>"
    msg = f"{header} | Score: {int(setup['setup_score'])}/100\n\n"
    msg += f"📢 Direction: {setup['direction']} | Leverage: 5x\n"
    msg += f"💰 Entry: {format_price(p)}\n🎯 TP: {format_price(tp)}\n🛑 SL: {format_price(sl)}\n\n"
    msg += f"📈 Profit Target: {(abs(tp-p)/p*500):.2f}%\n🧠 Confidence: {int(setup['setup_score']-5)}%\n"
    msg += f"📌 Pattern: {setup['pattern']} | RSI: {calculate_rsi(closes):.2f}\n"
    msg += f"⚡ Momentum: {mom:.2f}% | 🚀 Velocity: {velocity:.4f}/min\n"
    msg += f"⏳ ETA: ~{eta} mins | ⚠️ Risk: {(abs(p-sl)/p*100):.2f}%\n"
    msg += f"💧 Liq Zone: {format_price(liq) if liq else 'N/A'} | ✏️ ATR: {format_price(atr)}\n\n"
    if news: msg += "<b>📰 News:</b>\n" + "\n".join([f"• {n[:60]}..." for n in news]) + "\n\n"
    msg += f"⏰ Verified At: {get_ist_time()}"

    setup.update({"entry":p,"sl":sl,"tp":tp,"leverage":5,"timestamp":get_ist_datetime(),"reversal_alerted":False})
    pending_signals[coin] = setup
    return send_telegram(msg, coin=coin, add_buttons=True)

def send_hourly_batch():
    global hourly_queue, last_batch_time
    if not hourly_queue: return
    sorted_q = sorted(hourly_queue.values(), key=lambda x: x["setup_score"], reverse=True)
    sent = 0
    for s in sorted_q:
        if s["coin"] == "RIVER": continue
        if sent >= MAX_SIGNALS_PER_BATCH: break
        if format_and_send(s, s["coin"]): sent += 1
    hourly_queue.clear()
    last_batch_time = time.time()

def send_river_signal():
    global last_river_time
    p, k = get_price("RIVERUSDT"), get_klines("RIVERUSDT", "15m")
    if p and k:
        found = detect_patterns("RIVERUSDT", k, p)
        if found:
            best = max(found, key=lambda x: x[1])
            setup = {"symbol":"RIVERUSDT","coin":"RIVER","direction":best[2],"pattern":best[0],"setup_score":best[1]}
            format_and_send(setup, "RIVER", is_river=True)
    last_river_time = time.time()
  # ================= TRACKING & LOOP =================
def check_active_trades():
    global active_trades
    for c, t in list(active_trades.items()):
        p = get_price(t["symbol"])
        if not p: continue
        
        # 1x Trend Reversal Alert Logic
        if not t.get("reversal_alerted", False):
            cl = [float(x[4]) for x in get_klines(t["symbol"], "15m", 20)]
            ema20 = sum(cl)/20 if cl else p
            if (t["direction"] == "BUY" and p < ema20 * 0.995) or (t["direction"] == "SELL" and p > ema20 * 1.005):
                send_telegram(f"⚠️ <b>TREND REVERSAL {c}</b>\nPrice broke EMA20. Trend may be failing."); active_trades[c]["reversal_alerted"] = True

        # TP/SL Tracking
        hit = None
        if t["direction"] == "BUY":
            if p >= t["tp"]: hit = "✅ TAKE PROFIT"
            elif p <= t["sl"]: hit = "🛑 STOP LOSS"
        else:
            if p <= t["tp"]: hit = "✅ TAKE PROFIT"
            elif p >= t["sl"]: hit = "🛑 STOP LOSS"
        if hit:
            send_telegram(f"{hit} on {c}!\nExit: {format_price(p)}"); del active_trades[c]

def poll_telegram():
    global last_update_id
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            res = requests.get(url, params={"offset":last_update_id+1 if last_update_id else None}, timeout=15).json()
            for u in res.get("result", []):
                last_update_id = u["update_id"]
                if "callback_query" in u:
                    data = u["callback_query"]["data"]; c = data.split("_")[1]
                    if "ACTIVATE" in data and c in pending_signals:
                        active_trades[c] = pending_signals[c]; send_telegram(f"🚀 {c} Activated!"); del pending_signals[c]
        except: pass
        time.sleep(2)

def main():
    global last_batch_time, last_river_time, last_hourly_time
    threading.Thread(target=poll_telegram, daemon=True).start()
    send_telegram("🚀 <b>Ultimate Bot v4.9 Started</b>\n1-Hr River Signal & Intel Queue Active.")
    while True:
        try:
            # Intel Gathering Scan
            for coin in COINS:
                symbol = coin + "USDT"; p, k = get_price(symbol), get_klines(symbol, "15m")
                if not p or len(k) < 50: continue
                found = detect_patterns(symbol, k, p)
                if found:
                    best = max(found, key=lambda x: x[1])
                    if best[1] >= MIN_SETUP_SCORE:
                        hourly_queue[coin] = {"coin":coin,"symbol":symbol,"direction":best[2],"pattern":best[0],"setup_score":best[1]}
                time.sleep(0.15)
            
            check_active_trades()
            now = time.time()
            if (now - last_hourly_time) >= 3600:
                send_telegram(f"📊 <b>Hourly Checkpoint</b>\nQueue Size: {len(hourly_queue)} potential trades."); last_hourly_time = now
            if (now - last_batch_time) >= BATCH_INTERVAL: send_hourly_batch()
            if (now - last_river_time) >= RIVER_INTERVAL: send_river_signal()
            time.sleep(300)
        except Exception as e: print(f"Error: {e}"); time.sleep(60)

if __name__ == "__main__": main()
