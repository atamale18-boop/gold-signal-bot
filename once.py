import json, time, datetime
import requests
import deriv_signal_bot as b
import strategy
import pro

SYMBOLS = ["frxXAUUSD", "frxEURUSD", "frxGBPUSD", "frxUSDJPY",
           "frxEURJPY", "frxAUDUSD", "R_75", "R_100"]
F = "last_sent.json"
MAX_PRO_PER_DAY = 8
try:
    state = json.load(open(F))
except Exception:
    state = {}


def tg(text):
    requests.post(f"https://api.telegram.org/bot{b.TG_TOKEN}/sendMessage",
                  json={"chat_id": b.TG_CHAT_ID, "text": text}, timeout=15)


def decimals(x):
    return 2 if x >= 1000 else 3 if x >= 20 else 5


def fmt(name, s, live):
    d = decimals(s["entry"])
    f = lambda v: f"{v:.{d}f}"
    dist = abs(live - s["entry"]) / s["risk"]
    return (
        "🚀 DERIV SIGNAL ASSISTANT\n🆕 NEW SIGNAL ALERT\n━━━━━━━━━━━━━━━━\n"
        f"📊 Market: {b.SYMBOL}\n🧠 Strategy: {name}\n"
        f"📈 Direction: {s['dir']}\n🎯 Entry: {f(s['entry'])}\n"
        f"🛑 Stop Loss: {f(s['sl'])}\n"
        f"💰 Take Profit 1: {f(s['tp1'])}\n💰 Take Profit 2: {f(s['tp2'])}\n"
        f"📍 Live price: {f(live)}\n⏱ Signal age: {int(time.time() - s['epoch'])}s\n"
        f"✅ Entry distance: {dist:.3f}R\n━━━━━━━━━━━━━━━━\n"
        "⚠️ Signal only. Verify conditions before trading; nothing is executed automatically."
    )


def fmt_pro(s, live, n):
    d = decimals(s["entry"])
    f = lambda v: f"{v:.{d}f}"
    buy = s["dir"] == "BUY"
    yn = lambda v: "✅" if v else "❌"
    p = s["parts"]
    lo, hi = s["zone"]
    inval = "below" if buy else "above"
    return (
        "🎯 SMC PRO SIGNAL 🎯\n\n"
        f"{'🟢' if buy else '🔴'} Direction: {s['dir']}\n"
        f"📊 Symbol: {b.SYMBOL} (M15 | Intraday)\n\n"
        f"💰 Entry: {f(s['entry'])}\n"
        f"🛑 Stop Loss: {f(s['sl'])} (Structural)\n\n"
        f"🔹 TP1: {f(s['tp1'])} (Close 65%)\n"
        f"🔹 TP2: {f(s['tp2'])} (Close 20%)\n"
        f"🚀 TP3: {f(s['tp3'])} (Runner 15%)\n\n"
        "⚖️ Risk:Reward: 1:2.5\n"
        f"🎚️ Setup score: {s['score']}/100\n\n"
        "📝 Why this trade:\n"
        f"• Score: {s['score']}/100 → Sweep {p['Sweep']} | CHoCH {p['CHoCH']} | BOS {p['BOS']} | FVG {p['FVG']} | OB {p['OB']}\n"
        f"• Liquidity sweep: {yn(s['sweep'])}\n"
        f"• CHoCH: {yn(s['choch'])} | BOS: {yn(s['bos'])}\n"
        f"• Entry zone: {s['zone_name']} {f(lo)} - {f(hi)}\n"
        f"• Trigger: {'bullish' if buy else 'bearish'} candle reacted from the zone and closed {'above' if buy else 'below'} it\n"
        f"• Invalidated if a candle closes {inval} {f(s['sl'])}\n"
        f"• Targets: 1.0R / 1.5R / 2.5R | opposite liquidity at {f(s['liq'])}\n"
        f"• Context: H1 trend {s['bias']}\n\n"
        "⏳ Execute manually within 10 minutes.\n\n"
        "⚠️ Educational purpose only. Not financial advice.\n\n"
        f"📅 Signal {n} of max {MAX_PRO_PER_DAY} today ({b.SYMBOL})"
    )


def run_symbol(sym):
    b.SYMBOL = sym
    strategy._cache.clear()
    last_bar = strategy.candles(300)[-1]["epoch"]
    if time.time() - last_bar > 15 * 60:
        print(sym, ": market closed / stale data")
        return
    live = None
    for name, fn in strategy.STRATEGIES.items():
        try:
            s = fn()
        except Exception as e:
            print(sym, name, "error:", e)
            continue
        if not s:
            print(sym, name, ": no signal")
            continue
        key = f"{sym}|{name}|{s['dir']}"
        if time.time() - state.get(key, 0) < b.COOLDOWN:
            print(sym, name, ": cooldown")
            continue
        if live is None:
            live = b.live_price()
        if abs(live - s["entry"]) / s["risk"] < 0.3:
            tg(fmt(name, s, live))
            state[key] = time.time()
            print(sym, name, ": SENT", s["dir"])
        else:
            print(sym, name, ": price moved away")
    try:
        s = pro.analyse()
        if not s:
            print(sym, "SMC PRO : no signal")
            return
        key = f"{sym}|PRO|{s['dir']}"
        ck = f"pro_count|{sym}"
        cnt = state.get(ck, {})
        if cnt.get("date") != today:
            cnt = {"date": today, "n": 0}
        if time.time() - state.get(key, 0) < b.COOLDOWN:
            print(sym, "SMC PRO : cooldown")
        elif cnt["n"] >= MAX_PRO_PER_DAY:
            print(sym, "SMC PRO : daily limit reached")
        else:
            if live is None:
                live = b.live_price()
            if abs(live - s["entry"]) / s["risk"] < 0.3:
                cnt["n"] += 1
                tg(fmt_pro(s, live, cnt["n"]))
                state[key] = time.time()
                state[ck] = cnt
                print(sym, "SMC PRO : SENT", s["dir"])
            else:
                print(sym, "SMC PRO : price moved away")
    except Exception as e:
        print(sym, "SMC PRO error:", e)


now = datetime.datetime.now(datetime.timezone.utc)
today = now.strftime("%Y-%m-%d")
if now.hour >= 6 and state.get("alive") != today:
    tg("✅ Bot is alive, checking every ~5 minutes.\nMarkets: " + ", ".join(SYMBOLS) +
       "\nStrategies: " + ", ".join(list(strategy.STRATEGIES) + ["SMC PRO"]))
    state["alive"] = today

for sym in SYMBOLS:
    try:
        run_symbol(sym)
    except Exception as e:
        print(sym, "error:", e)

json.dump(state, open(F, "w"))
