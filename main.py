# ================= COINDCX + BINANCE VISION - PRODUCTION BOT v2.18.0 PREDICTIVE =================
# LOGIC: Scan 24/7 every 5min | Send BEST signals 1x per hour | Predict 30min ahead
# DYNAMIC LEVERAGE: BTC/ETH=10x | Large=8x | Mid=5x | Volatile=3x | Target 20-25%

import requests
import time
import json
import os
import threading
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ================= CONFIG =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8265055522:AAGl2v211gtKwqYTmjue_gXW9Vx0dvf8Wes")
CHAT_ID = os.getenv("CHAT_ID", "931982378")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

BINANCE_PRICE_URL = "https://data-api.binance.vision/api/v3/ticker/price"
BINANCE_KLINE_URL = "https://data-api.binance.vision/api/v3/klines"

# ================= 150 VERIFIED COINDCX FUTURES COINS =================
COINS = [
    "BTC","ETH","BNB","SOL","XRP","DOGE","ADA","TRX","AVAX","SHIB",
    "DOT","LINK","BCH","NEAR","MATIC","LTC","ICP","UNI","APT","ETC",
    "HBAR","FIL","ARB","VET","INJ","OP","ATOM","TIA","SUI","SEI",
    "FTM","ALGO","EGLD","NEO","FLOW","EOS","KLAY","IOTA","KAVA","XTZ",
    "ONE","ZIL","QTUM","W","AAVE","MKR","GRT","SNX","COMP","CRV",
    "SUSHI","LDO","RPL","GNO","CAKE","1INCH","DYDX","GMX","ENS","PENDLE",
    "JUP","PYTH","RNDR","FET","WLD","AR","THETA","LPT","ROSE","AKT",
    "SAND","MANA","AXS","GALA","CHZ","APE","GMT","ENJ","AGIX","OCEAN",
    "PEPE","WIF","FLOKI","BONK","ORDI","BOME","NOT","DOGS","CELO","SFP",
    "BLUR","MASK","LUNC","ZRX","BAT","HOT","DASH","ICX","ONT","ZEC",
    "XLM","ORDI","RUNE","STX","KAS","CRO","IMX","MINA","KDA","ANKR",
    "CFX","STORJ","SKL","BAND","REEF","COTI","CHR","CTSI","LRC","API3",
    "BAL","BNT","CEEK","CVC","DENT","DGB","FLUX","GLM","HNT","IOTX",
    "JASMY","KNC","NKN","OGN","OXT","PAXG","PHA","PUNDIX","REQ","RLC",
    "RVN","SC","STMX","STPT","SXP","SYS","TLM","TRB","UMA","VTHO",
    "WAN","WRX","XEM","XVS","YFI","YGG","ZEN","ACH","AERGO","ALICE",
    "ALPHA","ARPA","ASTR","AUDIO","BADGER","BICO","BLZ","CELR","CHESS","CKB"
]

PRIMARY_PATTERNS = [
    "EMA Trend", "Breakout", "Pullback to 20 EMA", "RSI Reversal", "Momentum Surge",
    "Volume Spike", "Double Bottom", "Bull Flag", "Trend Continuation", "Range Break + Retest"
]

SHADOW_PATTERNS = [
    "Head and Shoulders", "Inverse H&S", "Double Top", "Bear Flag",
    "Ascending Triangle", "Descending Triangle", "Rising Wedge", "Falling Wedge",
    "Cup and Handle", "Support Bounce", "Resistance Rejection", "Fake Breakout",
    "Liquidity Sweep", "Order Block", "Scalping Setup"
]

ALL_PATTERNS = PRIMARY_PATTERNS + SHADOW_PATTERNS

# ================= STATE =================
active_trades = {}
pending_signals = {}
hourly_queue = {} # NEW: Stores setups forming for next hourly batch
pattern_stats = {p: {"signals":0,"wins":0,"losses":0,"total_pnl":0} for p in ALL_PATTERNS}
last_update_id = None
last_report_time = time.time()
last_hourly_batch_time = 0 # NEW: Track last hourly send
IST = ZoneInfo("Asia/Kolkata")
SCAN_INTERVAL = 300 # 5min scan 24/7 - YOUR RULE
REQUEST_TIMEOUT = 8
DELAY_BETWEEN_COINS = 0.15
MAX_SIGNALS_PER_HOUR = 3 # YOUR RULE: Max 3 best signals per hour
MIN_SETUP_SCORE = 75 # Setup must be 75% formed to queue

