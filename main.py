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

trade_lock = threading.Lock()
IST = ZoneInfo("Asia/Kolkata")

# Duplicate-free coin list
COINS = list(dict.fromkeys([
    "BTC","ETH","BNB","SOL","XRP","DOGE","ADA","TRX","AVAX","SHIB",
    "DOT","LINK","BCH","NEAR","LTC","UNI","APT","ETC","HBAR","FIL",
    "ARB","VET","INJ","OP","ATOM","TIA","SUI","SEI","ALGO","EGLD",
    "FLOW","EOS","XTZ","AAVE","MKR","GRT","SNX","COMP","CRV","SUSHI",
    "LDO","CAKE","1INCH","DYDX","GMX","ENS","PENDLE","RNDR","FET","WLD",
    "AR","THETA","LPT","AKT","SAND","MANA","RIVER","AXS","GALA","CHZ","APE",
    "GMT","ENJ","PEPE","WIF","FLOKI","BONK","ORDI","BOME","NOT","DOGS"
]))

# ================= STATE MANAGEMENT =================
active_trades = {}
pending_signals = {}
hourly_queue = {}
sent_coins = []
pattern_stats = {p: {"signals":0,"wins":0,"losses":0,"total_pnl":0} for p in [
    "EMA Trend", "Breakout", "Pullback to 20 EMA", "RSI Reversal", "Momentum Surge",
    "Volume Spike", "Double Bottom", "Double Top", "Support Bounce", "Resistance Rejection",
    "Bullish Engulfing", "Bearish Engulfing", "Volume Breakout", "Bull Flag Break", "Bear Flag Break"
]}

last_update_id = None
last_batch_time = time.time()
last_river_time = time.time()
last_hourly_time = time.time()

SCAN_INTERVAL = 300
BATCH_INTERVAL = 7200
RIVER_INTERVAL = 1800 
MIN_SETUP_SCORE = 88 
MIN_PROFIT_TARGET = 20.0
DELAY_BETWEEN_COINS = 0.15
MAX_PRICE_DRIFT = 0.02
MAX_SIGNALS_PER_BATCH = 3

# ================= PERSISTENCE =================
def save_active_trades():
    with trade_lock:
        try:
            serializable = {k: {**v, "timestamp": v["timestamp"].isoformat()} for k, v in active_trades.items()}
            with open("active_trades.json", "w") as f:
                json.dump(serializable, f)
        except: pass

def load_active_trades():
    global active_trades
    try:
        if os.path.exists("active_trades.json"):
            with open("active_trades.json", "r") as f:
                data = json.load(f)
                active_trades = {k: {**v, "timestamp": datetime.fromisoformat(v["timestamp"])} for k, v in data.items()}
    except: pass

def save_trade_history():
    with trade_lock:
        try:
            with open("trades.json", "w") as f: json.dump(pattern_stats, f)
        except: pass

def load_trade_history():
    global pattern_stats
    try:
        if os.path.exists("trades.json"):
            with open("trades.json", "r") as f:
                loaded = json.load(f)
                for p in pattern_stats.keys():
                    if p in loaded: pattern_stats[p] = loaded[p]
    except: pass
# ================= UTILS, INDICATORS & LOGIC =================
def format_price(price):
    if price >= 1000: return f"{price:.2f}"
    elif price >= 1: return f"{price:.4f}"
    elif price >= 0.01: return f"{price:.6f}"
    else: return f"{price:.8f}"

def get_ist_time(): return datetime.now(IST).strftime("%I:%M:%S %p IST")
def get_ist_datetime(): return datetime.now(IST)

def get_price(symbol):
    try:
        res = requests.get(BINANCE_PRICE_URL, params={"symbol": symbol}, timeout=10)
        return float(res.json()["price"]) if res.status_code == 200 else None
    except: return None

def get_klines(symbol, interval, limit=100):
    try:
        res = requests.get(BINANCE_KLINE_URL, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=10)
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

def calculate_atr(klines, period=14):
    if len(klines) < period + 1: return 0
    trs = []
    for i in range(1, len(klines)):
        h, l, pc = float(klines[i][2]), float(klines[i][3]), float(klines[i-1][4])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs[-period:]) / period

def get_news_headlines(coin):
    if not NEWS_API_KEY: return []
    try:
        res = requests.get("https://cryptopanic.com/api/v1/posts/", params={"auth_token": NEWS_API_KEY, "currencies": coin, "kind": "news"}, timeout=5)
        return [p["title"] for p in res.json().get("results", [])[:3]]
    except: return []

