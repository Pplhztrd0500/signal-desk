"""The risk gate. A candidate must pass EVERY check to be allowed. Most should be blocked.

All checks read train and validation only. The test window is never touched here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .backtest import Result

LIMITS = {
    "max_val_drawdown": 0.30,  # crypto is volatile; still, -30% on validation is a no
    "min_trades": 6,           # fewer round trips than this is an anecdote, not a sample
}


@dataclass
class Verdict:
    passed: bool
    failed: list[str] = field(default_factory=list)  # one line per failed check, with numbers


def check(train: Result, val: Result, val_delayed: Result) -> Verdict:
    failed = []
    if val.trades == 0:
        failed.append("made no trades on validation: nothing to judge")
    elif val.ret <= 0:
        failed.append(f"validation return {val.ret:+.1%} is not positive after fees")
    if val.ret <= val.bh_ret:
        failed.append(f"validation {val.ret:+.1%} does not beat buy & hold {val.bh_ret:+.1%}")
    if val.max_dd > LIMITS["max_val_drawdown"]:
        failed.append(f"validation drawdown {val.max_dd:.1%} > {LIMITS['max_val_drawdown']:.0%} limit")
    if train.trades + val.trades < LIMITS["min_trades"]:
        failed.append(f"only {train.trades + val.trades} trades in train+validation (< {LIMITS['min_trades']})")
    if train.ret <= 0:
        failed.append(f"train return {train.ret:+.1%} is not positive: works in one window only")
    if val.ret > 0 and val_delayed.ret <= 0:  # only meaningful for something that made money on time
        failed.append(f"acting 1 bar late turns validation into {val_delayed.ret:+.1%}: timing-fragile")
    return Verdict(passed=not failed, failed=failed)
