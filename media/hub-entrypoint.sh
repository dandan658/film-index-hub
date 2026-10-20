#!/bin/sh
set -eu
if [ "${HUB_MODE:-0}" = 1 ]; then
  n=0
  while [ ! -s "$HUB_SECRET_FILE" ]; do
    n=$((n + 1)); [ "$n" -lt 90 ] || exit 1; sleep 1
  done
fi
cd /nas-tools
exec python3 hub_server.py
