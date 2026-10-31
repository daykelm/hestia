#!/bin/sh
# One command ships the website, a new WebView APK when that shell changed, and an over-the-air update for the native app when mobile/ changed.
# Touches only the hestia compose project on the Umbrel; checks the Bitcoin node and pool are left running.
set -eu
cd "$(dirname "$0")"
UMBREL="umbrel@192.168.68.78"
SSH="ssh -i $HOME/.ssh/waeking_umbrel"

echo "1/5 tests"
python3 -m unittest -q test_deals

echo "2/5 android app"
if python3 android/version.py changed; then
  if [ -f static/hestia.apk ]; then
    echo "   app source changed, version $(python3 android/version.py bump)"
  fi
  ./android/build.sh
  python3 android/version.py record
else
  echo "   unchanged, keeping version $(python3 -c 'import json;print(json.load(open("static/app-version.json"))["version_code"])')"
fi

echo "3/5 upload"
rsync -a -e "$SSH" app.py deals.py sources.py diligence.py history.py Dockerfile docker-compose.yml .dockerignore "$UMBREL:hestia/"
rsync -a --delete -e "$SSH" static/ "$UMBREL:hestia/static/"

echo "4/5 restart hestia"
$SSH "$UMBREL" 'set -e
cd ~/hestia
before=$(pgrep -x bitcoind; pgrep -x ckpool || true)
docker compose up -d --build hestia 2>&1 | tail -1
if [ -f tunnel.env ]; then docker compose --profile tunnel up -d tunnel 2>&1 | tail -1; fi
code=000
for i in $(seq 1 15); do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18080/ || true)
  [ "$code" = 200 ] && break
  sleep 1
done
after=$(pgrep -x bitcoind; pgrep -x ckpool || true)
[ "$before" = "$after" ] && echo "   bitcoind and ckpool untouched" || { echo "   WARNING: node or pool process changed"; exit 1; }
[ "$code" = 200 ] && echo "   site answers 200" || { echo "   site answered $code"; exit 1; }'

if curl -s -m 10 -o /dev/null -w "%{http_code}" https://hestia.trading/ 2>/dev/null | grep -qE '^(200|302|403)$'; then
  echo "   hestia.trading reachable"
fi

echo "5/5 native app"
sum=$(cd mobile && find src assets app.json package.json -type f | sort | xargs shasum | shasum | cut -c1-40)
if [ "$sum" = "$(cat mobile/.published 2>/dev/null || true)" ]; then
  echo "   unchanged"
else
  eas=$(command -v eas || echo "npx --yes eas-cli")
  if (cd mobile && $eas update --channel production --environment production --platform android \
    --non-interactive --message "$(git log -1 --format=%s 2>/dev/null || echo deploy)" > /tmp/hestia-eas-update.log 2>&1); then
    echo "$sum" > mobile/.published
    echo "   published over the air"
  else
    tail -15 /tmp/hestia-eas-update.log
    echo "   update failed, see /tmp/hestia-eas-update.log"
    exit 1
  fi
fi
echo "done"
