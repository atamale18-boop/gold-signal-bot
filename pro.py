import deriv_signal_bot as b
import strategy

MIN_SCORE = 60


def events_of(c, sw=3):
    H = [x["high"] for x in c]
    L = [x["low"] for x in c]
    C = [x["close"] for x in c]
    hi = lo = None
    hib = lob = True
    trend = 0
    ev = []
    for t in range(2 * sw, len(c)):
        p = t - sw
        if H[p] == max(H[p - sw:p + sw + 1]):
            hi, hib = H[p], False
        if L[p] == min(L[p - sw:p + sw + 1]):
            lo, lob = L[p], False
        if hi is not None and not hib and C[t] > hi:
            ev.append((t, "BUY", "CHOCH" if trend == -1 else "BOS"))
            hib, trend = True, 1
        if lo is not None and not lob and C[t] < lo:
            ev.append((t, "SELL", "CHOCH" if trend == 1 else "BOS"))
            lob, trend = True, -1
    return ev


def swept(c, d, n=15):
    for i in range(max(10, len(c) - n), len(c)):
        prev = c[i - 10:i]
        if d == "BUY":
            lvl = min(x["low"] for x in prev)
            if c[i]["low"] < lvl and c[i]["close"] > lvl:
                return True
        else:
            lvl = max(x["high"] for x in prev)
            if c[i]["high"] > lvl and c[i]["close"] < lvl:
                return True
    return False


def find_fvg(c, d, n=25):
    for i in range(len(c) - 1, max(len(c) - n, 2), -1):
        a, k = c[i - 2], c[i]
        if d == "BUY" and k["low"] > a["high"]:
            lo, hi = a["high"], k["low"]
            if all(x["close"] >= lo for x in c[i + 1:]):
                return (lo, hi)
        if d == "SELL" and k["high"] < a["low"]:
            lo, hi = k["high"], a["low"]
            if all(x["close"] <= hi for x in c[i + 1:]):
                return (lo, hi)
    return None


def find_ob(c, d, t):
    for i in range(t - 1, max(t - 12, 0), -1):
        x = c[i]
        if d == "BUY" and x["close"] < x["open"]:
            return (x["low"], x["high"])
        if d == "SELL" and x["close"] > x["open"]:
            return (x["low"], x["high"])
    return None


def h1_bias():
    h1 = strategy.candles(3600)
    cl = [x["close"] for x in h1]
    e20, e50 = b.ema(cl, 20)[-1], b.ema(cl, 50)[-1]
    a = b.atr(h1)
    if e20 - e50 > 0.1 * a:
        return "bullish"
    if e50 - e20 > 0.1 * a:
        return "bearish"
    return "neutral"


def analyse():
    m15, m5 = strategy.candles(900), strategy.candles(300)
    n = len(m15)
    recent = [e for e in events_of(m15) if n - 1 - e[0] <= 40]
    if not recent:
        return None
    d = recent[-1][1]
    same = [e for e in recent if e[1] == d]
    choch = any(e[2] == "CHOCH" for e in same)
    bos = any(e[2] == "BOS" for e in same)
    bias = h1_bias()
    if (d == "BUY" and bias == "bearish") or (d == "SELL" and bias == "bullish"):
        return None
    sw = swept(m15, d)
    z_fvg = find_fvg(m15, d)
    z_ob = find_ob(m15, d, same[-1][0])
    zone = z_fvg or z_ob
    if not zone:
        return None
    zlo, zhi = zone
    last = m15[-1]
    if d == "BUY":
        trig = last["low"] <= zhi and last["close"] > zhi and last["close"] > last["open"]
    else:
        trig = last["high"] >= zlo and last["close"] < zlo and last["close"] < last["open"]
    if not trig:
        return None
    parts = {"Sweep": 20 * sw, "CHoCH": 20 * choch, "BOS": 20 * bos,
             "FVG": 20 * (z_fvg is not None), "OB": 20 * (z_ob is not None)}
    score = sum(parts.values())
    if score < MIN_SCORE:
        return None
    a = b.atr(m15)
    entry = m5[-1]["close"]
    s = 1 if d == "BUY" else -1
    sl = zlo - 0.2 * a if d == "BUY" else zhi + 0.2 * a
    risk = (entry - sl) if d == "BUY" else (sl - entry)
    if risk <= 0 or risk < 0.5 * a or risk > 3 * a:
        return None
    liq = max(x["high"] for x in m15[-50:]) if d == "BUY" else min(x["low"] for x in m15[-50:])
    return {
        "dir": d, "entry": entry, "sl": sl, "risk": risk,
        "tp1": entry + s * risk, "tp2": entry + s * risk * 1.5, "tp3": entry + s * risk * 2.5,
        "epoch": m5[-1]["epoch"], "score": score, "parts": parts,
        "sweep": sw, "choch": choch, "bos": bos,
        "zone_name": "FVG" if z_fvg else "OB", "zone": zone,
        "bias": bias, "liq": liq,
    }
