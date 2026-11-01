#!/bin/bash
# Generate a short-lived SSO login link for a tenant's Studio (the portal's job).
#   bash edit-link.sh <slug>
set -euo pipefail
SLUG="${1:?usage: edit-link.sh <slug>}"
COMPOSE_DIR="${UNPRESS_COMPOSE_DIR:-$HOME/GitHub/unpress/docker/dev16}"
FRAPPE_SITE="$SLUG.studio.localhost"
EDIT_DOMAIN="$SLUG.studio.${UNPRESS_BASE_DOMAIN:-unpress.cloud}"
cd "$COMPOSE_DIR"
docker compose exec -T bench bash -c "cd /home/frappe/workspace/frappe-bench && bench --site $FRAPPE_SITE execute unpress_core.sso.make_login_url --kwargs \"{'base_url': 'https://$EDIT_DOMAIN'}\"" | tr -d '"' | tail -1
