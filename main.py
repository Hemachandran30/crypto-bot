# ================= COINDCX + BINANCE VISION - PRODUCTION BOT v4.6 ULTIMATE =================
# FIXED: Trend Reversal Spam (Alerts only ONCE per trade)
# ADDED: Dedicated 1-Hour RIVER Coin Signal Generator
# PRESERVED: 500+ Lines Original Logic | 15 Patterns | 3 Signals/2hr | Real Math

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
COINDX_FUTURES_URL = "https://public.coindcx.com/market_data/candles"

# ================= THE FULL 150+ COINDCX LIST =================
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

ALL_PATTERNS = [
    "EMA Trend", "Breakout", "Pullback to 20 EMA", "RSI Reversal", "Momentum Surge",
    "Volume Spike", "Double Bottom", "Double Top", "Support Bounce", "Resistance Rejection",
    "Bullish Engulfing", "Bearish Engulfing", "Volume Breakout", "Bull Flag Break", "Bear Flag Break",
    "Head and Shoulders", "Inverse H&S", "Bear Flag", "Trend Continuation", "Range Break + Retest",
    "Ascending Triangle", "Descending Triangle", "Rising Wedge", "Falling Wedge",
    "Cup and Handle", "Fake Breakout", "Liquidity Sweep", "Order Block", "Scalping Setup"
]

# ================= STATE MANAGEMENT =================
active_trades = {}
pending_signals = {}
hourly_queue = {}
last_trade_update = {}
pattern_stats = {p: {"signals":0,"wins":0,"losses":0,"total_pnl":0} for p in ALL_PATTERNS}
last_update_id = None

# TIMERS
last_batch_time = 0
last_hourly_time = time.time()
last_river_time = 0

IST = ZoneInfo("Asia/Kolkata")
SCAN_INTERVAL = 300 
BATCH_INTERVAL = 7200 # 2 Hours for top 3 signals
RIVER_INTERVAL = 3600 # 1 Hour for River signal
TRADE_UPDATE_INTERVAL = 1800 # 30 mins
MAX_SIGNALS_PER_HOUR = 3
MIN_SETUP_SCORE = 85
MAX_PRICE_DRIFT = 0.02
MIN_PROFIT_TARGET = 20.0
REQUEST_TIMEOUT = 8
TELEGRAM_TIMEOUT = 30
DELAY_BETWEEN_COINS = 0.15
# ================= UTILITIES & LOGGING =================
def format_price(price):
    if price >= 1000: return f"{price:.2f}"
    elif price >= 1: return f"{price:.4f}"
    elif price >= 0.01: return f"{price:.6f}"
    else: return f"{price:.8f}"

def get_ist_time(): return datetime.now(IST).strftime("%I:%M:%S %p IST")
def get_ist_datetime(): return datetime.now(IST)

def send_telegram(msg, coin=None, add_buttons=False):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
        if add_buttons and coin:
            payload["reply_markup"] = {"inline_keyboard": [[
                {"text": "✅ Activate Trade", "callback_data": f"ACTIVATE_{coin}"},
                {"text": "❌ Ignore", "callback_data": f"IGNORE_{coin}"}
            ]]}
        requests.post(url, json=payload, timeout=TELEGRAM_TIMEOUT)
        return True
    except: return False

def answer_callback(callback_query_id, text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
        requests.post(url, json={"callback_query_id": callback_query_id, "text": text}, timeout=TELEGRAM_TIMEOUT)
    except: pass

def save_trade_history():
    try:
        with open("trades.json", "w") as f: json.dump(pattern_stats, f)
    except: pass

def load_trade_history():
    global pattern_stats
    try:
        if os.path.exists("trades.json"):
            with open("trades.json", "r") as f:
                loaded = json.load(f)
                for p in ALL_PATTERNS:
                    if p in loaded: pattern_stats[p] = loaded[p]
    except: print("Starting fresh history")

def log_trade(coin, result, trade_data, pnl, exit_price):
    try:
        log_entry = {
            "timestamp": get_ist_time(), "coin": coin, "direction": trade_data["direction"],
            "pattern": trade_data["pattern"], "result": result, "entry": trade_data["entry"],
            "exit": exit_price, "sl": trade_data["sl"], "tp": trade_data["tp"],
            "leverage": trade_data["leverage"], "pnl_percent": round(pnl, 2),
            "risk_pct": trade_data["risk_pct"], "confidence": trade_data["confidence"],
            "setup_score": trade_data["setup_score"]
        }
        logs = []
        if os.path.exists("trades_log.json"):
            with open("trades_log.json", "r") as f: logs = json.load(f)
        logs.append(log_entry)
        with open("trades_log.json", "w") as f: json.dump(logs, f, indent=2)
    except: pass

# ================= DATA FETCHING =================
def get_price(symbol):
    try:
        res = requests.get(BINANCE_PRICE_URL, params={"symbol": symbol}, timeout=REQUEST_TIMEOUT)
        return float(res.json()["price"]) if res.status_code == 200 else None
    except: return None

def get_klines(symbol, interval, limit=100):
    try:
        res = requests.get(BINANCE_KLINE_URL, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=REQUEST_TIMEOUT)
        return res.json() if res.status_code == 200 else []
    except: return []

def get_news_headlines(coin, limit=3):
    if not NEWS_API_KEY: return []
    try:
        res = requests.get("https://cryptopanic.com/api/v1/posts/", params={"auth_token": NEWS_API_KEY, "currencies": coin, "kind": "news", "filter": "important"}, timeout=5)
        return [p["title"] for p in res.json().get("results", [])[:limit]] if res.status_code == 200 else []
    except: return []

def calculate_ema(closes, period):
    if len(closes) < period: return None
    ema = sum(closes[:period]) / period
    k = 2 / (period + 1)
    for price in closes[period:]: ema = price * k + ema * (1 - k)
    return ema

def calculate_rsi(closes, period=14):
    if len(closes) < period + 1: return 50
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(0, diff)); losses.append(max(0, -diff))
    avg_gain, avg_loss = sum(gains[-period:]) / period, sum(losses[-period:]) / period
    return 100 - (100 / (1 + (avg_gain/avg_loss))) if avg_loss != 0 else 100

def calculate_atr(klines, period=14):
    if len(klines) < period + 1: return 0
    trs = []
    for i in range(1, len(klines)):
        h, l, pc = float(klines[i][2]), float(klines[i][3]), float(klines[i-1][4])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs[-period:]) / period if len(trs) >= period else 0

def check_trend_reversal(symbol, direction, entry):
    klines = get_klines(symbol, "15m", 50)
    if len(klines) < 20: return False
    closes = [float(k[4]) for k in klines]
    ema20 = calculate_ema(closes, 20)
    if not ema20: return False
    if direction == "BUY" and closes[-1] < ema20 * 0.995: return True
    elif direction == "SELL" and closes[-1] > ema20 * 1.005: return True
    return False

def get_liquidity_zone(symbol, entry, direction):
    klines = get_klines(symbol, "1h", 20)
    if not klines: return None
    highs, lows = [float(k[2]) for k in klines], [float(k[3]) for k in klines]
    if direction == "BUY": return min(lows[-10:]) * 0.998
    return max(highs[-10:]) * 1.002

def get_dynamic_leverage(symbol, atr_pct, confidence):
    base = symbol.replace("USDT", "")
    if base in ["BTC", "ETH"]: return 10
    if base in ["BNB", "SOL"]: return 8
    if atr_pct < 2.0 and confidence > 80: return 8
    if atr_pct < 4.0: return 5
    return 4
     # ================= 15 DETAILED PATTERNS =================
