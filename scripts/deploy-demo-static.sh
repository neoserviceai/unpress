#!/bin/bash
# Deploy the static export of the Studio's published site to the local
# static vhost (served by Caddy). First deploy adapter: "local directory".
# Run ON the server: bash GitHub/unpress/scripts/deploy-demo-static.sh
set -euo pipefail

COMPOSE_DIR="$HOME/GitHub/unpress/docker/dev16"
WEBROOT="/var/www/demo"
SITE="unpress.localhost"

cd "$COMPOSE_DIR"

echo "[deploy] exporting static bundle..."
docker compose exec -T bench bash -c \
	"cd /home/frappe/workspace/frappe-bench && bench --site $SITE execute unpress_core.exporter.export_site" \
	| tail -3

echo "[deploy] copying bundle to $WEBROOT..."
sudo mkdir -p "$WEBROOT"
TMP=$(mktemp -d)
docker compose cp "bench:/home/frappe/workspace/frappe-bench/sites/$SITE/private/static-export/dist/." "$TMP/"
sudo rsync -a --delete "$TMP/" "$WEBROOT/"
sudo chown -R caddy:caddy "$WEBROOT" 2>/dev/null || sudo chown -R www-data:www-data "$WEBROOT" 2>/dev/null || true
rm -rf "$TMP"

echo "[deploy] done: $(sudo find $WEBROOT -name index.html | wc -l) pages in $WEBROOT"
