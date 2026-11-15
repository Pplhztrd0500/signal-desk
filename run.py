"""signal-desk: find out which strategies survive an honest test. It never places orders.

  python run.py fetch --source kraken --pair ETHUSD --interval 1440 --name eth_daily
  python run.py scan  --dataset eth_daily
  python run.py test  --dataset eth_daily --unlock-test     # once, at the very end
  python run.py signal --dataset eth_daily                  # today's call, you execute by hand
  python run.py lessons
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from desk import backtest, data, gate, lessons, strategies

RESULTS = os.path.join(data.ROOT, "results")
DEFAULT_FEE = 0.005  # per entry and per exit. Set it to your venue's real rate.


def _meta_path(name: str) -> str:
    return os.path.join(data.DATA_DIR, f"{name}.json")


def _fetch_with(meta: dict) -> list[data.Bar]:
    if meta["source"] == "kraken":
        return data.fetch_kraken(meta["pair"], meta["interval"])
    return data.fetch_geckoterminal(meta["network"], meta["pool"], meta["timeframe"])


def _date(ts: int) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts))


def cmd_fetch(a) -> None:
    if a.source == "kraken":
        meta = {"source": "kraken", "pair": a.pair, "interval": a.interval}
        name = a.name or f"kraken_{a.pair}_{a.interval}"
    else:
        if not a.pool:
            sys.exit("--pool is required for --source gecko (the pool address from geckoterminal.com)")
        meta = {"source": "gecko", "network": a.network, "pool": a.pool, "timeframe": a.timeframe}
        name = a.name or f"gecko_{a.network}_{a.pool[:6]}_{a.timeframe}"
    if os.path.exists(data.dataset_path(name)) and not a.refresh:
        sys.exit(f"Dataset '{name}' already exists. It is frozen on purpose: refetching shifts the "
                 f"train/validation/test windows. Use --refresh only to start a new study.")
    bars = _fetch_with(meta)
    path = data.save(name, bars)
    with open(_meta_path(name), "w") as f:
        json.dump(meta, f)
    v, t = data.split_points(len(bars))
    print(f"Saved {len(bars)} bars to {path}")
    print(f"  train      {_date(bars[0].ts)} -> {_date(bars[v - 1].ts)}  ({v} bars)")
    print(f"  validation {_date(bars[v].ts)} -> {_date(bars[t - 1].ts)}  ({t - v} bars)")
    print(f"  test       {_date(bars[t].ts)} -> {_date(bars[-1].ts)}  ({len(bars) - t} bars, LOCKED)")


def cmd_scan(a) -> None:
    bars = data.load(a.dataset)
    v, t = data.split_points(len(bars))
    visible = bars[:t]  # the scan cannot see the test window at all
    past = lessons.summary()
    print("Lessons so far: " + " | ".join(past))
    print(f"\nScanning {len(strategies.GRID)} candidates on '{a.dataset}', fee {a.fee:.2%} per side")
    print(f"train {v} bars, validation {t - v} bars, test {len(bars) - t} bars locked\n")

    rows = []
    for family, params in strategies.GRID:
        cid = strategies.candidate_id(family, params)
        sig = strategies.signal_for(family, params, visible)
        tr = backtest.run(visible, sig, 1, v, a.fee)
        va = backtest.run(visible, sig, v, t, a.fee)
        va_late = backtest.run(visible, backtest.delayed(sig), v, t, a.fee)
        verdict = gate.check(tr, va, va_late)
        if not verdict.passed:
            lessons.record(a.dataset, cid, verdict.failed)
        rows.append({"candidate": cid, "family": family, "params": params,
                     "train": tr.summary(), "val": va.summary(), "val_late": va_late.summary(),
                     "passed": verdict.passed, "failed": verdict.failed})

    bh = rows[0]["val"]["bh_ret"]
    print(f"{'candidate':50} {'train':>8} {'valid':>8} {'1 late':>8} {'maxDD':>7} {'trades':>6}  verdict")
    for r in rows:
        print(f"{r['candidate']:50} {r['train']['ret']:>+8.1%} {r['val']['ret']:>+8.1%} "
              f"{r['val_late']['ret']:>+8.1%} {r['val']['max_dd']:>7.1%} "
              f"{r['train']['trades'] + r['val']['trades']:>6}  {'PASS' if r['passed'] else 'BLOCK'}")
    passed = [r for r in rows if r["passed"]]
    print(f"\nbuy & hold on validation: {bh:+.1%}")
    print(f"{len(passed)} of {len(rows)} passed the gate.")
    for r in rows:
        if not r["passed"]:
            print(f"  BLOCK {r['candidate']}: {r['failed'][0]}" +
                  (f" (+{len(r['failed']) - 1} more)" if len(r["failed"]) > 1 else ""))
    print(f"\nReminder: {len(rows)} candidates were tried. With that many tries, one can pass by luck.")
    print("A PASS is a hypothesis for the locked test window, not a green light.")

    os.makedirs(RESULTS, exist_ok=True)
    out = {"dataset": a.dataset, "fee": a.fee, "time": int(time.time()),
           "windows": {"val_start": v, "test_start": t, "n": len(bars)}, "rows": rows}
    with open(os.path.join(RESULTS, f"{a.dataset}_scan.json"), "w") as f:
        json.dump(out, f, indent=1)
    _write_report(a.dataset, bars, out)
    print(f"\nReport: results/{a.dataset}_report.md")


def _write_report(name: str, bars: list[data.Bar], scan: dict) -> None:
    v, t = scan["windows"]["val_start"], scan["windows"]["test_start"]
    lines = [f"# Scan: {name}", "",
             f"- train: {_date(bars[0].ts)} to {_date(bars[v - 1].ts)} ({v} bars)",
             f"- validation: {_date(bars[v].ts)} to {_date(bars[t - 1].ts)} ({t - v} bars)",
             f"- test: {len(bars) - t} bars, locked",
             f"- fee: {scan['fee']:.2%} per entry and per exit",
             f"- buy & hold on validation: {scan['rows'][0]['val']['bh_ret']:+.1%}", "",
             "| candidate | train | validation | 1 bar late | max DD | trades | verdict | reason |",
             "|---|---:|---:|---:|---:|---:|---|---|"]
    for r in scan["rows"]:
        lines.append(f"| `{r['candidate']}` | {r['train']['ret']:+.1%} | {r['val']['ret']:+.1%} | "
                     f"{r['val_late']['ret']:+.1%} | {r['val']['max_dd']:.1%} | "
                     f"{r['train']['trades'] + r['val']['trades']} | "
                     f"{'PASS' if r['passed'] else 'BLOCK'} | {'; '.join(r['failed'])} |")
    with open(os.path.join(RESULTS, f"{name}_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _load_scan(name: str) -> dict:
    path = os.path.join(RESULTS, f"{name}_scan.json")
    if not os.path.exists(path):
        sys.exit(f"No scan for '{name}'. Run: python run.py scan --dataset {name}")
    with open(path) as f:
        return json.load(f)


def cmd_test(a) -> None:
    if not a.unlock_test:
        sys.exit("The test window is locked. Add --unlock-test when you are done changing strategies.\n"
                 "You get one clean look. After that, every change you make is tuned to the test.")
    scan = _load_scan(a.dataset)
    log_path = os.path.join(RESULTS, "test_log.jsonl")
    history = []
    if os.path.exists(log_path):
        with open(log_path) as f:
            history = [json.loads(l) for l in f if l.strip()]
    if any(h["dataset"] == a.dataset for h in history) and not a.again:
        sys.exit(f"The test window of '{a.dataset}' was already opened. A second look is not out-of-sample.\n"
                 f"Fetch a new dataset (later dates or another asset) for a clean test, or pass --again.")
    passed = [r for r in scan["rows"] if r["passed"]]
    bars = data.load(a.dataset)
    t = scan["windows"]["test_start"]
    print(f"Opening the test window of '{a.dataset}': {_date(bars[t].ts)} -> {_date(bars[-1].ts)}")
    if not passed:
        print("No candidate passed the gate, so there is nothing to test. The answer is: stay flat.")
    results = []
    for r in passed:
        sig = strategies.signal_for(r["family"], r["params"], bars)
        res = backtest.run(bars, sig, t, len(bars), scan["fee"])
        ok = res.ret > 0 and res.ret > res.bh_ret
        results.append({"candidate": r["candidate"], **res.summary(), "held_up": ok})
        print(f"  {r['candidate']:50} test {res.ret:+.1%} vs buy & hold {res.bh_ret:+.1%}, "
              f"max DD {res.max_dd:.1%}, {res.trades} trades -> {'HELD UP' if ok else 'FAILED'}")
    os.makedirs(RESULTS, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps({"dataset": a.dataset, "time": int(time.time()),
                            "repeat": bool(history and a.again), "results": results}) + "\n")


def cmd_signal(a) -> None:
    scan = _load_scan(a.dataset)
    with open(_meta_path(a.dataset)) as f:
        meta = json.load(f)
    bars = _fetch_with(meta)  # fresh bars, the frozen study dataset is left alone
    last = bars[-1]
    passed = [r for r in scan["rows"] if r["passed"]]
    print(f"Latest closed bar: {_date(last.ts)} UTC, close {last.close:g}")
    if not passed:
        print("No candidate passed the gate. Signal: FLAT. Doing nothing is a position too.")
        return
    for r in passed:
        sig = strategies.signal_for(r["family"], r["params"], bars)
        now, before = sig[-1], sig[-2]
        action = {(0, 1): "BUY", (1, 0): "SELL", (1, 1): "HOLD LONG", (0, 0): "STAY FLAT"}[(before, now)]
        print(f"  {r['candidate']:50} {action}")
    print("\nThis tool never places orders. If you act on it, you place the trade yourself.")


def cmd_lessons(_a) -> None:
    for line in lessons.summary():
        print(line)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="download public bars and freeze them as a dataset")
    f.add_argument("--source", choices=["kraken", "gecko"], default="kraken")
    f.add_argument("--pair", default="ETHUSD", help="Kraken pair, e.g. ETHUSD, SOLUSD, XBTUSD")
    f.add_argument("--interval", type=int, default=1440, help="Kraken minutes: 60, 240, 1440 ...")
    f.add_argument("--network", default="solana", help="GeckoTerminal network id")
    f.add_argument("--pool", help="GeckoTerminal pool address")
    f.add_argument("--timeframe", default="day", choices=["day", "hour", "minute"])
    f.add_argument("--name", help="dataset name")
    f.add_argument("--refresh", action="store_true", help="overwrite an existing dataset")
    f.set_defaults(func=cmd_fetch)

    s = sub.add_parser("scan", help="backtest every candidate on train + validation and run the gate")
    s.add_argument("--dataset", required=True)
    s.add_argument("--fee", type=float, default=DEFAULT_FEE, help="fee per entry and per exit, 0.005 = 0.50%%")
    s.set_defaults(func=cmd_scan)

    t = sub.add_parser("test", help="open the locked test window, once")
    t.add_argument("--dataset", required=True)
    t.add_argument("--unlock-test", action="store_true")
    t.add_argument("--again", action="store_true", help="look again (the result is no longer clean)")
    t.set_defaults(func=cmd_test)

    g = sub.add_parser("signal", help="today's signal from candidates that passed the gate")
    g.add_argument("--dataset", required=True)
    g.set_defaults(func=cmd_signal)

    l = sub.add_parser("lessons", help="why candidates got blocked, across all scans")
    l.set_defaults(func=cmd_lessons)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
