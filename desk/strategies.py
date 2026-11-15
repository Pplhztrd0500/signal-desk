"""Long-only strategy families.

Rule for every strategy: signal[i] may use bars[0..i] and nothing later.
signal[i] = 1 means "be long after the close of bar i". The backtest applies it from bar i+1.
tests/test_no_lookahead.py enforces this for every candidate.
"""
from __future__ import annotations

import math
from typing import Callable

from .data import Bar


def ema(xs: list[float], n: int) -> list[float]:
    k, out, e = 2 / (n + 1), [], None
    for x in xs:
        e = x if e is None else e + k * (x - e)
        out.append(e)
    return out


def rsi(xs: list[float], n: int) -> list[float | None]:
    """Wilder RSI. None until enough data."""
    out: list[float | None] = [None] * len(xs)
    gain = loss = 0.0
    for i in range(1, len(xs)):
        ch = xs[i] - xs[i - 1]
        g, l = max(ch, 0.0), max(-ch, 0.0)
        if i <= n:
            gain += g / n
            loss += l / n
            if i < n:
                continue
        else:
            gain = (gain * (n - 1) + g) / n
            loss = (loss * (n - 1) + l) / n
        out[i] = 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)
    return out


def ema_cross(bars: list[Bar], fast: int, slow: int) -> list[int]:
    c = [b.close for b in bars]
    f, s = ema(c, fast), ema(c, slow)
    return [1 if i >= slow and f[i] > s[i] else 0 for i in range(len(c))]


def breakout(bars: list[Bar], entry: int, exit: int) -> list[int]:
    """Donchian: buy a close above the prior `entry`-bar high, sell a close below the prior `exit`-bar low."""
    pos, out = 0, []
    for i, b in enumerate(bars):
        if pos == 0 and i >= entry and b.close > max(x.high for x in bars[i - entry:i]):
            pos = 1
        elif pos == 1 and i >= exit and b.close < min(x.low for x in bars[i - exit:i]):
            pos = 0
        out.append(pos)
    return out


def rsi_revert(bars: list[Bar], period: int, buy_below: float, sell_above: float) -> list[int]:
    r = rsi([b.close for b in bars], period)
    pos, out = 0, []
    for v in r:
        if v is not None:
            if pos == 0 and v < buy_below:
                pos = 1
            elif pos == 1 and v > sell_above:
                pos = 0
        out.append(pos)
    return out


def zscore_revert(bars: list[Bar], lookback: int, z: float) -> list[int]:
    """Buy when price is `z` std devs below its rolling mean, sell when it gets back to the mean."""
    c = [b.close for b in bars]
    pos, out = 0, []
    for i in range(len(c)):
        if i + 1 >= lookback:
            w = c[i + 1 - lookback:i + 1]
            m = sum(w) / lookback
            sd = math.sqrt(sum((x - m) ** 2 for x in w) / lookback)
            zz = (c[i] - m) / sd if sd > 0 else 0.0
            if pos == 0 and zz < -z:
                pos = 1
            elif pos == 1 and zz >= 0:
                pos = 0
        out.append(pos)
    return out


def momentum(bars: list[Bar], lookback: int) -> list[int]:
    c = [b.close for b in bars]
    return [1 if i >= lookback and c[i] > c[i - lookback] else 0 for i in range(len(c))]


FAMILIES: dict[str, Callable[..., list[int]]] = {
    "ema_cross": ema_cross,
    "breakout": breakout,
    "rsi_revert": rsi_revert,
    "zscore_revert": zscore_revert,
    "momentum": momentum,
}

# Every candidate the scan tests. Keep this list small: each extra candidate is one more
# lottery ticket, and the more tickets you buy, the more likely one "wins" by pure luck.
GRID: list[tuple[str, dict]] = [
    ("ema_cross", {"fast": 5, "slow": 20}),
    ("ema_cross", {"fast": 10, "slow": 30}),
    ("ema_cross", {"fast": 20, "slow": 50}),
    ("breakout", {"entry": 10, "exit": 5}),
    ("breakout", {"entry": 20, "exit": 10}),
    ("breakout", {"entry": 55, "exit": 20}),
    ("rsi_revert", {"period": 14, "buy_below": 30, "sell_above": 55}),
    ("rsi_revert", {"period": 14, "buy_below": 25, "sell_above": 50}),
    ("rsi_revert", {"period": 7, "buy_below": 20, "sell_above": 60}),
    ("zscore_revert", {"lookback": 20, "z": 1.5}),
    ("zscore_revert", {"lookback": 20, "z": 2.0}),
    ("zscore_revert", {"lookback": 50, "z": 2.0}),
    ("momentum", {"lookback": 10}),
    ("momentum", {"lookback": 30}),
    ("momentum", {"lookback": 90}),
]


def candidate_id(family: str, params: dict) -> str:
    return family + "(" + ",".join(f"{k}={v}" for k, v in params.items()) + ")"


def signal_for(family: str, params: dict, bars: list[Bar]) -> list[int]:
    return FAMILIES[family](bars, **params)
