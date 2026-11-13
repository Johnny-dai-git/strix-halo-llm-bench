| Task | halogen-v2 | halogen-ud | gufo-ud | strata-ud | halogen-v2-aguard0 |
|---|---:|---:|---:|---:|---:|
| HumanEval pass@1 | 96.3 ± 2.9 (n=164) | 97.0 ± 2.6 (n=164) | 97.0 ± 2.6 (n=164) | 97.6 ± 2.4 (n=164) | — |
| IFEval prompt strict | 82.8 ± 3.2 (n=541) | 84.8 ± 3.0 (n=541) | 83.2 ± 3.2 (n=541) | 93.2 ± 5.8 (n=73) | — |
| GSM8K | 87.7 ± 1.8 (n=1319) | 84.1 ± 2.0 (n=1319) | 96.0 ± 1.1 (n=1319) | — | 96.1 ± 1.1 (n=1319) |
| MMLU-Pro (1,000 sample) | 77.4 ± 2.6 (n=1000) | 76.1 ± 2.6 (n=1000) | 77.2 ± 2.6 (n=1000) | — | — |

± is a 95% binomial interval.

- halogen-v2 / humaneval: request errors 0, hit max_tokens 1, no answer extracted 0
- halogen-v2 / ifeval: request errors 0, hit max_tokens 23, no answer extracted 0
- halogen-v2 / gsm8k: request errors 0, hit max_tokens 444, no answer extracted 0
- halogen-v2 / mmlu_pro: request errors 0, hit max_tokens 142, no answer extracted 139
- halogen-ud / humaneval: request errors 0, hit max_tokens 2, no answer extracted 0
- halogen-ud / ifeval: request errors 0, hit max_tokens 21, no answer extracted 0
- halogen-ud / gsm8k: request errors 0, hit max_tokens 661, no answer extracted 0
- halogen-ud / mmlu_pro: request errors 0, hit max_tokens 155, no answer extracted 150
- gufo-ud / humaneval: request errors 0, hit max_tokens 2, no answer extracted 0
- gufo-ud / ifeval: request errors 0, hit max_tokens 16, no answer extracted 0
- gufo-ud / gsm8k: request errors 0, hit max_tokens 25, no answer extracted 0
- gufo-ud / mmlu_pro: request errors 0, hit max_tokens 144, no answer extracted 141
- strata-ud / humaneval: request errors 0, hit max_tokens 1, no answer extracted 0
- strata-ud / ifeval: request errors 0, hit max_tokens 2, no answer extracted 0
- halogen-v2-aguard0 / gsm8k: request errors 0, hit max_tokens 21, no answer extracted 0
