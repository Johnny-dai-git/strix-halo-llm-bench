# Gufo 0.34 speed re-run (2026-11-13)

A follow-up to the main report, prompted by a Gufo maintainer's reply in [gufo-org/gufo discussion #1208](https://github.com/gufo-org/gufo/discussions/1208): the report used Gufo 0.27.0 on the balanced power profile, and newer releases are faster. This re-run measures Gufo only. Halogen and Strata were not re-run, so these numbers are not comparable to the other engines in the main report.

Same machine (Ryzen AI Max+ 395, 128 GB), same weights (Unsloth UD-Q4_K_XL + MTP shared-Q8_0), power profile **performance**, IOMMU left on (translated mode). Gufo 0.27.0 was re-run under the same conditions as a control, so the 0.27 → 0.34 change is separated from the power-profile change.

## gufo bench (Gufo's own tool, 3 repetitions)

`gufo-bench.sh`, raw output in `gufo-bench-2026-11-13.txt`.

| Test | 0.27.0, balanced (report) | 0.27.0, performance | 0.34.0, performance | Published |
|---|---:|---:|---:|---:|
| pp2048, no drafting | 1,515 | 1,650 | **1,729** | 1,801 |
| pp8192, no drafting | — | 1,709 | **1,777** | — |
| pp32768, no drafting | — | 1,656 | **1,722** | — |
| pp131072, no drafting | — | 1,570 | **1,638** | — |
| tg128, no drafting | 29.40 | 29.50 | **30.45** | 28.29 |
| tg128, MTP | 48.44 | 48.78 | **62.29** | — |

- Performance vs balanced: about +9% prompt speed, no change in decode.
- 0.27 → 0.34: about +4–5% prompt speed, +3% plain decode, **+28% decode with MTP**. The MTP gain matches 0.28.1's "end MTP chains at the first unconfident draft".
- pp2048 is now 4% below the published 1,801 (it was 16% below).

### IOMMU passthrough (`iommu=pt`)

The maintainer also suggested disabling IOMMU. Re-run of 0.34.0 after booting with `iommu=pt` (all IOMMU groups `identity`, previously `DMA-FQ`); raw output in `gufo-bench-2026-11-13-iommu-pt.txt`. The same reboot also moved the kernel from 7.0.0-42 to 7.0.0-43, so this column changes both.

| Test | 0.34.0, IOMMU translated | 0.34.0, `iommu=pt` | Change |
|---|---:|---:|---:|
| pp2048, no drafting | 1,729 | 1,746 | +1.0% |
| pp8192, no drafting | 1,777 | 1,790 | +0.7% |
| pp32768, no drafting | 1,722 | 1,723 | 0% |
| pp131072, no drafting | 1,638 | 1,632 | −0.4% |
| tg128, no drafting | 30.45 | 30.45 | 0% |
| tg128, MTP | 62.29 | 62.33 | 0% |

Within about 1% either way, so IOMMU is not what separates this machine from the published pp2048 (now 3% below 1,801).

## API probe (speed_probe.py)

`probe-run.sh` starts the server (1 session, 262K context, MTP) and runs `../../speed_probe.py`; results in `gufo-0.27.0-performance.json` and `gufo-0.34.0-performance.json`. Streaming, greedy, thinking off, prompts built from a fixed seed so both versions get identical requests. The original `llm-probe.sh` prompts were not kept, so compare the two columns here with each other, not with the main report.

| Request | 0.27.0 | 0.34.0 | Change |
|---|---:|---:|---:|
| Short prompt, 256 out: story | 34.1 | 34.1 | 0% |
| Short prompt, 256 out: explanation | 40.2 | 47.7 | +19% |
| Short prompt, 256 out: Python function | 60.9 | 72.7 | +19% |
| **Short prompts, average decode** | **45.1** | **51.5** | **+14%** |
| Prompt speed, 8K | 1,570 | 1,608 | +2% |
| Prompt speed, 30K | 1,561 | 1,596 | +2% |
| Prompt speed, 32K | 1,561 | 1,588 | +2% |
| Prompt speed, 131K | 1,481 | 1,528 | +3% |

Prompt speed here is prompt tokens / time to first token, so it includes HTTP and chat-template overhead and gains less than `gufo bench`. Decode after the long prompts is left out: the replies were 9–128 tokens, too short to measure.
