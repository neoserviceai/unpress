#!/bin/bash
# Unpress single-site entrypoint: configure hosts, create the site on first
# boot, then serve. Idempotent — safe across restarts and version updates.
set -euo pipefail

SITE="${UNPRESS_SITE:-unpress.localhost}"
ADMIN_PASSWORD="${UNPRESS_ADMIN_PASSWORD:-}"
DB_HOST="${UNPRESS_DB_HOST:-mariadb}"
DB_ROOT_PASSWORD="${UNPRESS_DB_ROOT_PASSWORD:-unpress}"
REDIS_HOST="${UNPRESS_REDIS_HOST:-redis}"

cd /home/frappe/frappe-bench

bench set-config -g db_host "$DB_HOST"
bench set-config -g redis_cache "redis://${REDIS_HOST}-cache:6379"
bench set-config -g redis_queue "redis://${REDIS_HOST}-queue:6379"
bench set-config -g redis_socketio "redis://${REDIS_HOST}-queue:6379"

# wait for the database
until mysqladmin ping -h "$DB_HOST" -p"$DB_ROOT_PASSWORD" --silent 2>/dev/null; do
	echo "[unpress] waiting for database at $DB_HOST..."
	sleep 3
done

if [ ! -d "sites/$SITE" ]; then
	if [ -z "$ADMIN_PASSWORD" ]; then
		ADMIN_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)
		GENERATED=1
	fi
	echo "[unpress] creating site $SITE..."
	bench new-site "$SITE" \
		--mariadb-root-password "$DB_ROOT_PASSWORD" \
		--admin-password "$ADMIN_PASSWORD" \
		--mariadb-user-host-login-scope=%
	bench --site "$SITE" install-app builder
	bench --site "$SITE" install-app wp_migrator
	bench --site "$SITE" install-app unpress_core
# a plugin: installed so it exists, on or off from the Studio
bench --site "$SITE" install-app blog
	# headless setup wizard: the Studio user must never meet the Frappe desk
	# onboarding. Language/locale overridable via UNPRESS_LANGUAGE etc.
	bench --site "$SITE" execute frappe.desk.page.setup_wizard.setup_wizard.setup_complete \
		--kwargs "{'args': {'language': '${UNPRESS_LANGUAGE:-English}', 'country': '${UNPRESS_COUNTRY:-Switzerland}', 'timezone': '${UNPRESS_TIMEZONE:-Europe/Zurich}', 'currency': '${UNPRESS_CURRENCY:-CHF}', 'full_name': 'Site Owner', 'email': 'owner@${SITE}', 'password': '$ADMIN_PASSWORD'}}" || true
	bench use "$SITE"
	# frappe v16's `bench use` no longer writes currentsite.txt, but host
	# resolution needs it: without it http://localhost:8080 (any host that is
	# not the site name) is a 404. One site per container -> pin it.
	echo "$SITE" > sites/currentsite.txt
	if [ "${GENERATED:-0}" = "1" ]; then
		echo "=============================================================="
		echo "[unpress] Administrator password (SAVE THIS): $ADMIN_PASSWORD"
		echo "=============================================================="
	fi
else
	bench use "$SITE"
	echo "$SITE" > sites/currentsite.txt
	echo "[unpress] site $SITE exists — running migrations..."
	bench --site "$SITE" migrate || echo "[unpress] migrate failed (continuing with existing schema)"
fi

# The public address. Frappe builds every absolute URL — canonical tags, the
# sitemap, og:url, links inside mail — from the request it happens to see, and
# behind the tls proxy that request is plain http on the container's own port
# 8000. Without this the sitemap advertises `http://example.com:8000/contact`:
# wrong scheme, and an internal port that answers to nobody on the internet.
# `host_name` overrides both. Re-applied on every boot, so changing the domain
# in .env and restarting is enough.
if [ -n "${UNPRESS_DOMAIN:-}" ]; then
	PUBLIC_URL="https://${UNPRESS_DOMAIN}"
else
	# No domain: the site is reached through the published port, which is not
	# the port gunicorn listens on.
	PUBLIC_URL="http://${SITE}:${UNPRESS_HTTP_PORT:-8080}"
fi
# Also writes a robots.txt naming the sitemap, but only while there is none —
# an owner who wrote their own keeps it. See unpress_core/site_url.py.
bench --site "$SITE" execute unpress_core.site_url.apply_public_url \
	--kwargs "{'public_url': '$PUBLIC_URL'}" || \
	echo "[unpress] could not set the public URL (continuing)"
echo "[unpress] public URL: $PUBLIC_URL"

echo "[unpress] starting (Procfile.prod: gunicorn + socketio + scheduler + worker)..."
exec bench start
