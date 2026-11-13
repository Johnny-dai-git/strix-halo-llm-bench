#!/usr/bin/env bash
# usage: gufo-bench.sh <version> <outdir>
set -u
V=$1; OUT=$2; mkdir -p "$OUT"
M=$HOME/Desktop/Local-Deploy
run() { # name, extra args
  local name=$1; shift
  echo "== $V $name $(date -Is) profile=$(powerprofilesctl get)" | tee -a "$OUT/bench-$V.log"
  podman run --rm --name gufo-bench --userns=keep-id:uid=1000,gid=1000 \
    --device /dev/kfd --device /dev/dri --group-add keep-groups --ulimit memlock=-1 \
    -v $M/gguf-models/UD-Q4_K_XL:/models:ro -v $M/gufo-models:/mtp:ro \
    ghcr.io/gufo-org/toolboxes/gufo-runtime:$V \
    gufo bench -m /models/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf "$@" 2>&1 | tee -a "$OUT/bench-$V.log"
}
run nodraft-pp -p 2048,8192,32768,131072 -n 128 -r 3
run mtp-tg -p 2048 -n 128 -r 3 --speculative mtp --mtp-model /mtp/mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf
