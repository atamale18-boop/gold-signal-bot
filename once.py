import json, time
import deriv_signal_bot as b
import strategy

F = "last_sent.json"
try:
    last = json.load(open(F))
except Exception:
    last = {}

sig = strategy.analyse()
if sig and time.time() - last.get(sig["dir"], 0) > b.COOLDOWN:
    live = b.live_price()
    if abs(live - sig["entry"]) / sig["risk"] < 0.3:
        b.send(sig, live)
        last[sig["dir"]] = time.time()
        json.dump(last, open(F, "w"))
        print("Sent", sig["dir"])
    else:
        print("Price moved away")
else:
    print("No signal")
