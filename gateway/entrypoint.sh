#!/bin/sh
set -eu
n=0
while [ ! -s "$HUB_SECRET_FILE" ]; do
  n=$((n + 1)); [ "$n" -lt 90 ] || exit 1; sleep 1
done
export HUB_SHARED_SECRET="$(cat "$HUB_SECRET_FILE")"
export NGINX_ENVSUBST_FILTER='^HUB_SHARED_SECRET$'
exec /docker-entrypoint.sh nginx -g 'daemon off;'
