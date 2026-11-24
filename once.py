import json, time, datetime
import requests
import deriv_signal_bot as b
import strategy
import pro

F = "last_sent.json"
MAX_PRO_PER_DAY = 8
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


def fmt_pro(s, live, n):
    buy = s["dir"] == "BUY"
    yn = lambda v: "✅" if v else "❌"
    p = s["parts"]
    lo, hi = s["zone"]
    inval = "below" if buy else "above"
    return (
        "🎯 SMC PRO SIGNAL 🎯\n\n"
        f"{'🟢' if buy else '🔴'} Direction: {s['dir']}\n"
        f"📊 Symbol: {b.SYMBOL} (M15 | Intraday)\n\n"
        f"💰 Entry: {s['entry']:.2f}\n"
        f"🛑 Stop Loss: {s['sl']:.2f} (Structural)\n\n"
        f"🔹 TP1: {s['tp1']:.2f} (Close 65%)\n"
        f"🔹 TP2: {s['tp2']:.2f} (Close 20%)\n"
        f"🚀 TP3: {s['tp3']:.2f} (Runner 15%)\n\n"
        "⚖️ Risk:Reward: 1:2.5\n"
        f"🎚️ Setup score: {s['score']}/100\n\n"
        "📝 Why this trade:\n"
        f"• Score: {s['score']}/100 → Sweep {p['Sweep']} | CHoCH {p['CHoCH']} | BOS {p['BOS']} | FVG {p['FVG']} | OB {p['OB']}\n"
        f"• Liquidity sweep: {yn(s['sweep'])}\n"
        f"• CHoCH: {yn(s['choch'])} | BOS: {yn(s['bos'])}\n"
        f"• Entry zone: {s['zone_name']} {lo:.2f} - {hi:.2f}\n"
        f"• Trigger: {'bullish' if buy else 'bearish'} candle reacted from the zone and closed {'above' if buy else 'below'} it\n"
        f"• Invalidated if a candle closes {inval} {s['sl']:.2f}\n"
        f"• Targets: 1.0R / 1.5R / 2.5R | opposite liquidity at {s['liq']:.2f}\n"
        f"• Context: H1 trend {s['bias']}\n\n"
        "⏳ Execute manually within 10 minutes.\n\n"
        "⚠️ Educational purpose only. Not financial advice.\n\n"
        f"📅 Signal {n} of max {MAX_PRO_PER_DAY} today ({b.SYMBOL})"
    )


now = datetime.datetime.now(datetime.timezone.utc)
today = now.strftime("%Y-%m-%d")
if now.hour >= 6 and state.get("alive") != today:
    tg("✅ Bot is alive and checking " + b.SYMBOL + " about every 5 minutes.\n"
       "Strategies: " + ", ".join(list(strategy.STRATEGIES) + ["SMC PRO"]))
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

try:
    s = pro.analyse()
    if not s:
        print("SMC PRO : no signal")
    else:
        key = "PRO|" + s["dir"]
        cnt = state.get("pro_count", {})
        if cnt.get("date") != today:
            cnt = {"date": today, "n": 0}
        if time.time() - state.get(key, 0) < b.COOLDOWN:
            print("SMC PRO : cooldown")
        elif cnt["n"] >= MAX_PRO_PER_DAY:
            print("SMC PRO : daily limit reached")
        else:
            if live is None:
                live = b.live_price()
            if abs(live - s["entry"]) / s["risk"] < 0.3:
                cnt["n"] += 1
                tg(fmt_pro(s, live, cnt["n"]))
                state[key] = time.time()
                state["pro_count"] = cnt
                print("SMC PRO : SENT", s["dir"])
            else:
                print("SMC PRO : price moved away")
except Exception as e:
    print("SMC PRO error:", e)

json.dump(state, open(F, "w"))