# ================= UTILS =================
def get_ist_time():
    return datetime.now(IST).strftime("%I:%M:%S %p IST")

def get_ist_datetime():
    return datetime.now(IST)

def is_top_of_hour():
    now = get_ist_datetime()
    return now.minute == 0 # Send at :00 minutes

def send_telegram(msg, coin=None, add_buttons=False):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
        if add_buttons and coin:
            payload["reply_markup"] = {
                "inline_keyboard": [[
                    {"text": "✅ Activate Trade", "callback_data": f"ACTIVATE_{coin}"},
                    {"text": "❌ Ignore", "callback_data": f"IGNORE_{coin}"}
                ]]
            }
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code!= 200:
            print(f"Telegram Error: {res.text}")
    except Exception as e:
        print(f"Telegram Error: {e}")

def answer_callback(callback_query_id, text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
        payload = {"callback_query_id": callback_query_id, "text": text}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Callback Error: {e}")

def save_trade_history():
    try:
        with open("trades.json", "w") as f:
            json.dump(pattern_stats, f)
    except Exception as e:
        print(f"Save error: {e}")

def load_trade_history():
    global pattern_stats
    try:
        with open("trades.json", "r") as f:
            pattern_stats = json.load(f)
    except:
        print("No history file, starting fresh")
      # ================= DATA FETCH =================
def get_price(symbol):
    try:
        res = requests.get(BINANCE_PRICE_URL, params={"symbol": symbol}, timeout=REQUEST_TIMEOUT)
        if res.status_code == 200:
            return float(res.json()["price"])
        return None
    except Exception as e:
        print(f"Price error {symbol}: {e}")
        return None

def get_candles(symbol, interval="15m", limit=100):
    try:
        res = requests.get(BINANCE_KLINE_URL, params={"symbol":symbol,"interval":interval,"limit":limit}, timeout=REQUEST_TIMEOUT)
        data = res.json()
        if not isinstance(data, list): return [], [], [], [], [], []
        closes = [float(x[4]) for x in data]
        highs = [float(x[2]) for x in data]
        lows = [float(x[3]) for x in data]
        opens = [float(x[1]) for x in data]
        volumes = [float(x[5]) for x in data]
        times = [int(x[0]) for x in data]
        return closes, highs, lows, opens, volumes, times
    except Exception as e:
        print(f"Candle error {symbol}: {e}")
        return [], [], [], [], [], []

def ema(prices, period=20):
    if not prices: return 0
    k = 2 / (period + 1)
    e = prices[0]
    for p in prices: e = p * k + e * (1 - k)
    return e

def rsi(prices, period=14):
    if len(prices) < period + 1: return 50
    gains = [prices[i]-prices[i-1] for i in range(1,len(prices)) if prices[i]>prices[i-1]]
    losses = [abs(prices[i]-prices[i-1]) for i in range(1,len(prices)) if prices[i]<prices[i-1]]
    avg_gain = sum(gains[-period:]) / period if gains else 0
    avg_loss = sum(losses[-period:]) / period if losses else 1
    return 100 if avg_loss == 0 else 100 - (100 / (1 + avg_gain/avg_loss))

def atr(highs, lows, closes, period=14):
    if len(closes) < 2: return 0
    trs = [max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])) for i in range(1,len(closes))]
    return sum(trs[-period:]) / period if trs else 0

# ================= ETA + VOLATILITY =================
def calculate_eta(entry, target, atr_val, momentum, timeframe):
    if atr_val == 0 or entry == target: return "N/A"
    distance = abs(target - entry)
    candles_needed = distance / atr_val
    if abs(momentum) >= 4: candles_needed *= 0.5
    elif abs(momentum) >= 2: candles_needed *= 0.7
    tf_minutes = {"15m":15, "30m":30, "1h":60, "4h":240}
    minutes = candles_needed * tf_minutes.get(timeframe, 15)
    if minutes < 60: return f"{int(minutes)}-{int(minutes*1.5)} mins"
    elif minutes < 1440: return f"{int(minutes/60)}-{int(minutes/60*1.5)} hours"
    else: return f"{int(minutes/1440)}-{int(minutes/1440*1.5)} days"

