# Qwen3.8-Flash-Next local engine evals

**网页 / Page:** https://johnny-dai-git.github.io/qwen38-flash-next-evals/

## 中文

在同一台 AMD Ryzen AI Max+ 395（Strix Halo，128 GB）上，用同一个模型和同一套题，比较 Halogen、Gufo、Strata 三个本地推理引擎的准确率。关闭思考，温度 0。

| 配置 | HumanEval | IFEval | GSM8K | MMLU-Pro |
|---|---:|---:|---:|---:|
| Halogen 0.18.18 · HGN v2 | 96.3 | 82.8 | 87.7 | 77.4 |
| Halogen 0.18.18 · HGN v2 · 关 answer guard | — | — | 96.1 | — |
| Halogen 0.18.18 · UD-Q4_K_XL | 97.0 | 84.8 | 84.1 | 76.1 |
| Gufo 0.27.0 · UD-Q4_K_XL | 97.0 | 83.2 | 96.0 | 77.2 |
| Strata 0.2.7 · UD-Q4_K_XL | 97.6 | 93.2（仅 73 题） | — | — |

- HumanEval、IFEval、MMLU-Pro 上三个引擎的差距都在 95% 置信区间内。
- GSM8K 上 Halogen 默认设置偏低，原因是 answer guard 不让回答停在 `#### <数字>` 这一行。设置 `HALOGEN_ANSWER_GUARD=0` 后是 96.1%。已报告：[peonist-ai/halogen-flash-server#259](https://github.com/peonist-ai/halogen-flash-server/issues/259)。

完整说明、置信区间和细分数据见网页。原始汇总数据在 [`data/summary.json`](data/summary.json)。

## English

Accuracy of the same model on the same questions across three local inference engines (Halogen, Gufo, Strata), on one AMD Ryzen AI Max+ 395 (Strix Halo, 128 GB). Thinking off, temperature 0.

| Setup | HumanEval | IFEval | GSM8K | MMLU-Pro |
|---|---:|---:|---:|---:|
| Halogen 0.18.18 · HGN v2 | 96.3 | 82.8 | 87.7 | 77.4 |
| Halogen 0.18.18 · HGN v2 · answer guard off | — | — | 96.1 | — |
| Halogen 0.18.18 · UD-Q4_K_XL | 97.0 | 84.8 | 84.1 | 76.1 |
| Gufo 0.27.0 · UD-Q4_K_XL | 97.0 | 83.2 | 96.0 | 77.2 |
| Strata 0.2.7 · UD-Q4_K_XL | 97.6 | 93.2 (73 prompts only) | — | — |

- On HumanEval, IFEval and MMLU-Pro, every difference between the engines is inside the 95% interval.
- Halogen's GSM8K default is low because its answer guard won't let a reply end on the `#### <number>` line. With `HALOGEN_ANSWER_GUARD=0` it scores 96.1%. Reported as [peonist-ai/halogen-flash-server#259](https://github.com/peonist-ai/halogen-flash-server/issues/259).

The page has the full method, intervals and breakdowns. Raw summary data: [`data/summary.json`](data/summary.json).