def get_dynamic_leverage(symbol, atr_pct, confidence):
    base = symbol.replace("USDT", "")
    if base in ["BTC", "ETH"]: return 10
    if base in ["BNB", "SOL"]: return 8
    if atr_pct < 2.0 and confidence > 80: return 8
    if atr_pct < 4.0: return 5
    return 4

def get_active_trades_text():
    if not active_trades: return "No active trades"
    text = f"📊 <b>Active Trades ({len(active_trades)})</b>\n\n"
    for coin, trade in active_trades.items():
        text += f"<b>{coin}</b> {trade['direction']}\n"
        text += f"Entry: {format_price(trade['entry'])} | SL: {format_price(trade['sl'])}\n"
        text += f"TP: {format_price(trade['tp'])} | Lev: {trade['leverage']}x\n\n"
    return text

def get_pattern_stats_text():
    text = "📈 <b>Pattern Performance</b>\n\n"
    sorted_patterns = sorted(pattern_stats.items(), key=lambda x: x[1]["signals"], reverse=True)
    for pattern, stats in sorted_patterns[:10]:
        if stats["signals"] > 0:
            win_rate = (stats["wins"] / stats["signals"]) * 100
            text += f"<b>{pattern}</b>\n"
            text += f"Signals: {stats['signals']} | Win: {win_rate:.1f}% | PnL: {stats['total_pnl']:.1f}%\n\n"
    return text
# ================= PATTERN DETECTION WITH BTC FILTER =================
def detect_patterns(symbol, klines, price, btc_trend):
    if len(klines) < 50: return []
    closes = [float(k[4]) for k in klines]
    opens, highs, lows = [float(k[1]) for k in klines], [float(k[2]) for k in klines], [float(k[3]) for k in klines]
    vols = [float(k[5]) for k in klines]
    avg_v = sum(vols[-20:])/20
    rsi = calculate_rsi(closes)
    ema20 = calculate_ema(closes, 20)
    ema50 = calculate_ema(closes, 50)
    p = []

    if ema20 and price > ema20 and price > max(highs[-5:-1]) and btc_trend == 1:
        p.append(("Bull Flag Break", 92, "BUY"))

    if ema20 and price < ema20 and price < min(lows[-5:-1]) and btc_trend == -1:
        p.append(("Bear Flag Break", 92, "SELL"))

    if (closes[-1] > max(highs[-20:-1]) and vols[-1] > avg_v * 1.5):
        if btc_trend == 1: p.append(("Breakout", 88, "BUY"))
    elif (closes[-1] < min(lows[-20:-1]) and vols[-1] > avg_v * 1.5):
        if btc_trend == -1: p.append(("Breakout", 88, "SELL"))

    if (opens[-2] > closes[-2] and opens[-1] < closes[-2] and closes[-1] > opens[-2]):
        if btc_trend == 1: p.append(("Bullish Engulfing", 90, "BUY"))
    elif (opens[-2] < closes[-2] and opens[-1] > closes[-2] and closes[-1] < opens[-2]):
        if btc_trend == -1: p.append(("Bearish Engulfing", 90, "SELL"))

    if ema20 and ema50:
        if price > ema20 > ema50 and btc_trend == 1: p.append(("EMA Trend", 85, "BUY"))
        elif price < ema20 < ema50 and btc_trend == -1: p.append(("EMA Trend", 85, "SELL"))
    if ema20 and abs(price - ema20)/ema20 < 0.005: p.append(("Pullback to 20 EMA", 82, "BUY" if price > ema20 else "SELL"))
    if rsi < 30: p.append(("RSI Reversal", 80, "BUY"))
    elif rsi > 70: p.append(("RSI Reversal", 80, "SELL"))
    
    mom = (closes[-1] - closes[-3])/closes[-3]*100 if len(closes) > 3 else 0
    if mom > 3 and btc_trend == 1: p.append(("Momentum Surge", 87, "BUY"))
    elif mom < -3 and btc_trend == -1: p.append(("Momentum Surge", 87, "SELL"))
    if vols[-1] > avg_v * 3.5: p.append(("Volume Spike", 84, "BUY" if closes[-1] > opens[-1] else "SELL"))
    
    sup, res = min(lows[-30:-1]), max(highs[-30:-1])
    if price <= sup * 1.005 and closes[-1] > opens[-1]: p.append(("Support Bounce", 88, "BUY"))
    if price >= res * 0.995 and closes[-1] < opens[-1]: p.append(("Resistance Rejection", 88, "SELL"))
    
    if len(lows) > 40:
        if abs(min(lows[-40:-20]) - min(lows[-10:]))/price < 0.005: p.append(("Double Bottom", 90, "BUY"))
        if abs(max(highs[-40:-20]) - max(highs[-10:]))/price < 0.005: p.append(("Double Top", 90, "SELL"))

    if price > res and vols[-1] > avg_v * 2.5 and btc_trend == 1: p.append(("Volume Breakout", 91, "BUY"))

    return p
   # ================= VERIFICATION & SENDING =================