def get_volatility_rank(atr_val, price):
    atr_pct = (atr_val / price) * 100
    if atr_pct > 3: return "HIGH"
    elif atr_pct > 1.5: return "MED"
    else: return "LOW"

# ================= FILTERS =================
def btc_allows_trade(direction):
    try:
        btc_closes = get_candles("BTCUSDT", "1h", 50)[0]
        if not btc_closes: return True
        btc_trend = "BUY" if btc_closes[-1] > ema(btc_closes, 20) else "SELL"
        return btc_trend == direction
    except:
        return True

# ================= PATTERN DETECTION =================
def detect_primary_patterns(closes, highs, lows, opens, volumes, price, trend_score, rsi_val, momentum, vol_strength, atr_val):
    patterns = []
    if abs(trend_score) >= 3: patterns.append("EMA Trend")
    resistance = max(highs[-20:])
    if price > resistance * 1.001 and vol_strength >= 130 and closes[-1] > opens[-1]: patterns.append("Breakout")
    ema20 = ema(closes, 20)
    if abs(trend_score) >= 2 and abs(price - ema20)/ema20 < 0.008 and ((trend_score > 0 and closes[-1] > opens[-1]) or (trend_score < 0 and closes[-1] < opens[-1])): patterns.append("Pullback to 20 EMA")
    if (rsi_val < 30 and closes[-1] > opens[-1]) or (rsi_val > 70 and closes[-1] < opens[-1]): patterns.append("RSI Reversal")
    if abs(momentum) >= 3 and abs(closes[-1] - closes[-5])/closes[-5] * 100 >= 2: patterns.append("Momentum Surge")
    if vol_strength >= 200 and ((closes[-1] > opens[-1] and trend_score >= 0) or (closes[-1] < opens[-1] and trend_score < 0)): patterns.append("Volume Spike")
    if len(lows) >= 20:
        recent_low = min(lows[-10:])
        prev_low = min(lows[-20:-10])
        if abs(recent_low - prev_low)/prev_low < 0.005 and rsi_val < 40 and closes[-1] > opens[-1]: patterns.append("Double Bottom")
    if momentum > 5 and max(closes[-5:]) - min(closes[-5:]) < atr_val * 1.5 and closes[-1] > closes[-2]: patterns.append("Bull Flag")
    if closes[-1] > closes[-5] > closes[-10] and trend_score >= 2 and vol_strength >= 110: patterns.append("Trend Continuation")
    if len(highs) >= 25 and price > max(highs[-20:]) and min(lows[-5:]) > max(highs[-25:-20]) * 0.998: patterns.append("Range Break + Retest")
    return patterns

def detect_shadow_patterns(closes, highs, lows, opens, volumes, price, trend_score, rsi_val):
    patterns = []
    if rsi_val > 80 and closes[-1] < opens[-1]: patterns.append("Double Top")
    if max(highs[-5:]) - min(lows[-5:]) < atr(highs,lows,closes) * 1.2: patterns.append("Scalping Setup")
    return patterns  
# ================= DYNAMIC LEVERAGE - YOUR RULE =================
def get_dynamic_leverage(symbol, atr_val, entry):
    atr_pct = (atr_val / entry) * 100
    if symbol in ["BTCUSDT", "ETHUSDT", "BNBUSDT"]:
        return 10 if atr_pct < 1.5 else 8
    if atr_pct > 4.0: return 3
    elif atr_pct > 2.5: return 5
    elif atr_pct > 1.5: return 8
    else: return 10

