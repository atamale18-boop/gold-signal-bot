import deriv_signal_bot as b


def vwap_series(candles):
    last = candles[-1]["epoch"]
    day_start = last - last % 86400
    total, n, out = 0.0, 0, []
    for x in candles:
        if x["epoch"] < day_start:
            out.append(None)
            continue
        n += 1
        total += (x["high"] + x["low"] + x["close"]) / 3
        out.append(total / n)
    return out


def analyse():
    m15, m5 = b.get_candles(900), b.get_candles(300)
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
        trend = "BUY"
        fresh = any(a5[-k] <= z5[-k] for k in (2, 3, 4))
    elif a15[-1] < z15[-1] and c15[-1] < v15[-1] and a5[-1] < z5[-1] and c5[-1] < v5[-1]:
        trend = "SELL"
        fresh = any(a5[-k] >= z5[-k] for k in (2, 3, 4))
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
