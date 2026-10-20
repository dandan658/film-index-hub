#!/usr/bin/env bash
set -euo pipefail
image=ghcr.io/dandan658/film-index-hub:latest
mkdir -p data media/source media/destination
compose=(docker compose -p film-index-ci -f compose.yaml)
cleanup(){ status=$?; if [[ "$status" != 0 ]]; then "${compose[@]}" logs --tail=100; fi; "${compose[@]}" down --remove-orphans; exit "$status"; }
trap cleanup EXIT
docker run --rm --entrypoint python -v "$PWD/data:/fixture" -v "$PWD/tests:/tests:ro" "$image" /tests/create_legacy_fixture.py /fixture
"${compose[@]}" up -d --no-build --pull never --wait --wait-timeout 240
python3 scripts/test_single_application.py
"${compose[@]}" restart
"${compose[@]}" up -d --no-build --pull never --wait --wait-timeout 180
python3 scripts/test_single_application.py --after-restart
docker run --rm --entrypoint python -v "$PWD/data:/fixture" -v "$PWD/tests:/tests:ro" "$image" /tests/check_persistent_data.py /fixture
ids=$("${compose[@]}" ps -q)
[[ $(echo "$ids" | wc -l) == 1 ]]
docker stats --no-stream --format '{{.Name}} {{.MemUsage}} {{.CPUPerc}}' $ids | tee /tmp/film-index-resources.txt
docker top "$ids" -eo pid,args | tee /tmp/film-index-processes.txt
[[ $(docker top "$ids" -eo args | tail -n +2 | wc -l) == 1 ]]
! docker top "$ids" -eo args | grep -E 'nginx|pm2|hub_server|Xvfb|chromium'
echo 'PASS: one running container, one Python server process, no HTTP gateway or second backend'