def get_smart_sl_tp(closes, highs, lows, direction, entry, atr_val, momentum, vol_strength, symbol):
    if direction == "BUY":
        swing_low = min(lows[-10:])
        sl = swing_low - atr_val * 0.5
        sl = max(sl, entry * 0.98)
        signal_high = highs[-1]
        signal_low = lows[-1]
        ideal_entry = signal_low + (signal_high - signal_low) * 0.382
        entry_zone_low = signal_low + (signal_high - signal_low) * 0.236
        entry_zone_high = signal_low + (signal_high - signal_low) * 0.5
    else:
        swing_high = max(highs[-10:])
        sl = swing_high + atr_val * 0.5
        sl = min(sl, entry * 1.02)
        signal_high = highs[-1]
        signal_low = lows[-1]
        ideal_entry = signal_high - (signal_high - signal_low) * 0.382
        entry_zone_low = signal_high - (signal_high - signal_low) * 0.5
        entry_zone_high = signal_high - (signal_high - signal_low) * 0.236

    sl_distance = abs(entry - sl)
    tp_mult = 1.2
    if abs(momentum) >= 4: tp_mult += 0.2
    elif abs(momentum) >= 2: tp_mult += 0.1
    if vol_strength >= 200: tp_mult += 0.1
    tp_mult = min(tp_mult, 1.5)

    if direction == "BUY":
        tp = entry + (sl_distance * tp_mult)
    else:
        tp = entry - (sl_distance * tp_mult)

    leverage = get_dynamic_leverage(symbol, atr_val, entry)
    profit_target = abs((tp - entry) / entry) * 100 * leverage
    risk_percent = abs((sl - entry) / entry) * 100
    return sl, tp, leverage, profit_target, tp_mult, ideal_entry, entry_zone_low, entry_zone_high, risk_percent

# ================= PREDICTIVE SIGNAL DETECTION =================
def calculate_setup_score(conf, rsi_val, momentum, vol_strength, price, ideal_entry):
    score = conf # Base 0-100
    # Bonus if near ideal entry zone
    entry_distance_pct = abs(price - ideal_entry) / ideal_entry * 100
    if entry_distance_pct < 0.5: score += 15 # Within 0.5% of ideal
    elif entry_distance_pct < 1.0: score += 10
    elif entry_distance_pct < 2.0: score += 5
    # Bonus for momentum
    if abs(momentum) >= 4: score += 10
    elif abs(momentum) >= 2: score += 5
    # Bonus for volume
    if vol_strength >= 200: score += 10
    elif vol_strength >= 150: score += 5
    return min(round(score), 100)

def detect_setup(coin):
    symbol = coin + "USDT"
    price = get_price(symbol)
    if not price: return None

    best_setup = None
    for tf in ["15m", "30m"]:
        closes, highs, lows, opens, volumes, times = get_candles(symbol, tf, 100)
        if len(closes) < 50: continue

        rsi_val = rsi(closes)
        atr_val = atr(highs, lows, closes)

        trend_data = []
        for t in ["15m","30m","1h"]:
            t_closes = get_candles(symbol,t,50)[0]
            if t_closes: trend_data.append(1 if price > ema(t_closes,20) else -1)
        trend_score = sum(trend_data)

        momentum = ((closes[-1] - closes[-10]) / closes[-10]) * 100 if len(closes) >= 10 else 0
        vol_strength = (volumes[-1] / (sum(volumes[:-1])/len(volumes[:-1]))) * 100 if len(volumes) > 1 else 100

        direction = "BUY" if trend_score >= 0 else "SELL"
        if not btc_allows_trade(direction): continue

        primary_patterns = detect_primary_patterns(closes, highs, lows, opens, volumes, price, trend_score, rsi_val, momentum, vol_strength, atr_val)
        if not primary_patterns: continue

        pattern = primary_patterns[0]
        conf = 35 + min(20, abs(trend_score)*4)
        if vol_strength >= 150: conf += 15
        if abs(momentum) >= 4: conf += 15
        conf = min(round(conf), 95)

        sl, tp, leverage, profit_target, tp_mult, ideal_entry, ez_low, ez_high, risk_pct = get_smart_sl_tp(closes, highs, lows, direction, price, atr_val, momentum, vol_strength, symbol)
        setup_score = calculate_setup_score(conf, rsi_val, momentum, vol_strength, price, ideal_entry)

        # YOUR RULE: Only queue if 75%+ formed
        if setup_score >= MIN_SETUP_SCORE:
            eta = calculate_eta(price, tp, atr_val, momentum, tf)
            vol_rank = get_volatility_rank(atr_val, price)
            expires_at = get_ist_datetime() + timedelta(minutes=60) # Valid for next hour

            setup = {
                "coin": coin, "direction": direction, "entry": price, "tp": tp, "sl": sl,
                "pattern": pattern, "confidence": conf, "setup_score": setup_score,
                "timeframe": tf, "rsi": rsi_val, "momentum": momentum, "atr": atr_val,
                "vol_strength": vol_strength, "initial_sl": sl, "leverage": leverage,
                "profit_target": profit_target, "tp_mult": tp_mult, "start_time": time.time(),
                "ideal_entry": ideal_entry, "entry_zone_low": ez_low, "entry_zone_high": ez_high,
                "risk_percent": risk_pct, "eta": eta, "vol_rank": vol_rank,
                "expires_at": expires_at.strftime("%I:%M %p IST"), "liquidity": price * 1.0025
            }
            if not best_setup or setup_score > best_setup["setup_score"]:
                best_setup = setup

    return best_setup

# ================= ACTIVE TRADE MONITORING =================
def monitor_active_trades():
    global active_trades
    while True:
        try:
            for coin, trade in list(active_trades.items()):
                price = get_price(coin + "USDT")
                if not price: continue

                if trade["direction"] == "BUY":
                    pnl = (price - trade["entry"]) / trade["entry"] * 100 * trade["leverage"]
                    tp_hit = price >= trade["tp"]
                    sl_hit = price <= trade["sl"]
                else:
                    pnl = (trade["entry"] - price) / trade["entry"] * 100 * trade["leverage"]
                    tp_hit = price <= trade["tp"]
                    sl_hit = price >= trade["sl"]

                if tp_hit:
                    send_telegram(f"🎯 <b>TP HIT {coin}</b>\n\nEntry: {trade['entry']:.4f}\n\nExit: {price:.4f}\n\nProfit: +{pnl:.2f}%\n\nPattern: {trade['pattern']}")
                    track_pattern_result(trade["pattern"], pnl)
                    del active_trades
                    continue

                if sl_hit:
                    send_telegram(f"🛑 <b>SL HIT {coin}</b>\n\nEntry: {trade['entry']:.4f}\n\nExit: {price:.4f}\n\nLoss: {pnl:.2f}%\n\nPattern: {trade['pattern']}")
                    track_pattern_result(trade["pattern"], pnl)
                    del active_trades
                    continue

                sl_distance = abs(trade["entry"] - trade["initial_sl"])
                profit_distance = abs(price - trade["entry"])
                if profit_distance >= sl_distance and not trade.get("trailed"):
                    if trade["direction"] == "BUY":
                        trade["sl"] = trade["entry"] * 1.003
                    else:
                        trade["sl"] = trade["entry"] * 0.997
                    trade["trailed"] = True
                    send_telegram(f"🔒 <b>TRAIL ACTIVATED {coin}</b>\n\nSL moved to breakeven.\n\nRisk-free now!")

                closes = get_candles(coin + "USDT", "15m", 50)[0]
                if closes and len(closes) > 20:
                    current_ema = ema(closes, 20)
                    new_trend = "BUY" if closes[-1] > current_ema else "SELL"
                    if new_trend!= trade["direction"] and trade.get("last_trend_alert", 0) < time.time() - 1800:
                        eta_sl_current = calculate_eta(price, trade["sl"], trade["atr"], trade["momentum"], trade["timeframe"])
                        send_telegram(f"⚠️ <b>TREND REVERSAL {coin}</b>\n\nYour {trade['direction']} against trend.\n\nNow: {price:.4f}\n\nPnL: {pnl:.2f}%\n\nETA to SL: {eta_sl_current}")
                        trade["last_trend_alert"] = time.time()

        except Exception as e:
            print(f"Monitor error: {e}")
        time.sleep(30)
        # ================= TELEGRAM BUTTON HANDLER - FIXED =================
