#!/usr/bin/env bash
# usage: probe-run.sh <version> ; starts Gufo, runs speed_probe.py, stops it
set -u
V=$1; M=$HOME/Desktop/Local-Deploy; S=$(dirname "$0"); R=$M/strix-halo-llm-bench/runner
mkdir -p $R/results/speed
podman run -d --rm --replace --name gufo-probe --userns=keep-id:uid=1000,gid=1000 \
  --device /dev/kfd --device /dev/dri --group-add keep-groups --ulimit memlock=-1 \
  -p 127.0.0.1:8080:8080 \
  -v $M/gguf-models/UD-Q4_K_XL:/models:ro -v $M/gufo-models:/mtp:ro \
  ghcr.io/gufo-org/toolboxes/gufo-runtime:$V \
  gufo serve --host 0.0.0.0 --port 8080 llm \
    --model /models/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf \
    --served-model-name qwen3.8-flash-next \
    --speculative mtp --mtp-model /mtp/mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf \
    --sessions 1 --context 262144 >/dev/null
t0=$(date +%s)
until curl -sf http://127.0.0.1:8080/v1/models >/dev/null; do sleep 1; [ $(( $(date +%s) - t0 )) -gt 600 ] && { podman logs gufo-probe | tail; exit 1; }; done
echo "ready after $(( $(date +%s) - t0 ))s profile=$(powerprofilesctl get)"
python3 $R/speed_probe.py --out $R/results/speed/gufo-$V-performance.json
code=$?
podman logs gufo-probe > $S/server-$V.log 2>&1
podman stop gufo-probe >/dev/null
sleep 5
exit $code
