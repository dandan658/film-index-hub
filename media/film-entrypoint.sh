#!/bin/sh
set -eu
# Never allow upstream git-reset to undo this media-only profile.
export NASTOOL_AUTO_UPDATE=false
exec /nas-tools/docker/entrypoint.sh "$@"
