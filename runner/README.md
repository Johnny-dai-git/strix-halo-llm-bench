# eval-runner

The accuracy harness behind the [Halogen vs Gufo vs Strata report](https://johnny-dai-git.github.io/strix-halo-llm-bench/). It sends HumanEval, IFEval, GSM8K and MMLU-Pro to any OpenAI-compatible `/v1/chat/completions` endpoint, scores the replies, and saves every reply so results can be checked or re-scored later.

[中文说明在下面](#中文)

## Quick start

```bash
cd runner
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pip install --no-deps lm_eval==0.4.13   # only its IFEval checker is used
python3 fetch_data.py                   # 4.7 MB into ../eval-cache/data, sha256-checked
```

Point it at a running server:

```bash
python3 run_evals.py --name my-setup --base-url http://127.0.0.1:8080/v1 --limit 5   # smoke test
python3 run_evals.py --name my-setup --base-url http://127.0.0.1:8080/v1             # full run
python3 summarize.py                                                                  # results/summary.md + .json
```

A run resumes where it stopped: finished questions are skipped.

To start and stop engines one after another, copy `setups.example.conf` to `setups.conf`, fill in each engine's start and stop commands, and run `bash run_all.sh` (set `PY=.venv/bin/python` if the venv isn't active). `setups.experiment.conf` holds the exact commands used for the published results.

## What it runs

| Task | Questions | Score | `max_tokens` |
|---|---:|---|---:|
| HumanEval | 164 | pass@1: the reply's code runs against the official tests in a subprocess, 20 s timeout | 1,024 |
| IFEval | 541 | prompt-level strict, with lm_eval's official checker | 1,280 |
| GSM8K | 1,319 | the number after the last `#### `, falling back to "answer is" and then the last number | 1,024 |
| MMLU-Pro | 1,000 | stratified by subject (seed 1234), choice read from "the answer is (X)" | 2,048 |

Thinking off (`chat_template_kwargs: {enable_thinking: false}`, falling back to `/no_think` if the server rejects it), temperature 0, seed 0, one request at a time. `--thinking on --max-tokens-scale 4` turns thinking on. Intervals in the summary are normal-approximation 95% binomial intervals.

HumanEval runs model-written code on your machine, as the benchmark intends. Run it somewhere you're comfortable with that.

## Data and checking the published results

`fetch_data.py` downloads the four sets from Hugging Face at pinned revisions and checks their sha256: `openai/openai_humaneval`, `google/IFEval`, `openai/gsm8k` (main) and `TIGER-Lab/MMLU-Pro`.

`results/<setup>/<task>.jsonl` holds every reply from the published runs, one line per question, with its verdict, finish reason, token count and time. `results/<setup>/meta.json` records the endpoint and settings. To re-score them without a server:

```bash
python3 rescore.py                 # all setups; exits non-zero if any verdict changes
python3 rescore.py gufo-ud --tasks gsm8k
```

HumanEval, GSM8K and MMLU-Pro re-score to exactly the saved verdicts. IFEval re-scores to all but 6 of 1,696 saved verdicts (2 or fewer per setup). The official IFEval checker isn't deterministic: `letter_frequency` swaps a non-letter target such as `!` or `#` for a random letter, and `langdetect` is unseeded. `run_evals.py` now seeds both, so a reply always gets the same verdict; the published runs predate that change, and `rescore.py` lists those 6 prompts instead of failing on them.

| Folder | Engine and weights |
|---|---|
| `halogen-v2` | Halogen 0.18.18, native HGN v2 checkpoint |
| `halogen-v2-aguard0` | Same, with `-e HALOGEN_ANSWER_GUARD=0` (GSM8K only; see [halogen-flash-server#259](https://github.com/peonist-ai/halogen-flash-server/issues/259)) |
| `halogen-ud` | Halogen 0.18.18, Unsloth UD-Q4_K_XL GGUF |
| `gufo-ud` | Gufo 0.27.0, Unsloth UD-Q4_K_XL GGUF + MTP shared-Q8_0 |
| `strata-ud` | Strata 0.2.7, Unsloth UD-Q4_K_XL GGUF (stopped after HumanEval and 73 IFEval prompts) |

All on one AMD Ryzen AI Max+ 395 with 128 GB, Ubuntu 26.04.1.

---

## 中文

[Halogen vs Gufo vs Strata 报告](https://johnny-dai-git.github.io/strix-halo-llm-bench/)背后的准确率评测工具。它把 HumanEval、IFEval、GSM8K、MMLU-Pro 发给任何 OpenAI 兼容的 `/v1/chat/completions` 接口，给回答打分，并保存每一条回答，方便以后核对或重新打分。

**快速开始**：按上面 Quick start 的命令建虚拟环境、装依赖（`lm_eval` 用 `--no-deps` 安装，只用到它的 IFEval 评分代码），再运行 `fetch_data.py` 下载数据（4.7 MB，会校验 sha256）。然后用 `run_evals.py --base-url` 指向已启动的推理服务器；先加 `--limit 5` 冒烟测试。中途断了重跑同一条命令即可，已完成的题会跳过。`summarize.py` 生成汇总表。

**多个引擎轮流跑**：把 `setups.example.conf` 复制成 `setups.conf`，填好每个引擎的启动和停止命令，运行 `bash run_all.sh`。发布结果用的实际命令在 `setups.experiment.conf`。

**设置**：默认关闭思考，温度 0，种子 0，每次一个请求。HumanEval 会在本机子进程里执行模型写的代码（这是该测试的标准做法），请在你放心的环境里运行。

**核对已发布的结果**：`results/<配置>/<任务>.jsonl` 里是发布结果的每一条原始回答。`python3 rescore.py` 不需要推理服务器，就能用同样的评分代码重新打分；只要有一题判定和保存的不同，就会列出来并返回非零退出码。HumanEval、GSM8K、MMLU-Pro 重新打分后和保存的判定完全一致。IFEval 有 6 题（共 1,696 个判定，每套配置最多 2 题）不同：官方 IFEval 评分代码本身有随机性（`letter_frequency` 遇到 `!`、`#` 这类非字母目标会随机换成一个字母，`langdetect` 也没有固定种子）。现在 `run_evals.py` 固定了这两处种子，同一回答每次判定都一样；已发布的结果是在这个改动之前跑的，`rescore.py` 会列出这 6 题，但不算失败。
