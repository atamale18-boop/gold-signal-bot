"""
Deriv MTF Signal Bot -> Telegram
Signals only. Does NOT place trades.

Install:  pip install websocket-client requests
Env vars: TG_TOKEN, TG_CHAT_ID   (optional: SYMBOL, CHECK_SECONDS)
Run:      python deriv_signal_bot.py
"""
import os, time, json
import requests
from websocket import create_connection

TG_TOKEN = os.environ["TG_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]
SYMBOL = os.getenv("SYMBOL", "frxXAUUSD")
CHECK_SECONDS = int(os.getenv("CHECK_SECONDS", "60"))
COOLDOWN = 30 * 60          # min seconds between signals in same direction
WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"

last_sent = {"BUY": 0, "SELL": 0}


# ---------- data ----------
def get_candles(granularity, count=300):
    ws = create_connection(WS_URL, timeout=20)
    try:
        ws.send(json.dumps({
            "ticks_history": SYMBOL, "adjust_start_time": 1, "count": count,
            "end": "latest", "style": "candles", "granularity": granularity}))
        data = json.loads(ws.recv())
    finally:
        ws.close()
    if "candles" not in data:
        raise RuntimeError(data.get("error", data))
    return data["candles"][:-1]  # drop the still-forming candle


def live_price():
    ws = create_connection(WS_URL, timeout=20)
    try:
        ws.send(json.dumps({"ticks": SYMBOL}))
        return float(json.loads(ws.recv())["tick"]["quote"])
    finally:
        ws.close()


# ---------- indicators ----------
def ema(vals, n):
    k, out = 2 / (n + 1), [vals[0]]
    for v in vals[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(closes, n=14):
    gains = losses = 0.0
    for i in range(1, n + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0); losses += max(-d, 0)
    ag, al = gains / n, losses / n
    for i in range(n + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        ag = (ag * (n - 1) + max(d, 0)) / n
        al = (al * (n - 1) + max(-d, 0)) / n
    return 100 if al == 0 else 100 - 100 / (1 + ag / al)


def atr(c, n=14):
    trs = [max(x["high"] - x["low"],
               abs(x["high"] - c[i]["close"]),
               abs(x["low"] - c[i]["close"])) for i, x in enumerate(c[1:])]
    a = sum(trs[:n]) / n
    for t in trs[n:]:
        a = (a * (n - 1) + t) / n
    return a


# ---------- strategy ----------
def analyse():
    m30, m15, m5 = get_candles(1800), get_candles(900), get_candles(300)

    # M30 confirmation: trend filter
    c30 = [x["close"] for x in m30]
    e50, e200 = ema(c30, 50)[-1], ema(c30, 200)[-1]
    trend = "BUY" if c30[-1] > e50 > e200 else "SELL" if c30[-1] < e50 < e200 else None
    if not trend:
        return None

    # M15 setup: pullback to EMA20 then close back in trend direction
    c15 = [x["close"] for x in m15]
    e20 = ema(c15, 20)
    recent = m15[-5:]
    if trend == "SELL":
        setup = any(x["high"] >= e20[-5 + i] for i, x in enumerate(recent)) and c15[-1] < e20[-1]
    else:
        setup = any(x["low"] <= e20[-5 + i] for i, x in enumerate(recent)) and c15[-1] > e20[-1]
    if not setup:
        return None

    # M5 entry: break of last 6 candles' structure + RSI momentum
    c5 = [x["close"] for x in m5]
    prev = m5[-7:-1]
    r = rsi(c5)
    if trend == "SELL" and not (c5[-1] < min(x["low"] for x in prev) and r < 50):
        return None
    if trend == "BUY" and not (c5[-1] > max(x["high"] for x in prev) and r > 50):
        return None

    entry = c5[-1]
    risk = 1.5 * atr(m15)
    sign = -1 if trend == "SELL" else 1
    return {
        "dir": trend, "entry": entry,
        "sl": entry - sign * risk,
        "tp1": entry + sign * risk * 1.5,
        "tp2": entry + sign * risk * 3,
        "risk": risk, "epoch": m5[-1]["epoch"],
    }


# ---------- telegram ----------
def send(sig, live):
    age = int(time.time() - sig["epoch"])
    dist_r = abs(live - sig["entry"]) / sig["risk"]
    msg = (
        "🚀 DERIV SIGNAL ASSISTANT — MTF\n🆕 NEW SIGNAL ALERT\n━━━━━━━━━━━━━━━━\n"
        f"📊 Market: {SYMBOL} | Short-term\n"
        "⏱ Timeframes: M5 entry / M15 bias + VWAP\n"
        f"📈 Direction: {sig['dir']}\n"
        f"🎯 Entry: {sig['entry']:.2f}\n"
        f"🛑 Stop Loss: {sig['sl']:.2f}\n"
        f"💰 Take Profit 1: {sig['tp1']:.2f}\n"
        f"💰 Take Profit 2: {sig['tp2']:.2f}\n"
        f"📍 Live price: {live:.2f}\n"
        f"⏱ Signal age: {age}s\n"
        f"✅ Entry distance: {dist_r:.3f}R\n"
        f"🔖 Signal: {SYMBOL}-{sig['dir']}-{sig['epoch']}\n━━━━━━━━━━━━━━━━\n"
        "⚠️ Signal only. Verify conditions before trading; nothing is executed automatically."
    )
    requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                  json={"chat_id": TG_CHAT_ID, "text": msg}, timeout=15)


def main():
    print("Bot started")
    while True:
        try:
            sig = analyse()
            if sig and time.time() - last_sent[sig["dir"]] > COOLDOWN:
                live = live_price()
                if abs(live - sig["entry"]) / sig["risk"] < 0.3:  # still near entry
                    send(sig, live)
                    last_sent[sig["dir"]] = time.time()
                    print("Sent", sig["dir"], sig["entry"])
        except Exception as e:
            print("Error:", e)
        time.sleep(CHECK_SECONDS)


if __name__ == "__main__":
    main()