def handle_updates():
    global last_update_id, active_trades, pending_signals
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            params = {"offset": last_update_id + 1} if last_update_id else {}
            data = requests.get(url, params=params, timeout=10).json()
            for update in data.get("result", []):
                last_update_id = update["update_id"]
                if "callback_query" in update:
                    cq = update["callback_query"]
                    data = cq["data"]
                    coin = data.split("_")[1]
                    if data.startswith("ACTIVATE_"):
                        if coin in pending_signals:
                            active_trades = pending_signals
                            send_telegram(f"✅ <b>Tracking Activated</b> for {coin}\n\nTP/SL + Reversal + Hourly alerts ON.")
                            answer_callback(cq["id"], "Tracking ON ✅")
                            del pending_signals
                    elif data.startswith("IGNORE_"):
                        if coin in pending_signals:
                            del pending_signals
                        answer_callback(cq["id"], "Ignored")
        except Exception as e:
            print(f"Update error: {e}")
        time.sleep(2)

# ================= PATTERN TRACKING =================
def track_pattern_result(pattern, pnl_percent):
    if pattern not in pattern_stats: return
    pattern_stats[pattern]["signals"] += 1
    pattern_stats[pattern]["total_pnl"] += pnl_percent
    if pnl_percent > 0:
        pattern_stats[pattern]["wins"] += 1
    else:
        pattern_stats[pattern]["losses"] += 1
    save_trade_history()

def send_pattern_report():
    msg = f"📊 <b>PATTERN REPORT</b> - {get_ist_time()}\n\n<b>🔥 PRIMARY:</b>\n"
    for p in PRIMARY_PATTERNS:
        s = pattern_stats[p]
        if s["signals"] > 0:
            wr = round(s["wins"] / s["signals"] * 100, 1)
            avg_pnl = round(s["total_pnl"] / s["signals"], 2)
            msg += f"{p}: {s['signals']} | {wr}% WR | {avg_pnl}%\n"
    msg += "\n<b>👻 SHADOW:</b>\n"
    for p in SHADOW_PATTERNS:
        s = pattern_stats[p]
        if s["signals"] >= 3:
            wr = round(s["wins"] / s["signals"] * 100, 1)
            avg_pnl = round(s["total_pnl"] / s["signals"], 2)
            msg += f"{p}: {s['signals']} | {wr}% WR | {avg_pnl}%\n"
            if wr >= 65 and s["signals"] >= 10:
                msg += f" ⚡ PROMOTE {p}!\n"
    send_telegram(msg)

def send_hourly_pnl_update():
    global active_trades
    if not active_trades:
        send_telegram(f"⏰ <b>LIVE PnL UPDATE</b> - {get_ist_time()}\n\nNo active trades.\n\nScanning 150 coins...")
        return
    total_pnl = 0
    msg = f"⏰ <b>LIVE PnL UPDATE</b> - {get_ist_time()}\n\n"
    for coin, trade in active_trades.items():
        price = get_price(coin + "USDT")
        if not price: continue
        if trade["direction"] == "BUY":
            pnl = (price - trade["entry"]) / trade["entry"] * 100 * trade["leverage"]
        else:
            pnl = (trade["entry"] - price) / trade["entry"] * 100 * trade["leverage"]
        total_pnl += pnl
        eta_current = calculate_eta(price, trade["tp"], trade["atr"], trade["momentum"], trade["timeframe"])
        msg += f"<b>{coin}</b> {trade['direction']}\n\nPnL: {pnl:+.2f}%\n\nETA TP: {eta_current}\n\n"
    msg += f"<b>Total PnL: {total_pnl:+.2f}%</b>\n\nActive: {len(active_trades)} trades"
    send_telegram(msg)

