"""Public market data, cached locally, split into train / validation / locked test windows.

Sources (no API keys, no accounts):
  - Kraken public OHLC         -> majors like ETH/USD, SOL/USD (max 720 bars per call)
  - GeckoTerminal public OHLCV -> any DEX pool, e.g. Solana memecoins (max 1000 bars)
"""
from __future__ import annotations

import csv
import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
UA = "signal-desk/0.1 (+https://github.com)"


@dataclass(frozen=True)
class Bar:
    ts: int  # bar open time, unix seconds
    open: float
    high: float
    low: float
    close: float
    volume: float


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_kraken(pair: str = "ETHUSD", interval: int = 1440) -> list[Bar]:
    """interval in minutes: 1, 5, 15, 30, 60, 240, 1440, 10080."""
    q = urllib.parse.urlencode({"pair": pair, "interval": interval})
    d = _get_json(f"https://api.kraken.com/0/public/OHLC?{q}")
    if d.get("error"):
        raise RuntimeError(f"Kraken error: {d['error']}")
    key = next(k for k in d["result"] if k != "last")
    bars = [Bar(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[6]))
            for r in d["result"][key]]
    return bars[:-1]  # the newest bar is still forming: never trade on it


def fetch_geckoterminal(network: str, pool: str, timeframe: str = "day") -> list[Bar]:
    """timeframe: day | hour | minute. `pool` is the pool address, not the token address."""
    q = urllib.parse.urlencode({"aggregate": 1, "limit": 1000, "currency": "usd"})
    url = f"https://api.geckoterminal.com/api/v2/networks/{network}/pools/{pool}/ohlcv/{timeframe}?{q}"
    rows = _get_json(url)["data"]["attributes"]["ohlcv_list"]
    bars = sorted((Bar(int(r[0]), *map(float, r[1:6])) for r in rows), key=lambda b: b.ts)
    return bars[:-1]


def dataset_path(name: str) -> str:
    return os.path.join(DATA_DIR, f"{name}.csv")


def save(name: str, bars: list[Bar]) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    path = dataset_path(name)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "open", "high", "low", "close", "volume"])
        for b in bars:
            w.writerow([b.ts, b.open, b.high, b.low, b.close, b.volume])
    return path


def load(name: str) -> list[Bar]:
    path = dataset_path(name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"No dataset '{name}'. Run: python run.py fetch ... first.")
    with open(path, newline="") as f:
        return [Bar(int(r["ts"]), float(r["open"]), float(r["high"]), float(r["low"]),
                    float(r["close"]), float(r["volume"])) for r in csv.DictReader(f)]


def list_datasets() -> list[str]:
    if not os.path.isdir(DATA_DIR):
        return []
    return sorted(f[:-4] for f in os.listdir(DATA_DIR) if f.endswith(".csv"))


def split_points(n: int, train: float = 0.6, val: float = 0.2) -> tuple[int, int]:
    """Chronological split. Returns (val_start, test_start).

    bars[:val_start]          train      -> free to explore
    bars[val_start:test_start] validation -> the risk gate judges here
    bars[test_start:]         test       -> LOCKED, opened once at the very end
    """
    if n < 100:
        raise ValueError(f"Only {n} bars. Need at least 100 for three honest windows.")
    return int(n * train), int(n * (train + val))
