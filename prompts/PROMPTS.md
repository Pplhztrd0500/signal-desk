# Build signal-desk with Claude Code, one prompt at a time

Open Claude Code in an empty folder. Copy `CLAUDE.md` from this repo into it first.
Paste one prompt, read what it prints, then move on. Reading the output is the real work.

---

## 1. Plan

```
Read CLAUDE.md. Plan a small Python research terminal (standard library only) that:
fetches public daily bars from Kraken, splits them by time into train / validation /
locked test, backtests a few long-only strategy families with fees, runs a risk gate,
and records why candidates were blocked. Write PLAN.md with the files, what each does,
and how data flows. Do not write code yet.
```

Check: no orders, no keys, test window locked. If not, tell it to re-read CLAUDE.md.

## 2. Data and the locked window

```
Implement desk/data.py: fetch ETHUSD daily bars from Kraken's public OHLC endpoint,
drop the still-forming last bar, save to data/<name>.csv, and split 60/20/20 by time.
Add `python run.py fetch`. Print the date range and bar count of each window.
Refuse to overwrite an existing dataset unless --refresh is passed.
```

## 3. Strategies and an honest backtest

```
Implement desk/strategies.py with five long-only families (EMA cross, Donchian breakout,
RSI mean reversion, z-score mean reversion, momentum) and 3 parameter sets each.
Implement desk/backtest.py: a signal decided at close i earns bar i+1, 0.50% fee on
every entry and exit, positions closed at window end, buy & hold pays the same fees.
Write tests/test_engine.py proving (a) no strategy changes its past signals when future
bars are removed and (b) fills happen one bar late. Run the tests and show the output.
```

## 4. The risk gate

```
Implement desk/gate.py. A candidate passes only if on validation it is positive after
fees, beats buy & hold, has drawdown <= 30%, has >= 6 trades across train+validation,
is positive on train too, and stays positive when acted on one bar late. Add
`python run.py scan` that prints one row per candidate with PASS/BLOCK and the reason.
The scan must not be able to see the test window. Run it and show me the table.
```

Expect most rows to say BLOCK. If everything passes, ask it to hunt for look-ahead.

## 5. Memory of failures

```
Implement desk/lessons.py: append every BLOCK with its exact failed checks and numbers
to results/lessons.jsonl. Print a summary of the most common reasons at the start of
each scan and with `python run.py lessons`.
```

## 6. Open the test window, once

```
Add `python run.py test --unlock-test`. It evaluates only the candidates that passed
the gate on the locked test window, logs the result, and refuses a second look at the
same dataset unless --again is passed. unlock test.
```

## 7. Today's signal, executed by hand

```
Add `python run.py signal`: fetch fresh bars without touching the frozen dataset, and
for each candidate that passed the gate print BUY / SELL / HOLD LONG / STAY FLAT for the
latest closed bar. Print a line saying the tool never places orders.
```

## 8. Another market

```
Add GeckoTerminal as a second source (public OHLCV by pool address). Fetch a Solana
memecoin pool as a new dataset and run the same scan. Compare with the ETH result.
```

## Checking the agent's work

- Ask it to list every line that reads the test window. Only `run.py test` should.
- Ask it to rerun the scan with `--fee 0.01`. Survivors should shrink, never grow.
- Ask it to explain each BLOCK in one sentence. If it can't, the gate is too vague.
