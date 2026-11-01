#!/bin/bash
# Deploy the static export of the Studio's published site to a remote host
# over SSH/rsync — works with any shared hosting exposing SSH (Infomaniak
# web hostings do), a VPS, or any server.
#
#   bash scripts/deploy-remote.sh user@host /path/to/webroot [port]
#
# Run ON the machine hosting the Studio containers (or adapt COMPOSE_DIR).
set -euo pipefail

TARGET="${1:?usage: deploy-remote.sh user@host /remote/webroot [port]}"
REMOTE_PATH="${2:?usage: deploy-remote.sh user@host /remote/webroot [port]}"
PORT="${3:-22}"
COMPOSE_DIR="${UNPRESS_COMPOSE_DIR:-$HOME/GitHub/unpress/docker/dev16}"
SITE="${UNPRESS_SITE:-unpress.localhost}"

cd "$COMPOSE_DIR"

echo "[deploy] exporting static bundle..."
docker compose exec -T bench bash -c \
	"cd /home/frappe/workspace/frappe-bench && bench --site $SITE execute unpress_core.exporter.export_site" \
	| tail -2

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
docker compose cp "bench:/home/frappe/workspace/frappe-bench/sites/$SITE/private/static-export/dist/." "$TMP/" > /dev/null

echo "[deploy] rsync to $TARGET:$REMOTE_PATH (port $PORT)..."
rsync -az --delete -e "ssh -p $PORT -o StrictHostKeyChecking=accept-new" "$TMP/" "$TARGET:$REMOTE_PATH/"

PAGES=$(find "$TMP" -name index.html | wc -l | tr -d " ")
echo "[deploy] done: $PAGES pages shipped to $TARGET:$REMOTE_PATH"