def format_and_send(setup, coin, is_river=False):
    global pending_signals, sent_coins, hourly_queue
    p, k = get_price(setup["symbol"]), get_klines(setup["symbol"], "15m")
    if not p or not k: return False
    
    closes = [float(x[4]) for x in k]
    atr = calculate_atr(k)
    
    atr_pct = (atr / p) * 100 if p > 0 else 0
    lev = setup.get(
        "leverage",
        get_dynamic_leverage(
            setup["symbol"],
            atr_pct,
            setup["setup_score"]
        )
    )
    
    sl = p - (atr * 1.5) if setup["direction"] == "BUY" else p + (atr * 1.5)
    tp = p + (atr * 3.0) if setup["direction"] == "BUY" else p - (atr * 3.0)
    
    profit_target = (abs(tp - p) / p) * 100 * lev

    if profit_target < MIN_PROFIT_TARGET:
        risk_per_unit = abs(tp - p) / p
        if risk_per_unit > 0:
            needed_lev = int(MIN_PROFIT_TARGET / (risk_per_unit * 100)) + 1
            if needed_lev <= 10:
                lev = needed_lev
                profit_target = (abs(tp - p) / p) * 100 * lev
            else:
                return False

    setup["leverage"] = lev
    
    price_range = (max(closes[-10:]) - min(closes[-10:])) / 10
    eta = int(abs(tp - p) / (price_range if price_range > 0 else 0.001) * 15)
    
    mom = (closes[-1] - closes[-3])/closes[-3]*100
    news = get_news_headlines(coin)

    header = "🌊 <b>RIVER SIGNAL (1-HR)</b>" if is_river else f"🔥 <b>VERIFIED SETUP {coin}</b>"
    msg = f"{header} | Score: {int(setup['setup_score'])}/100\n\n"
    msg += f"📢 Direction: {setup['direction']} | Leverage: {lev}x\n"
    msg += f"💰 Entry: {format_price(p)}\n🎯 TP: {format_price(tp)}\n🛑 SL: {format_price(sl)}\n\n"
    msg += f"📈 Profit Target: {profit_target:.2f}%\n"
    msg += f"📌 Pattern: {setup['pattern']} | RSI: {calculate_rsi(closes):.2f}\n"
    msg += f"⚡ Momentum: {mom:.2f}% | 🚀 Velocity: {abs(mom/45):.4f}/min\n"
    msg += f"⏳ ETA: ~{eta} mins | ⏰ Expires: 1hr\n"
    msg += f"✏️ ATR: {format_price(atr)}\n\n"
    if news: msg += "<b>📰 News:</b>\n" + "\n".join([f"• {n[:60]}..." for n in news]) + "\n\n"
    msg += f"⏰ Verified At: {get_ist_time()}"

    setup.update({"entry":p,"sl":sl,"tp":tp,"timestamp":get_ist_datetime(),"reversal_alerted":False})
    pending_signals[coin] = setup
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "✅ Activate Trade", "callback_data": f"ACTIVATE_{coin}"},
                {"text": "❌ Ignore", "callback_data": f"IGNORE_{coin}"}
            ]]
        }
    }
    
    if requests.post(url, json=payload, timeout=30).status_code == 200:
        sent_coins.append(setup["coin"])
        for c in sent_coins:
            if c in hourly_queue:
                del hourly_queue[c]
        return True
    return False

