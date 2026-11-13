#!/usr/bin/env python3
"""Collect results/<setup>/<task>.jsonl into one table (stdout + results/summary.md + results/summary.json)."""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RES = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results")
TASKS = [("humaneval", "HumanEval pass@1"), ("ifeval", "IFEval prompt strict"), ("gsm8k", "GSM8K"),
         ("mmlu_pro", "MMLU-Pro (1,000 sample)")]
ORDER = ["halogen-v2", "halogen-ud", "gufo-ud", "strata-ud"]


def load(path):
    rows = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            rows[r["id"]] = r  # last write wins
    return list(rows.values())


def ci95(p, n):
    return 1.96 * math.sqrt(p * (1 - p) / n) if n else 0


setups = sorted([d for d in os.listdir(RES) if os.path.isdir(os.path.join(RES, d))],
                key=lambda s: (ORDER.index(s) if s in ORDER else 99, s))
summary = {}
for s in setups:
    summary[s] = {}
    for t, _ in TASKS:
        p = os.path.join(RES, s, f"{t}.jsonl")
        if not os.path.exists(p):
            continue
        rows = load(p)
        n = len(rows)
        acc = sum(bool(r.get("correct")) for r in rows) / n if n else 0
        e = {"n": n, "acc": acc, "ci95": ci95(acc, n),
             "request_errors": sum(1 for r in rows if r.get("request_error")),
             "truncated": sum(1 for r in rows if r.get("finish") == "length"),
             "no_answer": sum(1 for r in rows if "pred" in r and r["pred"] is None)}
        toks = [r["completion_tokens"] for r in rows if r.get("completion_tokens")]
        secs = [r["seconds"] for r in rows if r.get("seconds")]
        e["avg_out_tokens"] = sum(toks) / len(toks) if toks else None
        e["total_minutes"] = sum(secs) / 60 if secs else None
        if t == "ifeval":
            for k in ("prompt_level_loose_acc",):
                e[k] = sum(bool(r.get(k)) for r in rows) / n
            for k in ("inst_level_strict_acc", "inst_level_loose_acc"):
                flat = [x for r in rows for x in (r.get(k) or [])]
                e[k] = sum(flat) / len(flat) if flat else 0
        if t == "mmlu_pro":
            cats = {}
            for r in rows:
                c = cats.setdefault(r.get("category"), [0, 0])
                c[0] += bool(r.get("correct"))
                c[1] += 1
            e["by_category"] = {k: v[0] / v[1] for k, v in sorted(cats.items())}
        summary[s][t] = e

lines = ["| Task | " + " | ".join(setups) + " |", "|---|" + "---:|" * len(setups)]
for t, label in TASKS:
    cells = []
    for s in setups:
        e = summary[s].get(t)
        cells.append(f"{e['acc'] * 100:.1f} ± {e['ci95'] * 100:.1f} (n={e['n']})" if e else "—")
    lines.append(f"| {label} | " + " | ".join(cells) + " |")
extra = []
for s in setups:
    for t, label in TASKS:
        e = summary[s].get(t)
        if e and (e["request_errors"] or e["truncated"] or e["no_answer"]):
            extra.append(f"- {s} / {t}: request errors {e['request_errors']}, hit max_tokens {e['truncated']}, "
                         f"no answer extracted {e['no_answer']}")
md = "\n".join(lines) + "\n\n± is a 95% binomial interval.\n" + ("\n" + "\n".join(extra) + "\n" if extra else "")
print(md)
with open(os.path.join(RES, "summary.md"), "w") as f:
    f.write(md)
with open(os.path.join(RES, "summary.json"), "w") as f:
    json.dump(summary, f, indent=2)