# ================= HOURLY BATCH SENDER - YOUR RULE =================
def send_hourly_signal_batch():
    global hourly_queue, pending_signals
    if not hourly_queue:
        send_telegram(f"📡 <b>HOURLY SCAN COMPLETE</b> - {get_ist_time()}\n\nNo setups forming.\n\nNext batch in 1 hour.")
        return

    # Sort by setup_score, take top 3
    sorted_setups = sorted(hourly_queue.values(), key=lambda x: x["setup_score"], reverse=True)[:MAX_SIGNALS_PER_HOUR]

    send_telegram(f"🎯 <b>HOURLY SIGNAL BATCH</b> - {get_ist_time()}\n\n{len(sorted_setups)} setups ready:")

    for sig in sorted_setups:
        pending_signals[sig['coin']] = sig
        pattern_wr = round(pattern_stats[sig['pattern']]['wins']/max(1,pattern_stats[sig['pattern']]['signals'])*100,1)

        msg = f'''🔥 <b>SETUP {sig['coin']}</b> | Score: {sig['setup_score']}/100

📢 Direction: {sig['direction']}
📊 Leverage: {sig['leverage']}x

💰 Entry: {sig['entry']:.4f}
🎯 TP: {sig['tp']:.4f}
🛑 SL: {sig['sl']:.4f}

📈 Profit Target: {sig['profit_target']:.2f}%

🧠 Confidence: {sig['confidence']}%
📊 Setup Score: {sig['setup_score']}%

📌 Pattern: {sig['pattern']}
📌 Pattern Success: {pattern_wr}%

📉 RSI: {sig['rsi']:.2f}
📦 Volume Strength: {sig['vol_strength']:.2f}%

⚡ Momentum: {sig['momentum']:.1f}%
🚀 Velocity Score: {abs(sig['momentum']/10):.2f}

📍 Timeframe: {sig['timeframe']}
⏳ ETA: {sig['eta']}
⚠️ Risk: {sig['risk_percent']:.2f}%
⏰ Expires: {sig['expires_at']}

💧 Liquidity Zone: {sig['liquidity']:.4f}
📏 ATR: {sig['atr']:.4f}

⏰ Trade Time: {get_ist_time()}'''

        send_telegram(msg, sig['coin'], add_buttons=True)
        pattern_stats[sig['pattern']]["signals"] += 1
        time.sleep(1)

    hourly_queue.clear() # Clear for next hour

# ================= MAIN LOOP - PREDICTIVE 24/7 SCAN =================
def main():
    global last_report_time, last_hourly_batch_time, hourly_queue
    load_trade_history()
    send_telegram("🚀 <b>BOT ONLINE v2.18.0 PREDICTIVE</b>\n\n150 Coins | 5min Scans 24/7\n\nHourly Signal Batch | Dynamic Leverage\n\nTarget 20-25% | Max 3 signals/hour")

    threading.Thread(target=monitor_active_trades, daemon=True).start()
    threading.Thread(target=handle_updates, daemon=True).start()

    while True:
        try:
            scan_start = time.time()

            # SCAN ALL COINS EVERY 5 MINUTES - BUILD QUEUE
            for coin in COINS:
                setup = detect_setup(coin)
                if setup:
                    # Keep only best setup per coin
                    if coin not in hourly_queue or setup["setup_score"] > hourly_queue[coin]["setup_score"]:
                        hourly_queue = setup
                time.sleep(DELAY_BETWEEN_COINS)

            # CHECK IF TOP OF HOUR - SEND BATCH
            if is_top_of_hour() and time.time() - last_hourly_batch_time > 3500: # Prevent double send
                send_hourly_signal_batch()
                last_hourly_batch_time = time.time()

            # HOURLY PNL UPDATE
            if time.time() - last_hourly_time > 3600:
                send_hourly_pnl_update()
                last_hourly_time = time.time()

            # 6-HOUR PATTERN REPORT
            if time.time() - last_report_time > 21600:
                send_pattern_report()
                last_report_time = time.time()
                save_trade_history()

            scan_time = round(time.time() - scan_start, 1)
            next_hour = (get_ist_datetime() + timedelta(hours=1)).replace(minute=0, second=0)
            mins_to_batch = int((next_hour - get_ist_datetime()).total_seconds() / 60)
            send_telegram(f"✅ Scan done in {scan_time}s. {len(hourly_queue)} setups queued.\n\nNext batch in {mins_to_batch}min.")
            time.sleep(SCAN_INTERVAL)

        except Exception as e:
            send_telegram(f"❌ <b>CRASH</b>\n\n{str(e)}\n\nRestarting 60s...")
            print(f"Main error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
