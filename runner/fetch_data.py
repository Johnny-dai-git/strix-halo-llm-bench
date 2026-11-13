#!/usr/bin/env python3
"""Download the four eval sets from Hugging Face into <cache>/data and check their sha256.

The files and revisions are the ones the published results were run on.
<cache> is $EVAL_CACHE, or ../eval-cache next to this folder (same as run_evals.py).

  python3 fetch_data.py
"""
import hashlib
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.environ.get("EVAL_CACHE") or os.path.join(os.path.dirname(HERE), "eval-cache")
DATA = os.path.join(CACHE, "data")

# local name: (dataset, revision, path in the dataset repo, sha256)
FILES = {
    "humaneval-test.parquet": ("openai/openai_humaneval", "7dce6050a7d6d172f3cc5c32aa97f52fa1a2e544",
                               "openai_humaneval/test-00000-of-00001.parquet",
                               "2f2871a15fbc95b6c683043359f4ed8e144c5a1c4f24f25f66bc51f598dfcfb6"),
    "ifeval.jsonl": ("google/IFEval", "966cd89545d6b6acfd7638bc708b98261ca58e84",
                     "ifeval_input_data.jsonl",
                     "6a85310ca8ce15eff755aa08a3a4ff931c7e273e7515ebb3c492ea85fd8288f2"),
    "gsm8k-test.parquet": ("openai/gsm8k", "740312add88f781978c0658806c59bc2815b9866",
                           "main/test-00000-of-00001.parquet",
                           "ee7b8da9e381df27b9e3f7758a159ab2bdaa4dbaa910546cbbc47e0cb44e4f59"),
    "mmlupro-test.parquet": ("TIGER-Lab/MMLU-Pro", "b189ec765aa7ed75c8acfea42df31fdae71f97be",
                             "data/test-00000-of-00001.parquet",
                             "0e24a191921c2f453518a537a8b2117bd137e7714d4ef1565e9ba06c1ecb9ad8"),
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    os.makedirs(DATA, exist_ok=True)
    bad = 0
    for name, (repo, rev, path, want) in FILES.items():
        dest = os.path.join(DATA, name)
        if os.path.exists(dest) and sha256(dest) == want:
            print(f"ok      {name} (already there)")
            continue
        url = f"https://huggingface.co/datasets/{repo}/resolve/{rev}/{path}"
        print(f"fetch   {name} <- {url}", flush=True)
        urllib.request.urlretrieve(url, dest + ".part")
        got = sha256(dest + ".part")
        if got != want:
            print(f"BAD     {name}: sha256 {got}, expected {want}")
            bad += 1
            continue
        os.replace(dest + ".part", dest)
        print(f"ok      {name}")
    print(f"data in {DATA}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
