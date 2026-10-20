#!/usr/bin/env bash
set -euo pipefail
cat > /tmp/film-hub-ci.yaml <<'YAML'
services:
  pan:
    environment:
      ADMIN_PASSWORD: ci-smoke-test-only
YAML
compose=(docker compose -p film-hub-ci -f compose.yaml -f compose.build.yaml -f /tmp/film-hub-ci.yaml)
cleanup(){ status=$?; if [[ "$status" != 0 ]]; then "${compose[@]}" logs --tail=150; fi; "${compose[@]}" down --remove-orphans; exit "$status"; }
trap cleanup EXIT
"${compose[@]}" up -d --no-build --pull never --wait --wait-timeout 240
python3 scripts/test_gateway.py
"${compose[@]}" restart pan media
"${compose[@]}" up -d --no-build --pull never --wait --wait-timeout 180
for attempt in $(seq 1 90); do
  if curl --max-time 3 -fsS http://127.0.0.1:18520/healthz >/dev/null; then break; fi
  sleep 2
done
python3 scripts/test_gateway.py --after-restart
"${compose[@]}" ps --format json > /tmp/film-hub-containers.json
ids=$("${compose[@]}" ps -q)
docker stats --no-stream --format '{{.Name}} {{.MemUsage}} {{.CPUPerc}}' $ids | tee /tmp/film-hub-resources.txt
for id in $("${compose[@]}" ps -q media); do
  docker top "$id" -eo pid,args > /tmp/film-hub-media-processes.txt
  ! grep -E 'pm2|Xvfb|chromium' /tmp/film-hub-media-processes.txt
 done
