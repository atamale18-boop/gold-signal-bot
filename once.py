import json, time, datetime
import requests
import deriv_signal_bot as b
import strategy

F = "last_sent.json"
try:
    state = json.load(open(F))
except Exception:
    state = {}


def tg(text):
    requests.post(f"https://api.telegram.org/bot{b.TG_TOKEN}/sendMessage",
                  json={"chat_id": b.TG_CHAT_ID, "text": text}, timeout=15)


def fmt(name, s, live):
    dist = abs(live - s["entry"]) / s["risk"]
    return (
        "🚀 DERIV SIGNAL ASSISTANT\n🆕 NEW SIGNAL ALERT\n━━━━━━━━━━━━━━━━\n"
        f"📊 Market: {b.SYMBOL}\n🧠 Strategy: {name}\n"
        f"📈 Direction: {s['dir']}\n🎯 Entry: {s['entry']:.2f}\n"
        f"🛑 Stop Loss: {s['sl']:.2f}\n"
        f"💰 Take Profit 1: {s['tp1']:.2f}\n💰 Take Profit 2: {s['tp2']:.2f}\n"
        f"📍 Live price: {live:.2f}\n⏱ Signal age: {int(time.time() - s['epoch'])}s\n"
        f"✅ Entry distance: {dist:.3f}R\n━━━━━━━━━━━━━━━━\n"
        "⚠️ Signal only. Verify conditions before trading; nothing is executed automatically."
    )


now = datetime.datetime.now(datetime.timezone.utc)
today = now.strftime("%Y-%m-%d")
if now.hour >= 6 and state.get("alive") != today:
    tg("✅ Bot is alive and checking " + b.SYMBOL + " about every 5 minutes.\n"
       "Strategies: " + ", ".join(strategy.STRATEGIES))
    state["alive"] = today

live = None
for name, fn in strategy.STRATEGIES.items():
    try:
        s = fn()
    except Exception as e:
        print(name, "error:", e)
        continue
    if not s:
        print(name, ": no signal")
        continue
    key = name + "|" + s["dir"]
    if time.time() - state.get(key, 0) < b.COOLDOWN:
        print(name, ": cooldown")
        continue
    if live is None:
        live = b.live_price()
    if abs(live - s["entry"]) / s["risk"] < 0.3:
        tg(fmt(name, s, live))
        state[key] = time.time()
        print(name, ": SENT", s["dir"])
    else:
        print(name, ": price moved away")

json.dump(state, open(F, "w"))
