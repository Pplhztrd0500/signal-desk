"""Memory of why candidates were blocked, so the next round does not repeat the last one.

Plain JSON lines in results/lessons.jsonl. Swap in mem0 later if you want semantic search.
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter

from .data import ROOT

PATH = os.path.join(ROOT, "results", "lessons.jsonl")


def record(dataset: str, candidate: str, failed: list[str]) -> None:
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({"time": int(time.time()), "dataset": dataset,
                            "candidate": candidate, "failed": failed}) + "\n")


def load() -> list[dict]:
    if not os.path.exists(PATH):
        return []
    with open(PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def summary() -> list[str]:
    rows = load()
    if not rows:
        return ["No lessons yet. Run a scan first."]
    by_check = Counter()
    by_family = Counter()
    for r in rows:
        by_family[r["candidate"].split("(")[0]] += 1
        for msg in r["failed"]:
            by_check[_kind(msg)] += 1
    out = [f"{len(rows)} blocked candidates on record."]
    out.append("Most common reasons: " + ", ".join(f"{k} ({v})" for k, v in by_check.most_common(4)))
    out.append("Most blocked families: " + ", ".join(f"{k} ({v})" for k, v in by_family.most_common(5)))
    return out


def _kind(msg: str) -> str:
    for key, label in [("not positive after fees", "loses after fees"),
                       ("buy & hold", "loses to buy & hold"),
                       ("drawdown", "drawdown too deep"),
                       ("trades in", "too few trades"),
                       ("train return", "fails on train"),
                       ("1 bar late", "timing-fragile")]:
        if key in msg:
            return label
    return "other"
