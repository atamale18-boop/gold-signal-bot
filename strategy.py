import deriv_signal_bot as b

_cache = {}


def candles(g):
    if g not in _cache:
        _cache[g] = b.get_candles(g)
    return _cache[g]


def build(trend, entry, risk, m5, r1=1.5, r2=3.0):
    s = -1 if trend == "SELL" else 1
    return {
        "dir": trend, "entry": entry,
        "sl": entry - s * risk,
        "tp1": entry + s * risk * r1,
        "tp2": entry + s * risk * r2,
        "risk": risk, "epoch": m5[-1]["epoch"],
    }


def vwap_series(c):
    last = c[-1]["epoch"]
    day = last - last % 86400
    tot, n, out = 0.0, 0, []
    for x in c:
        if x["epoch"] < day:
            out.append(None)
            continue
        n += 1
        tot += (x["high"] + x["low"] + x["close"]) / 3
        out.append(tot / n)
    return out


def ema_cross():
    m5 = candles(300)
    cl = [x["close"] for x in m5]
    e10, e23 = b.ema(cl, 10), b.ema(cl, 23)
    up = e10[-1] > e23[-1] and any(e10[-k] <= e23[-k] for k in (2, 3))
    dn = e10[-1] < e23[-1] and any(e10[-k] >= e23[-k] for k in (2, 3))
    if not (up or dn):
        return None
    return build("BUY" if up else "SELL", cl[-1], 1.5 * b.atr(m5), m5)


def vwap_strategy():
    m15, m5 = candles(900), candles(300)
    c15 = [x["close"] for x in m15]
    c5 = [x["close"] for x in m5]
    a15, z15 = b.ema(c15, 10), b.ema(c15, 23)
    a5, z5 = b.ema(c5, 10), b.ema(c5, 23)
    v15, v5 = vwap_series(m15), vwap_series(m5)
    if v15[-1] is None or v5[-1] is None:
        return None
    if sum(1 for v in v5 if v is not None) < 12:
        return None
    if a15[-1] > z15[-1] and c15[-1] > v15[-1] and a5[-1] > z5[-1] and c5[-1] > v5[-1]:
        t = "BUY"
        fresh = any(a5[-k] <= z5[-k] for k in (2, 3, 4))
    elif a15[-1] < z15[-1] and c15[-1] < v15[-1] and a5[-1] < z5[-1] and c5[-1] < v5[-1]:
        t = "SELL"
        fresh = any(a5[-k] >= z5[-k] for k in (2, 3, 4))
    else:
        return None
    if not fresh:
        return None
    return build(t, c5[-1], 1.5 * b.atr(m15), m5)


def scalp():
    m15, m5 = candles(900), candles(300)
    c15 = [x["close"] for x in m15]
    c5 = [x["close"] for x in m5]
    a15, z15 = b.ema(c15, 10), b.ema(c15, 23)
    a5, z5 = b.ema(c5, 10), b.ema(c5, 23)
    v15 = vwap_series(m15)
    if v15[-1] is None:
        return None
    r_now, r_prev = b.rsi(c5, 7), b.rsi(c5[:-1], 7)
    if a15[-1] > z15[-1] and c15[-1] > v15[-1]:
        pull = any(m5[-k]["low"] <= z5[-k] for k in (2, 3, 4))
        if pull and c5[-1] > a5[-1] and r_now > r_prev and r_now < 70:
            return build("BUY", c5[-1], b.atr(m5), m5, 1.0, 2.0)
    if a15[-1] < z15[-1] and c15[-1] < v15[-1]:
        pull = any(m5[-k]["high"] >= z5[-k] for k in (2, 3, 4))
        if pull and c5[-1] < a5[-1] and r_now < r_prev and r_now > 30:
            return build("SELL", c5[-1], b.atr(m5), m5, 1.0, 2.0)
    return None


STRATEGIES = {
    "EMA 10/23 cross (M5)": ema_cross,
    "VWAP + EMA 10/23": vwap_strategy,
    "SCALP pullback": scalp,
}