def send_hourly_batch():
    global hourly_queue, last_batch_time, sent_coins
    if not hourly_queue: return
    sorted_q = sorted(hourly_queue.values(), key=lambda x: x["setup_score"], reverse=True)
    sent_count = 0
    for s in sorted_q:
        if s["coin"] == "RIVER": continue
        if sent_count >= MAX_SIGNALS_PER_BATCH: break
        if format_and_send(s, s["coin"]): sent_count += 1
    sent_coins = []
    hourly_queue.clear()
    last_batch_time = time.time()
 # ================= TRACKING, COMMANDS & MAIN LOOP =================
def check_active_trades():
    global active_trades
    for c, t in list(active_trades.items()):
        p = get_price(t["symbol"])
        if not p: continue
        
        if not t.get("reversal_alerted", False):
            cl = [float(x[4]) for x in get_klines(t["symbol"], "15m", 20)]
            ema20 = calculate_ema(cl, 20)
            if ema20 and ((t["direction"] == "BUY" and p < ema20 * 0.995) or (t["direction"] == "SELL" and p > ema20 * 1.005)):
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": f"⚠️ <b>TREND REVERSAL {c}</b>\nPrice broke EMA20.", "parse_mode": "HTML"})
                active_trades[c]["reversal_alerted"] = True
                save_active_trades()

        current_pnl = ((p - t["entry"]) / t["entry"]) * 100 * t["leverage"] if t["direction"] == "BUY" else ((t["entry"] - p) / t["entry"]) * 100 * t["leverage"]
        if not t.get("breakeven_sent", False) and current_pnl >= 10:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    "chat_id": CHAT_ID,
                    "text": f"🟡 BREAK-EVEN ALERT {c}\n\nTrade reached +10% profit.\nConsider moving SL to entry.\n\nCurrent PnL: {current_pnl:.2f}%"
                }
            )
            active_trades[c]["breakeven_sent"] = True
            save_active_trades()

        hit = None
        if t["direction"] == "BUY":
            if p >= t["tp"]: hit = "WIN"
            elif p <= t["sl"]: hit = "LOSS"
        else:
            if p <= t["tp"]: hit = "WIN"
            elif p >= t["sl"]: hit = "LOSS"
            
        if hit:
            with trade_lock:
                # UPDATED STATS LOGIC
                primary_pattern = t["pattern"].split(" + ")[0]

                if primary_pattern in pattern_stats:
                    pattern_stats[primary_pattern]["signals"] += 1
                    if hit == "WIN":
                        pattern_stats[primary_pattern]["wins"] += 1
                    else:
                        pattern_stats[primary_pattern]["losses"] += 1
            
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": f"{'✅' if hit=='WIN' else '🛑'} Trade Closed: {c} ({hit})"})
            del active_trades[c]
            save_active_trades()
            save_trade_history()

def poll_telegram():
    global last_update_id
    while True:
        try:
            params = {}
            if last_update_id is not None:
                params["offset"] = last_update_id + 1
            
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            res = requests.get(url, params=params, timeout=15).json()
            for u in res.get("result", []):
                last_update_id = u["update_id"]
                
                if "callback_query" in u:
                    cb = u["callback_query"]
                    data = cb["data"]; c = data.split("_")[1]
                    
                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery", json={"callback_query_id": cb["id"], "text": "Processing..."})
                    
                    if "ACTIVATE" in data and c in pending_signals:
                        with trade_lock:
                            pending_signals[c]["breakeven_sent"] = False
                            active_trades[c] = pending_signals[c]
                        save_active_trades()
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": f"🚀 {c} Activated!"})
                        del pending_signals[c]
                    elif "IGNORE" in data and c in pending_signals:
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": f"❌ {c} Ignored"})
                        del pending_signals[c]
                        
                elif "message" in u:
                    text = u["message"].get("text", "").lower()
                    if text == "/stats":
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": get_pattern_stats_text(), "parse_mode": "HTML"})
                    elif text == "/trades":
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": get_active_trades_text(), "parse_mode": "HTML"})
        except: pass
        time.sleep(2)

def send_hourly_report():
    global last_hourly_time
    now = time.time()
    if (now - last_hourly_time) >= 3600:
        report = f"📊 <b>Hourly Report {get_ist_time()}</b>\n\nActive: {len(active_trades)} | Pending: {len(pending_signals)}\n" + get_pattern_stats_text()
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": report, "parse_mode": "HTML"})
        last_hourly_time = now

