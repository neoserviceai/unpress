#!/bin/bash
# Publish a Studio site's static export into a mutualized site's webroot.
#   sudo bash publish-site.sh <slug> [studio-site]
set -euo pipefail

SLUG="${1:?usage: publish-site.sh <slug> [studio-site]}"
STUDIO_SITE="${2:-unpress.localhost}"
SITES_ROOT="${UNPRESS_SITES_ROOT:-/var/www/sites}"
COMPOSE_DIR="${UNPRESS_COMPOSE_DIR:-$HOME/GitHub/unpress/docker/dev16}"
WEBROOT="$SITES_ROOT/$SLUG"

cd "$COMPOSE_DIR"
echo "[publish] exporting $STUDIO_SITE..."
docker compose exec -T bench bash -c \
	"cd /home/frappe/workspace/frappe-bench && bench --site $STUDIO_SITE execute unpress_core.exporter.export_site" \
	| tail -1

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
docker compose cp "bench:/home/frappe/workspace/frappe-bench/sites/$STUDIO_SITE/private/static-export/dist/." "$TMP/" > /dev/null
sudo mkdir -p "$WEBROOT"
sudo rsync -a --delete "$TMP/" "$WEBROOT/"
# static files served by the caddy user — ensure world-readable/traversable
sudo chmod -R a+rX "$WEBROOT"
echo "[publish] $(sudo find "$WEBROOT" -name index.html | wc -l | tr -d ' ') pages -> $WEBROOT"
