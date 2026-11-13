#!/usr/bin/env python3
"""Offline accuracy evals against any OpenAI-compatible chat endpoint.

Tasks: humaneval, ifeval, gsm8k, mmlu_pro (data from ../eval-cache/data, or
$EVAL_CACHE/data; fetch it with fetch_data.py).
Dependencies: Python stdlib + the packages in requirements.txt (pyarrow for
parquet; langdetect / nltk / immutabledict for the official IFEval checkers,
imported from lm_eval). Packages in <cache>/lib/py are picked up if present.

Results go to results/<name>/<task>.jsonl, one line per question, so an
interrupted run resumes where it stopped.

Example:
  python3 run_evals.py --name halogen-v2 --base-url http://127.0.0.1:8080/v1
  python3 run_evals.py --name halogen-v2 --base-url ... --limit 5   # smoke test
"""
import argparse
import concurrent.futures as cf
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import threading
import time
import types
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.environ.get("EVAL_CACHE") or os.path.join(ROOT, "eval-cache")
DATA = os.path.join(CACHE, "data")
LIBPY = os.path.join(CACHE, "lib", "py")

if os.path.isdir(LIBPY) and LIBPY not in sys.path:
    sys.path.insert(0, LIBPY)
os.environ.setdefault("NLTK_DATA", os.path.join(CACHE, "lib", "nltk_data"))

ALL_TASKS = ["humaneval", "ifeval", "gsm8k", "mmlu_pro"]
MAX_TOKENS = {"humaneval": 1024, "ifeval": 1280, "gsm8k": 1024, "mmlu_pro": 2048}
MMLU_PRO_SAMPLE = 1000
MMLU_PRO_SEED = 1234
LETTERS = "ABCDEFGHIJ"


# ---------------------------------------------------------------- data

def read_parquet(name):
    import pyarrow.parquet as pq
    return pq.read_table(os.path.join(DATA, name)).to_pylist()


def load_humaneval():
    return [dict(d, id=d["task_id"]) for d in read_parquet("humaneval-test.parquet")]


def load_ifeval():
    with open(os.path.join(DATA, "ifeval.jsonl"), encoding="utf-8") as f:
        return [dict(d, id=str(d["key"])) for d in map(json.loads, f) if d]


def load_gsm8k():
    return [dict(d, id=str(i)) for i, d in enumerate(read_parquet("gsm8k-test.parquet"))]


def load_mmlu_pro(sample=MMLU_PRO_SAMPLE):
    rows = read_parquet("mmlupro-test.parquet")
    if not sample or sample >= len(rows):
        picked = rows
    else:
        # Stratified by category, proportional allocation, fixed seed: every setup gets the same questions.
        rng = random.Random(MMLU_PRO_SEED)
        by_cat = {}
        for r in rows:
            by_cat.setdefault(r["category"], []).append(r)
        cats = sorted(by_cat)
        quota = {c: int(sample * len(by_cat[c]) / len(rows)) for c in cats}
        rest = sample - sum(quota.values())
        for c in sorted(cats, key=lambda c: -(sample * len(by_cat[c]) / len(rows) % 1))[:rest]:
            quota[c] += 1
        picked = []
        for c in cats:
            picked += rng.sample(by_cat[c], quota[c])
        picked.sort(key=lambda r: int(r["question_id"]))
    return [dict(r, id=str(r["question_id"])) for r in picked]


LOADERS = {"humaneval": load_humaneval, "ifeval": load_ifeval, "gsm8k": load_gsm8k, "mmlu_pro": load_mmlu_pro}


# ---------------------------------------------------------------- prompts

def prompt_humaneval(d):
    return ("Complete the following Python function. Reply with the complete function "
            "(including any imports it needs) in a single ```python code block.\n\n"
            f"```python\n{d['prompt']}```")


def prompt_ifeval(d):
    return d["prompt"]


def prompt_gsm8k(d):
    return (f"{d['question']}\n\nSolve the problem step by step. "
            "On the last line, write the final numeric answer in the form \"#### <number>\".")


def prompt_mmlu_pro(d):
    s = (f"The following is a multiple choice question about {d['category']}. Think step by step "
         "and then finish your answer with \"the answer is (X)\" where X is the correct letter choice.\n\n")
    s += "Question:\n" + d["question"] + "\nOptions:\n"
    for i, opt in enumerate(list(d["options"])[:10]):
        s += f"{LETTERS[i]}. {str(opt).strip()}\n"
    return s + "Answer: Let's think step by step."


PROMPTS = {"humaneval": prompt_humaneval, "ifeval": prompt_ifeval, "gsm8k": prompt_gsm8k, "mmlu_pro": prompt_mmlu_pro}


# ---------------------------------------------------------------- scoring

NUM = r"-?\$?\s?\d[\d,]*(?:\.\d+)?"


def to_number(s):
    s = s.replace(",", "").replace("$", "").replace(" ", "").rstrip(".")
    try:
        return float(s)
    except ValueError:
        return None


