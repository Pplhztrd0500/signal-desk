"""Honest backtest: next-bar execution, fees on every entry and exit, positions closed at window end."""
from __future__ import annotations

from dataclasses import dataclass, asdict

from .data import Bar


@dataclass
class Result:
    ret: float          # total return over the window, after fees
    bh_ret: float       # buy & hold over the same window, after the same fees
    max_dd: float       # worst peak-to-trough drop of the equity curve (0.25 = -25%)
    trades: int         # number of entries
    win_rate: float     # share of round trips that made money after fees
    exposure: float     # share of bars spent in a position
    curve: list[float]  # equity, starts at 1.0

    def summary(self) -> dict:
        d = asdict(self)
        d.pop("curve")
        return d


def run(bars: list[Bar], signal: list[int], start: int, end: int, fee: float) -> Result:
    """Evaluate `signal` on bars[start:end].

    The position held from close[i-1] to close[i] is signal[i-1]: decided at a close,
    filled at that close, earning the next bar. The window starts flat, so an open
    position at `start` pays its entry fee, and anything open at `end` pays an exit fee.
    """
    if not 0 < start < end <= len(bars):
        raise ValueError("need 0 < start < end <= len(bars)")
    eq, peak, max_dd = 1.0, 1.0, 0.0
    curve = [eq]
    held, trades, wins, in_bars = 0, 0, 0, 0
    entry_eq = 1.0
    for i in range(start + 1, end):
        want = signal[i - 1]
        if want != held:  # trade at close[i-1]
            eq *= 1 - fee
            if want == 1:
                trades += 1
                entry_eq = eq / (1 - fee)  # equity before paying the entry fee
            elif eq > entry_eq:
                wins += 1
            held = want
        if held:
            eq *= bars[i].close / bars[i - 1].close
            in_bars += 1
        peak = max(peak, eq)
        max_dd = max(max_dd, 1 - eq / peak)
        curve.append(eq)
    if held:  # close out so every window is judged flat-to-flat
        eq *= 1 - fee
        wins += eq > entry_eq
        curve[-1] = eq
        max_dd = max(max_dd, 1 - eq / peak)
    n = end - start - 1
    bh = bars[end - 1].close / bars[start].close * (1 - fee) ** 2
    return Result(
        ret=eq - 1,
        bh_ret=bh - 1,
        max_dd=max_dd,
        trades=trades,
        win_rate=wins / trades if trades else 0.0,
        exposure=in_bars / n if n else 0.0,
        curve=curve,
    )


def delayed(signal: list[int], bars: int = 1) -> list[int]:
    """Same signal, acted on `bars` later. Real edges survive a small delay; leaks and flukes often don't."""
    return [0] * bars + signal[:-bars]
