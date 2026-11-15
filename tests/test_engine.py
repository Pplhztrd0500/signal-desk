"""The two promises this repo makes: no strategy sees the future, and the backtest trades one bar late."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from desk import backtest, strategies  # noqa: E402
from desk.data import Bar  # noqa: E402


def random_walk(n=400, seed=7):
    rnd, p, out = random.Random(seed), 100.0, []
    for i in range(n):
        o = p
        p = max(1.0, p * (1 + rnd.gauss(0, 0.03)))
        out.append(Bar(i * 86400, o, max(o, p) * 1.01, min(o, p) * 0.99, p, 1.0))
    return out


class NoLookahead(unittest.TestCase):
    def test_signals_do_not_change_when_the_future_changes(self):
        bars = random_walk()
        for family, params in strategies.GRID:
            full = strategies.signal_for(family, params, bars)
            for k in (60, 150, 250, 399):
                cut = strategies.signal_for(family, params, bars[:k])
                self.assertEqual(full[:k], cut, f"{family}{params} uses data after bar {k}")


class Backtest(unittest.TestCase):
    def test_flat_price_costs_exactly_the_fees(self):
        bars = [Bar(i, 10, 10, 10, 10, 1) for i in range(50)]
        res = backtest.run(bars, [1] * 50, 1, 50, fee=0.01)
        self.assertAlmostEqual(res.ret, (1 - 0.01) ** 2 - 1)
        self.assertEqual(res.trades, 1)

    def test_signal_is_filled_on_the_next_bar(self):
        # Price alternates up/down. A signal that buys every up-bar AFTER seeing it
        # always holds the following down-bar, so it must lose, even with zero fees.
        closes = [100, 110] * 30
        bars = [Bar(i, c, c, c, c, 1) for i, c in enumerate(closes)]
        sig = [1 if i > 0 and closes[i] > closes[i - 1] else 0 for i in range(len(closes))]
        res = backtest.run(bars, sig, 1, len(bars), fee=0.0)
        self.assertLess(res.ret, 0)

    def test_buy_and_hold_pays_the_same_fees(self):
        bars = [Bar(i, c, c, c, c, 1) for i, c in enumerate([90, 100, 120])]
        res = backtest.run(bars, [1, 1, 1], 1, 3, fee=0.005)
        self.assertAlmostEqual(res.bh_ret, 1.2 * 0.995 ** 2 - 1)
        self.assertAlmostEqual(res.ret, res.bh_ret)

    def test_delayed_shifts_by_one_bar(self):
        self.assertEqual(backtest.delayed([1, 0, 1, 1]), [0, 1, 0, 1])


if __name__ == "__main__":
    unittest.main()
