#!/usr/bin/env python3
"""Re-score saved replies in results/<setup>/<task>.jsonl with the scorers in run_evals.py,
without an inference server, and report any question whose verdict changes.

  python3 rescore.py                       # every setup and task under results/
  python3 rescore.py gufo-ud --tasks gsm8k

HumanEval re-runs the model's code in a subprocess, as run_evals.py does.
"""
import argparse
import json
import os
import sys

import run_evals as ev


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("setups", nargs="*", help="setup folders under results/ (default: all)")
    ap.add_argument("--tasks", default=",".join(ev.ALL_TASKS))
    ap.add_argument("--results", default=os.path.join(ev.HERE, "results"))
    a = ap.parse_args()
    setups = a.setups or sorted(d for d in os.listdir(a.results) if os.path.isdir(os.path.join(a.results, d)))
    tasks = [t.strip() for t in a.tasks.split(",") if t.strip()]
    changed = 0
    for task in tasks:
        docs = None
        for s in setups:
            path = os.path.join(a.results, s, f"{task}.jsonl")
            if not os.path.exists(path):
                continue
            docs = docs or {d["id"]: d for d in ev.LOADERS[task]()}
            rows = {}
            with open(path, encoding="utf-8") as f:
                for line in f:
                    r = json.loads(line)
                    rows[r["id"]] = r  # last write wins, as in summarize.py
            same = 0
            for qid, r in rows.items():
                text = ev.THINK_RE.sub("", r.get("response") or "").strip()
                ok = bool(ev.SCORERS[task](docs[qid], text)["correct"]) if not r.get("request_error") else False
                if ok == bool(r.get("correct")):
                    same += 1
                elif task == "ifeval":  # saved verdicts predate the seeded checker; see README
                    print(f"  ifeval checker randomness: {s} id {qid}: saved {bool(r.get('correct'))}, now {ok}")
                else:
                    changed += 1
                    print(f"  changed: {s}/{task} id {qid}: saved {bool(r.get('correct'))}, now {ok}")
            n = len(rows)
            acc = sum(bool(r.get("correct")) for r in rows.values()) / n
            print(f"{s:20s} {task:10s} n={n:5d}  saved acc {acc:.4f}  verdicts unchanged {same}/{n}", flush=True)
    sys.exit(1 if changed else 0)


if __name__ == "__main__":
    main()
