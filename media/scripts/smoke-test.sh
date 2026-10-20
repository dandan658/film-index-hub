#!/usr/bin/env bash
set -euo pipefail
image="${1:?image required}"
name=film-index-smoke
cleanup() { docker logs --tail=160 "$name" || true; docker rm -f "$name" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker run -d --name "$name" -p 127.0.0.1:18510:3000 -e NASTOOL_AUTO_UPDATE=false "$image"
ready=0
for attempt in $(seq 1 90); do
  if curl --max-time 5 -fsS http://127.0.0.1:18510/profile-info > /tmp/film-profile.json; then ready=1; break; fi
  sleep 2
done
[[ "$ready" == 1 ]]
curl --max-time 45 -fsS http://127.0.0.1:18510/ > /tmp/film-login.html
grep -q liquid-glass.css /tmp/film-login.html
curl --max-time 60 -fsS -c /tmp/film-cookies -d 'username=admin&password=password&remember=on' http://127.0.0.1:18510/ > /tmp/film-navigation.html
grep -q layout-navbar /tmp/film-navigation.html
for page in mediafile unidentification history tmdbcache service basic users library directorysync notification customwords mediaserver subtitle; do
  curl --max-time 45 -fsS -b /tmp/film-cookies "http://127.0.0.1:18510/$page" > "/tmp/film-$page.html"
  ! grep -q 'name="username"' "/tmp/film-$page.html"
done
for page in indexer downloader download_setting douban filterrule upload; do
  code=$(curl --max-time 10 -s -o /dev/null -w '%{http_code}' -b /tmp/film-cookies "http://127.0.0.1:18510/$page")
  [[ "$code" == 404 ]]
done
curl --max-time 15 -fsS -b /tmp/film-cookies -d 'dir=/tmp&filter=HIDE_FILES_FILTER' http://127.0.0.1:18510/dirlist | grep -q jqueryFileTree
curl --max-time 15 -fsS http://127.0.0.1:18510/static/js/glass-picker.js | grep -q 'fti-picker'
curl --max-time 15 -fsS http://127.0.0.1:18510/static/img/film-index-logo.svg | grep -q '<svg'
curl --max-time 15 -fsS http://127.0.0.1:18510/project-source.zip -o /tmp/film-source.zip
python3 - <<'PY'
import zipfile
with zipfile.ZipFile('/tmp/film-source.zip') as z:
    assert z.testzip() is None
    assert any(n.endswith('liquid-glass.css') for n in z.namelist())
print('PASS: real container starts, admin login, all 13 retained pages and source archive')
PY
