#!/usr/bin/env python3
"""Speed probe for an OpenAI-compatible /v1/chat/completions endpoint.

Same shape as the llm-probe.sh runs behind the report: 3 short prompts with 256 tokens out,
then fresh 8K / 30K / 32K / 131K prompts (shuffled common words, so no prompt cache helps)
with 128 tokens out. Greedy, thinking off, one request at a time, streamed.

  prefill tok/s = prompt_tokens / time to first token
  decode tok/s  = (completion_tokens - 1) / (time of last token - time of first token)

Prompts are built from a fixed seed, so two runs send identical requests.

  python3 speed_probe.py --base-url http://127.0.0.1:8080/v1 --out results/speed/gufo-0.34.json
"""
import argparse
import http.client
import json
import random
import time
import urllib.parse

SHORT = [
    ("story", "Write a short story about a lighthouse keeper who finds a message in a bottle."),
    ("fridge", "Explain how a refrigerator works, step by step, for a curious teenager."),
    ("python", "Write a Python function that parses a CSV file of transactions and returns the "
               "total amount per category, with type hints and a docstring."),
]
LONG = [("8K", 8192), ("30K", 30023), ("32K", 32768), ("131K", 131072)]
WORDS = ("time year people way day man thing woman life child world school state family student group "
         "country problem hand part place case week company system program question work government number "
         "night point home water room mother area money story fact month lot right study book eye job word "
         "business issue side kind head house service friend father power hour game line end member law car "
         "city community name president team minute idea kid body information back parent face others level "
         "office door health person art war history party result change morning reason research girl guy "
         "moment air teacher force education foot boy age policy music market sense nation plan college "
         "interest death experience effect class control care field development role effort rate heart drug "
         "show leader light voice wife police mind price report decision son view relationship town road arm "
         "difference value building action model season society tax director position player record paper "
         "space ground form event official matter center couple site project activity star table need court "
         "oil situation cost industry figure street image phone data picture practice piece land product "
         "doctor wall patient worker news test movie north love support technology step baby computer type "
         "attention film tree source organization hair window evidence population site truth river").split()


def post_stream(base, key, body):
    u = urllib.parse.urlparse(base)
    conn = http.client.HTTPConnection(u.hostname, u.port, timeout=1800)
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    t0 = time.perf_counter()
    conn.request("POST", u.path.rstrip("/") + "/chat/completions", json.dumps(body), headers)
    r = conn.getresponse()
    if r.status != 200:
        raise RuntimeError(f"HTTP {r.status}: {r.read()[:500]!r}")
    first = last = None
    usage = None
    while True:
        line = r.readline()
        if not line:
            break
        line = line.strip()
        if not line.startswith(b"data:"):
            continue
        data = line[5:].strip()
        if data == b"[DONE]":
            break
        ev = json.loads(data)
        if ev.get("usage"):
            usage = ev["usage"]
        for ch in ev.get("choices") or []:
            d = ch.get("delta") or {}
            if d.get("content") or d.get("reasoning_content"):
                now = time.perf_counter()
                first = first or now
                last = now
    conn.close()
    return t0, first, last, usage


def request(base, key, model, content, max_tokens):
    body = {"model": model, "messages": [{"role": "user", "content": content}],
            "max_tokens": max_tokens, "temperature": 0, "seed": 0, "stream": True,
            "stream_options": {"include_usage": True},
            "chat_template_kwargs": {"enable_thinking": False}}
    t0, first, last, usage = post_stream(base, key, body)
    pt, ct = usage["prompt_tokens"], usage["completion_tokens"]
    return {"prompt_tokens": pt, "completion_tokens": ct,
            "ttft_s": round(first - t0, 3),
            "prefill_tps": round(pt / (first - t0), 1),
            "decode_tps": round((ct - 1) / (last - first), 1) if ct > 1 and last > first else None}


def filler(rng, n_words):
    return " ".join(rng.choice(WORDS) for _ in range(n_words))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    ap.add_argument("--api-key", default="")
    ap.add_argument("--model", default="qwen3.8-flash-next")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=20261113)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    out = {"base_url": a.base_url, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "short": {}, "long": {}}

    request(a.base_url, a.api_key, a.model, "Say hi.", 8)  # warm-up, not recorded
    for name, prompt in SHORT:
        out["short"][name] = r = request(a.base_url, a.api_key, a.model, prompt, 256)
        print(name, r, flush=True)
    short = [v["decode_tps"] for v in out["short"].values()]
    out["short_avg_decode_tps"] = round(sum(short) / len(short), 1)

    # Calibrate words per token on this tokenizer, then build each long prompt to its target length.
    probe = filler(random.Random(0), 2000)
    pt = request(a.base_url, a.api_key, a.model, probe, 1)["prompt_tokens"]
    words_per_token = 2000 / pt
    for name, target in LONG:
        text = filler(rng, int((target - 40) * words_per_token))
        prompt = f"{text}\n\nIn one sentence, which word above seems most common?"
        out["long"][name] = r = request(a.base_url, a.api_key, a.model, prompt, 128)
        print(name, r, flush=True)
    out["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with open(a.out, "w") as f:
        json.dump(out, f, indent=2)
    print("short avg decode", out["short_avg_decode_tps"])


if __name__ == "__main__":
    main()