def detect_patterns(symbol, klines, price):
    if len(klines) < 50: return []
    closes = [float(k[4]) for k in klines]
    opens, highs, lows = [float(k[1]) for k in klines], [float(k[2]) for k in klines], [float(k[3]) for k in klines]
    volumes = [float(k[5]) for k in klines]

    ema20, ema50 = calculate_ema(closes, 20), calculate_ema(closes, 50)
    rsi = calculate_rsi(closes)
    avg_vol = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else volumes[-1]
    p = []

    # 1. EMA Trend
    if ema20 and ema50:
        if price > ema20 > ema50 and closes[-1] > closes[-5]: p.append(("EMA Trend", 85, "BUY"))
        elif price < ema20 < ema50 and closes[-1] < closes[-5]: p.append(("EMA Trend", 85, "SELL"))
    # 2. Breakout
    if price > max(highs[-20:-1]) * 1.002 and volumes[-1] > avg_vol * 1.5: p.append(("Breakout", 88, "BUY"))
    if price < min(lows[-20:-1]) * 0.998 and volumes[-1] > avg_vol * 1.5: p.append(("Breakout", 88, "SELL"))
    # 3. Pullback to 20 EMA
    if ema20 and abs(price - ema20) / ema20 < 0.01:
        if closes[-1] > closes[-2] and rsi < 60: p.append(("Pullback to 20 EMA", 82, "BUY"))
        elif closes[-1] < closes[-2] and rsi > 40: p.append(("Pullback to 20 EMA", 82, "SELL"))
    # 4. RSI Reversal
    if rsi < 30 and closes[-1] > closes[-2]: p.append(("RSI Reversal", 80, "BUY"))
    elif rsi > 70 and closes[-1] < closes[-2]: p.append(("RSI Reversal", 80, "SELL"))
    # 5. Momentum Surge
    if len(closes) >= 3:
        mom = (closes[-1] - closes[-3]) / closes[-3] * 100
        if mom > 3 and volumes[-1] > avg_vol * 2: p.append(("Momentum Surge", 87, "BUY"))
        elif mom < -3 and volumes[-1] > avg_vol * 2: p.append(("Momentum Surge", 87, "SELL"))
    # 6. Volume Spike
    if volumes[-1] > avg_vol * 3.5: p.append(("Volume Spike", 84, "BUY" if closes[-1] > opens[-1] else "SELL"))
    # 7 & 8. Support / Resistance
    sup, res = min(lows[-30:-1]), max(highs[-30:-1])
    if price <= sup * 1.005 and closes[-1] > opens[-1]: p.append(("Support Bounce", 88, "BUY"))
    if price >= res * 0.995 and closes[-1] < opens[-1]: p.append(("Resistance Rejection", 88, "SELL"))
    # 9 & 10. Double Top/Bottom
    if len(lows) > 40:
        if abs(min(lows[-40:-20]) - min(lows[-10:-1])) / price < 0.005 and price > min(lows[-10:-1]): p.append(("Double Bottom", 90, "BUY"))
        if abs(max(highs[-40:-20]) - max(highs[-10:-1])) / price < 0.005 and price < max(highs[-10:-1]): p.append(("Double Top", 90, "SELL"))
    # 11 & 12. Engulfing
    if opens[-2] > closes[-2] and closes[-1] > opens[-1] and closes[-1] > opens[-2]: p.append(("Bullish Engulfing", 89, "BUY"))
    if opens[-2] < closes[-2] and closes[-1] < opens[-1] and closes[-1] < opens[-2]: p.append(("Bearish Engulfing", 89, "SELL"))
    # 13. Volume Breakout
    if price > res and volumes[-1] > avg_vol * 2.5: p.append(("Volume Breakout", 91, "BUY"))
    # 14 & 15. Flags
    if ema20 and price > ema20 and price > max(highs[-5:-1]): p.append(("Bull Flag Break", 92, "BUY"))
    if ema20 and price < ema20 and price < min(lows[-5:-1]): p.append(("Bear Flag Break", 92, "SELL"))

    return p

