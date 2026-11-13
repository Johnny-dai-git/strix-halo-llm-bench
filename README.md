# Qwen3.8-Flash-Next local engine evals

**网页 / Page:** https://johnny-dai-git.github.io/qwen38-flash-next-evals/

## 中文

在同一台 AMD Ryzen AI Max+ 395（Strix Halo，128 GB）上，比较 Halogen、Gufo、Strata 三个本地推理引擎跑 Qwen3.8-Flash-Next 的速度、内存、困惑度（PPL）和准确率。网页是完整报告；下表只列准确率（关闭思考，温度 0）。

速度和内存的要点：Halogen v2 生成 66.7 tok/s、留给其他软件 40.1 GiB，都是四套配置里最好的；同一份 UD-Q4_K_XL 权重上，Gufo（49.0 tok/s）和 Halogen（47.6 tok/s）接近，Strata 34.0 tok/s，且几乎占满内存。

| 配置 | HumanEval | IFEval | GSM8K | MMLU-Pro |
|---|---:|---:|---:|---:|
| Halogen 0.18.18 · HGN v2 | 96.3 | 82.8 | 87.7 | 77.4 |
| Halogen 0.18.18 · HGN v2 · 关 answer guard | — | — | 96.1 | — |
| Halogen 0.18.18 · UD-Q4_K_XL | 97.0 | 84.8 | 84.1 | 76.1 |
| Gufo 0.27.0 · UD-Q4_K_XL | 97.0 | 83.2 | 96.0 | 77.2 |
| Strata 0.2.7 · UD-Q4_K_XL | 97.6 | 93.2（仅 73 题） | — | — |

- HumanEval、IFEval、MMLU-Pro 上三个引擎的差距都在 95% 置信区间内。
- GSM8K 上 Halogen 默认设置偏低，原因是 answer guard 不让回答停在 `#### <数字>` 这一行。设置 `HALOGEN_ANSWER_GUARD=0` 后是 96.1%。已报告：[peonist-ai/halogen-flash-server#259](https://github.com/peonist-ai/halogen-flash-server/issues/259)。

速度、内存、PPL、完整方法和细分数据见网页。原始汇总数据在 [`data/summary.json`](data/summary.json)。

## English

Speed, memory, perplexity and accuracy of Qwen3.8-Flash-Next across three local inference engines (Halogen, Gufo, Strata) on one AMD Ryzen AI Max+ 395 (Strix Halo, 128 GB). The page is the full report; the table below lists accuracy only (thinking off, temperature 0).

Speed and memory in short: Halogen v2 decodes at 66.7 tok/s and leaves 40.1 GiB free, the best of the four setups; on the same UD-Q4_K_XL weights Gufo (49.0 tok/s) and Halogen (47.6 tok/s) are close, while Strata manages 34.0 tok/s and nearly fills memory.

| Setup | HumanEval | IFEval | GSM8K | MMLU-Pro |
|---|---:|---:|---:|---:|
| Halogen 0.18.18 · HGN v2 | 96.3 | 82.8 | 87.7 | 77.4 |
| Halogen 0.18.18 · HGN v2 · answer guard off | — | — | 96.1 | — |
| Halogen 0.18.18 · UD-Q4_K_XL | 97.0 | 84.8 | 84.1 | 76.1 |
| Gufo 0.27.0 · UD-Q4_K_XL | 97.0 | 83.2 | 96.0 | 77.2 |
| Strata 0.2.7 · UD-Q4_K_XL | 97.6 | 93.2 (73 prompts only) | — | — |

- On HumanEval, IFEval and MMLU-Pro, every difference between the engines is inside the 95% interval.
- Halogen's GSM8K default is low because its answer guard won't let a reply end on the `#### <number>` line. With `HALOGEN_ANSWER_GUARD=0` it scores 96.1%. Reported as [peonist-ai/halogen-flash-server#259](https://github.com/peonist-ai/halogen-flash-server/issues/259).

The page has speed, memory, perplexity, the full method and breakdowns. Raw summary data: [`data/summary.json`](data/summary.json).