def main():
    global last_batch_time, last_river_time
    load_active_trades(); load_trade_history()
    threading.Thread(target=poll_telegram, daemon=True).start()
    
    while True:
        try:
            btc_p = get_price("BTCUSDT"); btc_k = get_klines("BTCUSDT", "1h", 100)
            btc_ema50 = calculate_ema([float(x[4]) for x in btc_k], 50)
            
            if not btc_p or btc_ema50 is None:
                time.sleep(60)
                continue
            
            btc_trend = 1 if btc_p > btc_ema50 else -1
            
            for coin in COINS:
                symbol = coin + "USDT"; p = get_price(symbol); k = get_klines(symbol, "15m")
                if not p or not k: continue
                
                found = detect_patterns(symbol, k, p, btc_trend)
                if found:
                    best = max(found, key=lambda x: x[1])
                    confirmed_patterns = list(dict.fromkeys([x[0] for x in found]))
                    
                    primary_pattern = best[0]
                    confirmation_patterns = [pat for pat in confirmed_patterns if pat != primary_pattern]
                    pattern_text = primary_pattern
                    if confirmation_patterns:
                        pattern_text += " + " + " + ".join(confirmation_patterns[:2])
                    
                    confirmation_bonus = min(len(found) * 2, 8)
                    boosted_score = min(best[1] + confirmation_bonus, 99)

                    if boosted_score >= MIN_SETUP_SCORE:
                        atr = calculate_atr(k)
                        atr_pct = (atr / p) * 100 if p > 0 else 0
                        lev = get_dynamic_leverage(symbol, atr_pct, boosted_score)
                        
                        new_setup = {
                            "coin": coin,
                            "symbol": symbol,
                            "direction": best[2],
                            "pattern": pattern_text,
                            "setup_score": boosted_score,
                            "leverage": lev
                        }

                        if (coin not in hourly_queue or boosted_score > hourly_queue[coin]["setup_score"]):
                            hourly_queue[coin] = new_setup
                time.sleep(DELAY_BETWEEN_COINS)
            
            check_active_trades(); send_hourly_report()
            
            now = time.time()
            if (now - last_batch_time) >= BATCH_INTERVAL:
                send_hourly_batch()
                
            if (now - last_river_time) >= 1800:
                try:
                    if "RIVER" not in active_trades and "RIVER" not in pending_signals:
                        p_r = get_price("RIVERUSDT")
                        k_r = get_klines("RIVERUSDT", "15m", 100)
                        
                        if p_r and k_r and len(k_r) >= 50:
                            f_r = detect_patterns("RIVERUSDT", k_r, p_r, 1) + detect_patterns("RIVERUSDT", k_r, p_r, -1)
                            unique_patterns = []
                            seen = set()
                            for pat in f_r:
                                key = (pat[0], pat[2])
                                if key not in seen:
                                    seen.add(key); unique_patterns.append(pat)
                            
                            f_r = unique_patterns
                            if f_r:
                                # UPDATED MULTI-CONFIRMATION LOGIC FOR RIVER
                                best_r = max(f_r, key=lambda x: x[1])

                                confirmed_patterns_r = list(dict.fromkeys([x[0] for x in f_r]))

                                primary_pattern_r = best_r[0]

                                confirmation_patterns_r = [
                                    pat for pat in confirmed_patterns_r
                                    if pat != primary_pattern_r
                                ]

                                pattern_text_r = primary_pattern_r

                                if confirmation_patterns_r:
                                    pattern_text_r += " + " + " + ".join(confirmation_patterns_r[:2])

                                confirmation_bonus_r = min(len(f_r) * 2, 8)

                                boosted_score_r = min(best_r[1] + confirmation_bonus_r, 99)

                                if boosted_score_r >= MIN_SETUP_SCORE:
                                    atr_r = calculate_atr(k_r); atr_pct_r = (atr_r / p_r) * 100 if p_r > 0 else 0
                                    lev_r = get_dynamic_leverage("RIVERUSDT", atr_pct_r, boosted_score_r)
                                    river_setup = {
                                        "coin": "RIVER",
                                        "symbol": "RIVERUSDT",
                                        "direction": best_r[2],
                                        "pattern": pattern_text_r,
                                        "setup_score": boosted_score_r,
                                        "leverage": lev_r
                                    }
                                    format_and_send(river_setup, "RIVER", True)
                    last_river_time = now
                except: pass
            
            time.sleep(SCAN_INTERVAL)
        except: time.sleep(60)

if __name__ == "__main__": main()