def get_smart_sl_tp(symbol, entry, direction, klines, leverage):
    if len(klines) < 20: return None, None, 0, 0
    atr = calculate_atr(klines)
    if direction == "BUY":
        sl = entry - (atr * 1.5)
        tp = entry + (atr * 3.0)
    else:
        sl = entry + (atr * 1.5)
        tp = entry - (atr * 3.0)
    risk_pct = (abs(entry - sl) / entry) * 100
    return sl, tp, atr, risk_pct

def scan_market():
    global hourly_queue
    hourly_queue.clear() 

    for coin in COINS:
        symbol = coin + "USDT"
        try:
            price, klines = get_price(symbol), get_klines(symbol, "15m", 100)
            if not price or len(klines) < 50: continue

            patterns = detect_patterns(symbol, klines, price)
            if not patterns: continue

            best = max(patterns, key=lambda x: x[1])
            pattern, confidence, direction = best

            if confidence < MIN_SETUP_SCORE: continue

            atr = calculate_atr(klines)
            atr_pct = (atr / price) * 100 if price > 0 else 0
            leverage = get_dynamic_leverage(symbol, atr_pct, confidence)

            sl, tp, atr_val, risk_pct = get_smart_sl_tp(symbol, price, direction, klines, leverage)
            if not sl: continue

            # Force minimum profit logic via leverage if needed
            profit_target = ((abs(tp - price)) / price * 100 * leverage)
            if profit_target < MIN_PROFIT_TARGET:
                risk_per_unit = abs(tp - price) / price
                if risk_per_unit > 0:
                    needed_leverage = int(MIN_PROFIT_TARGET / (risk_per_unit * 100)) + 1
                    if needed_leverage <= 10:
                        leverage = needed_leverage
                        profit_target = risk_per_unit * 100 * leverage
                        sl, tp, atr_val, risk_pct = get_smart_sl_tp(symbol, price, direction, klines, leverage)
                    else: continue

            pattern_success = (pattern_stats[pattern]["wins"] / pattern_stats[pattern]["signals"] * 100) if pattern_stats[pattern]["signals"] > 0 else 0
            setup_score = min(100, confidence + (pattern_success / 10))

            setup = {
                "coin": coin, "symbol": symbol, "direction": direction, "pattern": pattern,
                "confidence": confidence, "setup_score": setup_score, "entry": price,
                "sl": sl, "tp": tp, "atr": atr_val, "risk_pct": risk_pct, "leverage": leverage,
                "pattern_success": pattern_success, "profit_target": profit_target,
                "timestamp": get_ist_datetime(), "reversal_alerted": False
            }

            if coin not in hourly_queue or confidence > hourly_queue[coin]["confidence"]:
                hourly_queue[coin] = setup 

        except Exception as e: print(f"Scan error {coin}: {e}")
        time.sleep(DELAY_BETWEEN_COINS)
     # ================= SIGNAL GENERATION & REAL MATH =================
