import deriv_signal_bot as b


def gap(candles):
    cl = [x["close"] for x in candles]
    e10, e23 = b.ema(cl, 10), b.ema(cl, 23)
    return cl, [a - z for a, z in zip(e10, e23)]


def analyse():
    m30, m15, m5 = b.get_candles(1800), b.get_candles(900), b.get_candles(300)
    c30, g30 = gap(m30)
    c15, g15 = gap(m15)
    c5, g5 = gap(m5)
    e200 = b.ema(c30, 200)[-1]

    if c30[-1] > e200 and g30[-1] > 0 and g15[-1] > 0 and g5[-1] > 0:
        trend = "BUY"
        fresh = any(g5[-k] <= 0 for k in (2, 3, 4))
    elif c30[-1] < e200 and g30[-1] < 0 and g15[-1] < 0 and g5[-1] < 0:
        trend = "SELL"
        fresh = any(g5[-k] >= 0 for k in (2, 3, 4))
    else:
        return None
    if not fresh:
        return None

    entry = c5[-1]
    risk = 1.5 * b.atr(m15)
    sign = -1 if trend == "SELL" else 1
    return {
        "dir": trend, "entry": entry,
        "sl": entry - sign * risk,
        "tp1": entry + sign * risk * 1.5,
        "tp2": entry + sign * risk * 3,
        "risk": risk, "epoch": m5[-1]["epoch"],
    }
