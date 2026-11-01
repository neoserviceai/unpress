#!/bin/bash
# Per-tenant provisioner for the Unpress mutualized edition — the Unpress
# equivalent of a per-bench provisioner, but based on native Frappe
# multi-site (1 Frappe site per client = isolated DB + own Builder Pages),
# not on a proprietary Website Profile.
#
# Creates a Frappe site in the shared Studio bench, installs the Unpress apps,
# and provisions the client's static webroot + Caddy vhost.
#
#   bash add-unpress-site.sh <slug> [display-name]
set -euo pipefail

SLUG="${1:?usage: add-unpress-site.sh <slug> [display-name]}"
NAME="${2:-$SLUG}"
COMPOSE_DIR="${UNPRESS_COMPOSE_DIR:-$HOME/GitHub/unpress/docker/dev16}"
DB_ROOT="${UNPRESS_DB_ROOT_PASSWORD:-unpress}"
FRAPPE_SITE="$SLUG.studio.localhost"

[[ "$SLUG" =~ ^[a-z0-9][a-z0-9-]{1,40}$ ]] || { echo "invalid slug: $SLUG"; exit 1; }

cd "$COMPOSE_DIR"

if docker compose exec -T bench bash -c "test -d /home/frappe/workspace/frappe-bench/sites/$FRAPPE_SITE"; then
	echo "[tenant] Frappe site $FRAPPE_SITE already exists"
else
	echo "[tenant] creating Frappe site $FRAPPE_SITE (isolated DB)..."
	ADMIN_PW=$(openssl rand -base64 15 | tr -d '/+=' | head -c 16)
	docker compose exec -T bench bash -c "cd /home/frappe/workspace/frappe-bench && \
		bench new-site $FRAPPE_SITE --mariadb-root-password $DB_ROOT --admin-password $ADMIN_PW --mariadb-user-host-login-scope=% && \
		bench --site $FRAPPE_SITE install-app builder && \
		bench --site $FRAPPE_SITE install-app unpress_core && \
		bench --site $FRAPPE_SITE set-config developer_mode 1 && \
		bench --site $FRAPPE_SITE set-config mute_emails 1 && \
		bench --site $FRAPPE_SITE execute frappe.desk.page.setup_wizard.setup_wizard.setup_complete \
			--kwargs \"{'args': {'language': '${UNPRESS_SITE_LANGUAGE:-Français}', 'country': 'Switzerland', 'timezone': 'Europe/Zurich', 'currency': 'CHF', 'full_name': 'Site Owner', 'email': 'owner@$FRAPPE_SITE', 'password': '$ADMIN_PW'}}\" || true"
	echo "[tenant] admin password for $FRAPPE_SITE: $ADMIN_PW"
fi

# ensure a per-site SSO secret (only generate if absent — keeps links valid)
HAS_SECRET=$(docker compose exec -T bench bash -c "cd /home/frappe/workspace/frappe-bench && bench --site $FRAPPE_SITE execute frappe.client.get_value --kwargs \"{'doctype':'x'}\" 2>/dev/null; python3 -c \"import json;print(json.load(open('sites/$FRAPPE_SITE/site_config.json')).get('unpress_sso_secret',''))\"" | tr -d '[:space:]')
if [ -z "$HAS_SECRET" ]; then
	SSO_SECRET=$(openssl rand -hex 24)
	docker compose exec -T bench bash -c "cd /home/frappe/workspace/frappe-bench && bench --site $FRAPPE_SITE set-config unpress_sso_secret $SSO_SECRET"
fi

# edit access: no per-client vhost needed — the *.studio.unpress.cloud
# wildcard block proxies <slug>.studio.unpress.cloud to the multi-tenant
# gunicorn with the right Host header, TLS included.
EDIT_DOMAIN="$SLUG.studio.${UNPRESS_BASE_DOMAIN:-unpress.cloud}"
echo "[tenant] edit Studio at https://$EDIT_DOMAIN/builder"

# static webroot + Caddy vhost + TLS
sudo bash "$(dirname "$0")/provision-site.sh" "$SLUG" "$NAME"

echo "[tenant] done: edit at Frappe site $FRAPPE_SITE, publish -> $SLUG.sites.unpress.cloud"
echo "[tenant] first publish: bash $(dirname "$0")/publish-site.sh $SLUG $FRAPPE_SITE"