def format_and_send_signal(setup, coin, is_river=False):
    global pending_signals
    symbol = setup["symbol"]
    fresh_price = get_price(symbol)
    klines = get_klines(symbol, "15m", 100)
    if not fresh_price or not klines: return False

    setup["entry"] = fresh_price
    sl, tp, atr, risk_pct = get_smart_sl_tp(symbol, fresh_price, setup["direction"], klines, setup["leverage"])
    if not sl: return False
    setup["sl"] = sl; setup["tp"] = tp; setup["atr"] = atr; setup["risk_pct"] = risk_pct
    setup["profit_target"] = (abs(tp - fresh_price) / fresh_price * 100 * setup["leverage"])

    closes = [float(k[4]) for k in klines]
    rsi = calculate_rsi(closes)
    vol_strength = (float(klines[-1][5]) / (sum([float(k[5]) for k in klines[-20:]])/20) * 100)
    mom = ((closes[-1] - closes[-3]) / closes[-3] * 100) if len(closes) > 3 else 0
    velocity = abs(mom) / 45
    liq = get_liquidity_zone(symbol, fresh_price, setup["direction"])
    
    avg_body = sum(abs(float(k[4]) - float(k[1])) for k in klines[-10:]) / 10
    eta_mins = int((abs(tp - fresh_price) / (avg_body if avg_body > 0 else 0.001)) * 15)

    news = get_news_headlines(coin)
    header = "🌊 <b>DEDICATED RIVER SIGNAL</b>" if is_river else f"🔥 <b>SETUP {coin}</b>"

    msg = f"{header} | Score: {int(setup['setup_score'])}/100\n\n"
    msg += f"📢 <b>Direction:</b> {setup['direction']}\n📊 <b>Leverage:</b> {setup['leverage']}x\n\n"
    msg += f"💰 <b>Entry:</b> {format_price(setup['entry'])}\n🎯 <b>TP:</b> {format_price(setup['tp'])}\n🛑 <b>SL:</b> {format_price(setup['sl'])}\n\n"
    msg += f"📈 <b>Profit Target:</b> {setup['profit_target']:.2f}%\n"
    msg += f"🧠 <b>Confidence:</b> {setup['confidence']}%\n📊 <b>Setup Score:</b> {int(setup['setup_score'])}%\n\n"
    msg += f"📌 <b>Pattern:</b> {setup['pattern']}\n📌 <b>Success Rate:</b> {setup['pattern_success']:.1f}%\n\n"
    msg += f"📉 <b>RSI:</b> {rsi:.2f}\n📦 <b>Volume Strength:</b> {vol_strength:.2f}%\n\n"
    msg += f"⚡ <b>Momentum:</b> {mom:.2f}%\n🚀 <b>Velocity Score:</b> {velocity:.4f}/min\n\n"
    msg += f"📍 <b>Timeframe:</b> 15m\n⏳ <b>ETA:</b> ~{eta_mins} mins\n⚠️ <b>Risk:</b> {setup['risk_pct']:.2f}%\n"
    msg += f"⏰ <b>Expires:</b> {(get_ist_datetime() + timedelta(hours=1)).strftime('%I:%M %p IST')}\n\n"
    msg += f"💧 <b>Liquidity Zone:</b> {format_price(liq) if liq else 'N/A'}\n✏️ <b>ATR:</b> {format_price(setup['atr'])}\n\n"
    msg += f"⏰ <b>Trade Time:</b> {get_ist_time()}\n"

    if news:
        msg += "\n<b>📰 News:</b>\n" + "\n".join([f"• {h[:60]}..." for h in news]) + "\n"

    pending_signals[coin] = setup 
    send_telegram(msg, coin=coin, add_buttons=True)
    return True

def send_hourly_batch():
    global hourly_queue, last_batch_time
    if not hourly_queue: return
    sorted_setups = sorted(hourly_queue.values(), key=lambda x: x["setup_score"], reverse=True)
    sent = 0
    for setup in sorted_setups:
        if setup["coin"] == "RIVER": continue # Handled by the dedicated River timer
        if sent >= MAX_SIGNALS_PER_HOUR: break
        if format_and_send_signal(setup, setup["coin"]):
            sent += 1
            time.sleep(1)
    hourly_queue.clear() 
    last_batch_time = time.time()

def send_river_signal():
    global last_river_time
    symbol, coin = "RIVERUSDT", "RIVER"
    price, klines = get_price(symbol), get_klines(symbol, "15m", 100)
    if price and len(klines) >= 50:
        found = detect_patterns(symbol, klines, price)
        if found:
            best = max(found, key=lambda x: x[1])
            succ = (pattern_stats[best[0]]["wins"]/pattern_stats[best[0]]["signals"]*100) if pattern_stats[best[0]]["signals"]>0 else 0
            score = min(100, best[1] + (succ/10))
            if score >= MIN_SETUP_SCORE:
                setup = {
                    "coin": coin, "symbol": symbol, "direction": best[2], "pattern": best[0],
                    "confidence": best[1], "setup_score": score, "pattern_success": succ,
                    "leverage": 5, "reversal_alerted": False
                }
                format_and_send_signal(setup, coin, is_river=True)
    last_river_time = time.time()
