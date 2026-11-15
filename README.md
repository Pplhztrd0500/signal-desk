# signal-desk

A small trading research terminal you can build in an evening with Claude Code.
It pulls public market data, backtests a handful of strategies with fees, runs every
one through a risk gate, keeps the last chunk of data locked until the very end, and
tells you which ideas did **not** survive. It never places orders.

- Pure Python standard library. No API keys, no exchange account, nothing to `pip install`.
- Data: Kraken (majors like ETH, SOL, BTC) and GeckoTerminal (any DEX pool, incl. Solana memecoins).
- Every number it prints comes from a script you can rerun.

Follow the build on X: [@Pplhz_trd_0500](https://x.com/Pplhz_trd_0500)

> Not financial advice. This is a research tool. Past results, including the ones below, prove nothing about the future.

## What a run looks like

My own run, ETH/USD daily bars from Kraken (Nov 25 2024 → Nov 14 2026), 0.50% fee per entry and per exit:

- 15 candidates, 5 strategy families
- **14 of 15 blocked** by the gate on validation
- 1 passed: `momentum(lookback=30)`, +0.6% on validation while buy & hold lost 32.7%
- Locked test window (Jun 24 → Nov 14 2026), opened once: **+24.2% vs buy & hold +8.1%, 5 trades**
- Same 15 candidates on BONK/SOL daily: **0 of 15 passed**

One candidate holding up on one asset with five trades is a hint, not an edge. Read it that way.

## Quick start

```bash
git clone https://github.com/Pplhztrd0500/signal-desk.git && cd signal-desk
python -m unittest discover -s tests          # the no-look-ahead and fee tests
python run.py fetch --source kraken --pair ETHUSD --interval 1440 --name eth_daily
python run.py scan --dataset eth_daily
python run.py lessons
python run.py test --dataset eth_daily --unlock-test   # once, when you're done tuning
python run.py signal --dataset eth_daily               # today's call from candidates that passed
```

A Solana memecoin instead? Find the pool on geckoterminal.com and copy its address:

```bash
python run.py fetch --source gecko --network solana --pool <POOL_ADDRESS> --name mytoken_daily
```

## How it keeps itself honest

| Rule | Where |
|---|---|
| Data is split by time: 60% train, 20% validation, 20% test | `desk/data.py` |
| The scan cannot see the test window at all. Opening it takes `--unlock-test`, and a second look is refused | `run.py` |
| A signal decided at a close is filled at that close and earns the *next* bar | `desk/backtest.py` |
| Fees on every entry and exit, buy & hold pays the same fees | `desk/backtest.py` |
| Strategies may only use past bars. A test feeds them a cut-off history and checks nothing changes | `tests/test_engine.py` |
| Risk gate: positive after fees, beats buy & hold, drawdown ≤ 30%, ≥ 6 trades, positive on train too, survives acting one bar late | `desk/gate.py` |
| Every block is saved with its reason, so you stop retrying the same idea | `desk/lessons.py` |

## Build it yourself with Claude Code

The `prompts/` folder has the step-by-step prompts I used. Paste them into Claude Code
one at a time, in an empty folder, and you end up with this repo. `CLAUDE.md` holds the
rules the agent follows every session.

## Where I trade the signals

signal-desk only researches. When I act on a signal, I place the trade myself on
[fomo](https://fomo.family), where every trade I make shows up in a public feed, so
you can check my results against what this tool said instead of taking my word for it.

**Disclosure:** the link below is my referral link. If you sign up through it you get
10% off fomo's standard trading fee (0.50% → 0.45%), and I receive a share of the
trading fees fomo charges you. It does not add anything to what you pay.
You don't need fomo, or any account, to use this repo.

→ **fomo.family/r/Pplhz_trd0500**

Check that fomo is available where you live before signing up (see its Terms of Service).
A referral code can only be applied before your first trade.

## Extending it

- Add a strategy: write a function in `desk/strategies.py`, add it to `FAMILIES` and `GRID`. The look-ahead test covers it automatically.
- Raise the fee with `--fee 0.01` and see what still survives.
- Walk-forward: fetch the same asset again in a month as a new dataset and rerun the test on bars the scan never saw.

If you run it on your own coins, post what it blocked and tag [@Pplhz_trd_0500](https://x.com/Pplhz_trd_0500).

MIT license.
