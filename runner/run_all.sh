#!/usr/bin/env bash
# Run the evals for every setup in setups.conf, one engine at a time.
#   bash run_all.sh            full run
#   bash run_all.sh --limit 5  smoke test (5 questions per task)
# Extra args are passed to run_evals.py. Re-running resumes where it stopped.
# Suggested: mkdir -p results && tmux new -s evals 'bash run_all.sh 2>&1 | tee -a results/run_all.log'
set -u
cd "$(dirname "$0")"
mkdir -p results logs
CONF=setups.conf
[ -f "$CONF" ] || { echo "copy setups.example.conf to setups.conf and fill it in"; exit 1; }
# PY picks the interpreter that has requirements.txt installed (e.g. a venv's python).
PY="${PY:-python3}"

wait_ready() {  # $1 = base url
  for _ in $(seq 1 ${READY_TRIES:-120}); do
    curl -sf "$1/models" >/dev/null 2>&1 && return 0
    sleep 5
  done
  return 1
}

while IFS='|' read -r NAME URL START STOP; do
  [[ -z "${NAME// }" || "$NAME" =~ ^# ]] && continue
  NAME=$(echo "$NAME" | xargs); URL=$(echo "$URL" | xargs)
  echo "=== $NAME  $(date '+%F %T') ==="
  PID=""
  if [ -n "${START// }" ]; then
    setsid bash -c "$START" > "logs/$NAME.engine.log" 2>&1 &
    PID=$!
  fi
  if ! wait_ready "$URL"; then
    echo "!!! $NAME did not come up at $URL within 10 min, see logs/$NAME.engine.log"
  else
    "$PY" run_evals.py --name "$NAME" --base-url "$URL" "$@" < /dev/null
  fi
  if [ -n "${STOP// }" ]; then bash -c "$STOP" || true; fi
  if [ -n "$PID" ]; then kill -TERM -- "-$PID" 2>/dev/null; sleep 5; kill -KILL -- "-$PID" 2>/dev/null; fi
  sleep 20  # let GPU memory drain before the next engine
done < "$CONF"

"$PY" summarize.py