def score_gsm8k(d, text):
    gold = to_number(d["answer"].split("####")[-1].strip())
    m = re.findall(r"####\s*(" + NUM + ")", text)
    if not m:
        m = re.findall(r"answer is\s*:?\s*(" + NUM + ")", text, re.I)
    if not m:
        m = re.findall(NUM, text)
    pred = to_number(m[-1]) if m else None
    ok = pred is not None and gold is not None and abs(pred - gold) < 1e-6
    return {"correct": ok, "pred": pred, "gold": gold}


def score_mmlu_pro(d, text):
    m = re.findall(r"answer is \(?([A-J])\)?", text)
    if not m:
        m = re.findall(r"[Aa]nswer:\s*\(?([A-J])\)?\b", text)
    pred = m[-1] if m else None
    return {"correct": pred == d["answer"], "pred": pred, "gold": d["answer"], "category": d["category"]}


def extract_code(text):
    blocks = re.findall(r"```(?:python|py|Python)?\s*\n(.*?)```", text, re.S)
    if blocks:
        return max(blocks, key=len)
    if "```" in text:  # unterminated block (hit max_tokens)
        return text.split("```", 1)[1].split("\n", 1)[-1]
    return text


def score_humaneval(d, text, timeout=20):
    code = extract_code(text)
    if re.search(rf"def\s+{re.escape(d['entry_point'])}\s*\(", code):
        # Keep the original prompt first: it carries helper functions and imports.
        # Its stub (docstring only) is a valid def that the model's version then replaces.
        program = d["prompt"] + "\n    pass\n\n" + code
    else:
        program = d["prompt"] + code  # model returned only the body
    program += "\n\n" + d["test"] + f"\n\ncheck({d['entry_point']})\n"
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "prog.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(program)
        try:
            r = subprocess.run([sys.executable, "-I", path], cwd=tmp, capture_output=True, timeout=timeout, text=True)
            ok, err = r.returncode == 0, r.stderr[-400:]
        except subprocess.TimeoutExpired:
            ok, err = False, "timeout"
    return {"correct": ok, "error": None if ok else err}


_ifeval = None


def ifeval_module():
    """Import the official IFEval checker from the bundled lm_eval without running lm_eval's
    package __init__ (which pulls in torch / datasets / transformers)."""
    global _ifeval
    if _ifeval:
        return _ifeval
    import importlib
    import importlib.util
    spec = importlib.util.find_spec("lm_eval")
    if spec is None:
        sys.exit("lm_eval not found: pip install -r requirements.txt (see README)")
    base = list(spec.submodule_search_locations)[0]
    for name, sub in (("lm_eval", ""), ("lm_eval.tasks", "tasks"), ("lm_eval.tasks.ifeval", "tasks/ifeval")):
        if name not in sys.modules:
            m = types.ModuleType(name)
            m.__path__ = [os.path.join(base, sub)]
            sys.modules[name] = m
    try:
        import packaging.version  # noqa: F401
    except ImportError:  # minimal stand-in, only used for the nltk version check
        pk, pv = types.ModuleType("packaging"), types.ModuleType("packaging.version")
        pv.parse = lambda v: tuple(int(x) for x in re.findall(r"\d+", v)[:3])
        pk.version = pv
        sys.modules["packaging"], sys.modules["packaging.version"] = pk, pv
    _ifeval = importlib.import_module("lm_eval.tasks.ifeval.utils")
    return _ifeval


def score_ifeval(d, text):
    # The official checker isn't deterministic: letter_frequency swaps a non-letter target ("!", "#")
    # for a random letter, and langdetect is unseeded. Seed both so a reply always gets the same verdict.
    # The published results predate this; see README.
    import langdetect
    langdetect.DetectorFactory.seed = 0
    random.seed(int(d["key"]))
    doc = {k: d[k] for k in ("key", "instruction_id_list", "prompt", "kwargs")}
    r = ifeval_module().process_results(doc, [text])
    return {"correct": bool(r["prompt_level_strict_acc"]), **r}


SCORERS = {"humaneval": score_humaneval, "ifeval": score_ifeval, "gsm8k": score_gsm8k, "mmlu_pro": score_mmlu_pro}


# ---------------------------------------------------------------- client

THINK_RE = re.compile(r"<think>.*?</think>", re.S)


class Client:
    def __init__(self, base_url, model, thinking, timeout, api_key):
        self.base = base_url.rstrip("/")
        self.model = model
        self.thinking = thinking
        self.timeout = timeout
        self.api_key = api_key
        self.use_kwargs = True
        self.lock = threading.Lock()

    def _post(self, path, body):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read())

    def detect_model(self):
        req = urllib.request.Request(self.base + "/models", headers={"Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read()).get("data") or []
        return data[0]["id"] if data else "default"

    def chat(self, prompt, max_tokens):
        content = prompt
        body = {"model": self.model, "temperature": 0.0, "max_tokens": max_tokens, "seed": 0,
                "messages": [{"role": "user", "content": content}]}
        if self.thinking == "off":
            if self.use_kwargs:
                body["chat_template_kwargs"] = {"enable_thinking": False}
            else:
                body["messages"][0]["content"] = content + " /no_think"
        last = None
        for attempt in range(4):
            t0 = time.time()
            try:
                r = self._post("/chat/completions", body)
                msg = r["choices"][0]["message"]
                text = msg.get("content") or ""
                return {"text": THINK_RE.sub("", text).strip(), "raw": text,
                        "reasoning_chars": len(msg.get("reasoning_content") or msg.get("reasoning") or ""),
                        "finish": r["choices"][0].get("finish_reason"),
                        "completion_tokens": (r.get("usage") or {}).get("completion_tokens"),
                        "seconds": round(time.time() - t0, 2)}
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:300]
                last = f"HTTP {e.code}: {detail}"
                if e.code in (400, 422) and "chat_template_kwargs" in body:
                    with self.lock:
                        if self.use_kwargs:
                            print("  endpoint rejected chat_template_kwargs; switching to /no_think", flush=True)
                        self.use_kwargs = False
                    body.pop("chat_template_kwargs")
                    body["messages"][0]["content"] = content + " /no_think"
                    continue
            except Exception as e:  # connection reset, timeout, engine restart
                last = repr(e)
            time.sleep(5 * (attempt + 1))
        raise RuntimeError(last)


# ---------------------------------------------------------------- main loop

def run_task(client, task, out_dir, limit, concurrency, max_tokens_scale):
    docs = LOADERS[task]()
    if limit:
        docs = docs[:limit]
    path = os.path.join(out_dir, f"{task}.jsonl")
    done = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["id"])
                except Exception:
                    pass
    todo = [d for d in docs if d["id"] not in done]
    print(f"[{task}] {len(docs)} questions, {len(done & {d['id'] for d in docs})} already done, {len(todo)} to run", flush=True)
    if not todo:
        return
    max_tokens = int(MAX_TOKENS[task] * max_tokens_scale)
    wlock = threading.Lock()
    stats = {"n": 0, "ok": 0, "t0": time.time()}

    def one(d):
        try:
            r = client.chat(PROMPTS[task](d), max_tokens)
            sc = SCORERS[task](d, r["text"])
        except Exception as e:
            r, sc = {"text": "", "error": str(e)}, {"correct": False, "request_error": str(e)}
        rec = {"id": d["id"], **sc, "finish": r.get("finish"), "completion_tokens": r.get("completion_tokens"),
               "seconds": r.get("seconds"), "reasoning_chars": r.get("reasoning_chars"), "response": r.get("raw", r.get("text"))}
        with wlock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            stats["n"] += 1
            stats["ok"] += bool(sc.get("correct"))
            if stats["n"] % 10 == 0 or stats["n"] == len(todo):
                el = time.time() - stats["t0"]
                eta = el / stats["n"] * (len(todo) - stats["n"])
                print(f"  [{task}] {stats['n']}/{len(todo)}  acc so far {stats['ok'] / stats['n']:.3f}  "
                      f"elapsed {el / 60:.1f} min  eta {eta / 60:.1f} min", flush=True)

    with cf.ThreadPoolExecutor(max_workers=concurrency) as ex:
        list(ex.map(one, todo))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True, help="setup name, e.g. halogen-v2 (results folder)")
    ap.add_argument("--base-url", required=True, help="OpenAI-compatible base URL ending in /v1")
    ap.add_argument("--model", default=None, help="model id (default: first id from /v1/models)")
    ap.add_argument("--tasks", default=",".join(ALL_TASKS))
    ap.add_argument("--limit", type=int, default=0, help="first N questions per task (smoke test)")
    ap.add_argument("--thinking", choices=["off", "on"], default="off")
    ap.add_argument("--max-tokens-scale", type=float, default=1.0, help="multiply per-task max_tokens (use ~4 with thinking on)")
    ap.add_argument("--concurrency", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=1800, help="seconds per request")
    ap.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", "none"))
    ap.add_argument("--results", default=os.path.join(HERE, "results"))
    a = ap.parse_args()

    tasks = [t.strip() for t in a.tasks.split(",") if t.strip()]
    bad = set(tasks) - set(ALL_TASKS)
    if bad:
        sys.exit(f"unknown task(s): {bad}")
    if "ifeval" in tasks:
        ifeval_module()  # fail fast if the checker can't load

    client = Client(a.base_url, a.model, a.thinking, a.timeout, a.api_key)
    if not client.model:
        client.model = client.detect_model()
    out_dir = os.path.join(a.results, a.name + (f"-smoke{a.limit}" if a.limit else ""))
    os.makedirs(out_dir, exist_ok=True)
    meta = {"name": a.name, "base_url": a.base_url, "model": client.model, "thinking": a.thinking,
            "max_tokens": {t: int(MAX_TOKENS[t] * a.max_tokens_scale) for t in tasks},
            "mmlu_pro_sample": MMLU_PRO_SAMPLE, "mmlu_pro_seed": MMLU_PRO_SEED, "limit": a.limit,
            "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"setup {a.name}  model {client.model}  thinking {a.thinking}  -> {out_dir}", flush=True)
    for t in tasks:
        run_task(client, t, out_dir, a.limit, a.concurrency, a.max_tokens_scale)
    print("done. summarize with: python3 summarize.py", flush=True)


if __name__ == "__main__":
    main()