# ================= TRADE TRACKING & COMMANDS =================
def get_active_trades_text():
    if not active_trades: return "No active trades"
    text = f"📊 <b>Active Trades ({len(active_trades)})</b>\n\n"
    for coin, trade in active_trades.items():
        text += f"<b>{coin}</b> {trade['direction']}\nEntry: {format_price(trade['entry'])} | SL: {format_price(trade['sl'])}\nTP: {format_price(trade['tp'])} | Lev: {trade['leverage']}x\n\n"
    return text

def get_pattern_stats_text():
    text = "📈 <b>Pattern Performance</b>\n\n"
    for pattern, stats in sorted(pattern_stats.items(), key=lambda x: x[1]["signals"], reverse=True)[:10]:
        if stats["signals"] > 0:
            text += f"<b>{pattern}</b>\nSignals: {stats['signals']} | Win: {(stats['wins']/stats['signals']*100):.1f}% | PnL: {stats['total_pnl']:.1f}%\n\n"
    return text

def check_active_trades():
    global active_trades, last_trade_update
    current_time = time.time()

    for coin in list(active_trades.keys()):
        trade = active_trades.get(coin) 
        if not isinstance(trade, dict): continue

        symbol = trade["symbol"]
        price = get_price(symbol)
        if not price: continue

        # Check Trend Reversal ONCE per trade
        if not trade.get("reversal_alerted", False):
            if check_trend_reversal(symbol, trade["direction"], trade["entry"]):
                send_telegram(f"⚠️ <b>TREND REVERSAL {coin}</b>\n\nYour {trade['direction']} trade is at risk!\nPrice broke EMA20 against direction.\n\nCurrent: {format_price(price)}\nEntry: {format_price(trade['entry'])}\n\nConsider closing manually.")
                active_trades[coin]["reversal_alerted"] = True

        hit, pnl = None, 0
        if trade["direction"] == "BUY":
            if price >= trade["tp"]: hit, pnl = "TP_HIT", ((trade["tp"] - trade["entry"]) / trade["entry"]) * 100 * trade["leverage"]
            elif price <= trade["sl"]: hit, pnl = "SL_HIT", ((trade["sl"] - trade["entry"]) / trade["entry"]) * 100 * trade["leverage"]
        else:
            if price <= trade["tp"]: hit, pnl = "TP_HIT", ((trade["entry"] - trade["tp"]) / trade["entry"]) * 100 * trade["leverage"]
            elif price >= trade["sl"]: hit, pnl = "SL_HIT", ((trade["entry"] - trade["sl"]) / trade["entry"]) * 100 * trade["leverage"]

        if hit:
            pattern_stats[trade["pattern"]]["signals"] += 1
            if hit == "TP_HIT": pattern_stats[trade["pattern"]]["wins"] += 1
            else: pattern_stats[trade["pattern"]]["losses"] += 1
            pattern_stats[trade["pattern"]]["total_pnl"] += pnl
            log_trade(coin, hit, trade, pnl, price)
            save_trade_history()
            
            icon = "✅" if hit == "TP_HIT" else "🛑"
            exit_p = trade['tp'] if hit == "TP_HIT" else trade['sl']
            send_telegram(f"{icon} <b>{hit.replace('_', ' ')} {coin}</b>\n\nPnL: {pnl:+.2f}%\nPattern: {trade['pattern']}\nEntry: {format_price(trade['entry'])}\nExit: {format_price(exit_p)}\nTime: {get_ist_time()}")
            del active_trades[coin] 
            if coin in last_trade_update: del last_trade_update[coin] 
            continue

        if coin not in last_trade_update or (current_time - last_trade_update[coin]) >= TRADE_UPDATE_INTERVAL: 
            cur_pnl = ((price - trade["entry"]) / trade["entry"]) * 100 * trade["leverage"] if trade["direction"] == "BUY" else ((trade["entry"] - price) / trade["entry"]) * 100 * trade["leverage"]
            time_elapsed = int((current_time - trade["timestamp"].timestamp()) / 60)
            msg = f"📊 <b>TRADE UPDATE {coin}</b> | {get_ist_time()}\n\nDirection: {trade['direction']} {trade['leverage']}x\nEntry: {format_price(trade['entry'])} | Current: {format_price(price)}\nPnL: {cur_pnl:+.2f}% | Time: {time_elapsed} mins\n\nTrend: {'Reversing ⚠️' if trade.get('reversal_alerted') else 'Still Valid ✅'}\n\nNext update in 30 mins"
            send_telegram(msg)
            last_trade_update[coin] = current_time 

