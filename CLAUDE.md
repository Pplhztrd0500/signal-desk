# Rules for this project

This is a research tool. It never trades.

1. Never write code that places orders, connects to an exchange account, or stores API keys or private keys.
2. Never automate any trading app or website. Signals are printed; a human places trades by hand.
3. Data comes only from public endpoints (Kraken public OHLC, GeckoTerminal). No scraping.
4. The test window (last 20% of a dataset) is locked. Never read, tune on, or print results from it unless the user says "unlock test" in chat.
5. Strategies may only use bars up to the current one. Any new strategy must pass `tests/test_engine.py`.
6. Fees are on from the first backtest. Default 0.50% per entry and per exit.
7. Every number you report must come from a script you ran in this session. Show the command.
8. If every candidate looks great, assume a bug (usually look-ahead) and go find it before reporting.
9. Pure standard library unless the user approves a dependency.