def poll_telegram_commands():
    global last_update_id
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            res = requests.get(url, params={"offset": last_update_id + 1 if last_update_id else None, "timeout": 10}, timeout=15)
            if res.status_code != 200: continue
            for u in res.json().get("result", []):
                last_update_id = u["update_id"]
                if "callback_query" in u:
                    c = u["callback_query"]["data"].split("_")[1]
                    if u["callback_query"]["data"].startswith("ACTIVATE") and c in pending_signals:
                        active_trades[c] = pending_signals[c]
                        pattern_stats[pending_signals[c]["pattern"]]["signals"] += 1
                        last_trade_update[c] = time.time()
                        send_telegram(f"🚀 <b>{c} Activated</b>\n\nMonitoring for TP/SL/Trend."); del pending_signals[c]
                    elif u["callback_query"]["data"].startswith("IGNORE") and c in pending_signals:
                        send_telegram(f"❌ {c} Ignored"); del pending_signals[c]
                elif "message" in u:
                    t = u["message"].get("text", "").lower()
                    if t == "/stats": send_telegram(get_pattern_stats_text())
                    elif t == "/trades": send_telegram(get_active_trades_text())
                    elif t == "/help": send_telegram("🤖 <b>Commands</b>\n/stats - Patterns\n/trades - Active\n/help - Menu")
        except: pass
        time.sleep(2)

def send_hourly_report():
    global last_hourly_time
    now = time.time()
    if (now - last_hourly_time) >= 3600:
        report = f"📊 <b>Hourly Report {get_ist_time()}</b>\n\n<b>Coins:</b> {len(COINS)}\n<b>Active:</b> {len(active_trades)}\n<b>Pending:</b> {len(pending_signals)}\n\n" + get_pattern_stats_text()
        send_telegram(report)
        last_hourly_time = now

def main():
    global last_batch_time, last_river_time
    print("🚀 Bot v4.6 ULTIMATE starting...")
    load_trade_history()
    threading.Thread(target=poll_telegram_commands, daemon=True).start()
    send_telegram(f"🚀 <b>Bot v4.6 ULTIMATE Started</b>\n\n<b>Coins:</b> {len(COINS)}\n<b>Features:</b> 15 Patterns | Real Math | 1-Hr RIVER Signal | 1x Trend Reversal Alert")

    last_batch_time = time.time()
    last_river_time = time.time()

    while True:
        try:
            scan_market()
            check_active_trades()
            send_hourly_report()

            now = time.time()
            if (now - last_batch_time) >= BATCH_INTERVAL: send_hourly_batch()
            if (now - last_river_time) >= RIVER_INTERVAL: send_river_signal()

            save_trade_history()
            time.sleep(SCAN_INTERVAL)
        except Exception as e:
            print(f"Main loop error: {e}")
            time.sleep(60)

if __name__ == "__main__": main()
