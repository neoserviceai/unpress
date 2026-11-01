#!/bin/bash
# Idempotent bootstrap of the Unpress dev bench inside the frappe/bench image.
# State lives in the bench-data volume; re-running skips completed steps.
#
# Local apps are installed manually (clone/copy + pip -e + apps.txt) because
# `bench get-app <local path>` crashes with "'App' object has no attribute
# 'org'" on local sources (bench bug seen 2026-07).
set -euo pipefail

SITE="${UNPRESS_SITE:-unpress16.localhost}"
FRAPPE_BRANCH="${FRAPPE_BRANCH:-version-16}"
cd /home/frappe/workspace

if [ ! -d frappe-bench/apps/frappe ]; then
	echo "[unpress] bench init (frappe $FRAPPE_BRANCH)..."
	rm -rf frappe-bench  # a failed previous init leaves a partial dir behind
	bench init --skip-redis-config-generation --frappe-branch "$FRAPPE_BRANCH" frappe-bench
fi
cd frappe-bench

bench set-config -g db_host mariadb
bench set-config -g redis_cache redis://redis-cache:6379
bench set-config -g redis_queue redis://redis-queue:6379
bench set-config -g redis_socketio redis://redis-queue:6379

install_local_app() {
	local name="$1" src="$2"
	if [ ! -d "apps/$name" ]; then
		echo "[unpress] installing app $name from $src..."
		if [ -d "$src/.git" ]; then
			git clone --depth 1 "file://$src" "apps/$name"
		else
			cp -a "$src" "apps/$name"
		fi
	fi
	./env/bin/pip install --quiet -e "apps/$name"
}

install_local_app builder /workspace/vendor/builder

# unpress apps: re-synced from the mounted repo on every boot (active development)
for app in wp_migrator unpress_core; do
	echo "[unpress] syncing $app source..."
	rm -rf "apps/$app"
	cp -a "/workspace/unpress/apps/$app" "apps/$app"
	./env/bin/pip install --quiet -e "apps/$app"
done

# apps.txt bookkeeping (normally done by get-app); newline-safe append
python3 - << 'PYEOF'
lines = [l.strip() for l in open('sites/apps.txt').read().splitlines() if l.strip()]
for app in ('builder', 'wp_migrator', 'unpress_core'):
    if app not in lines:
        lines.append(app)
open('sites/apps.txt', 'w').write('\n'.join(lines) + '\n')
PYEOF

if [ ! -d "sites/$SITE" ]; then
	echo "[unpress] new-site $SITE..."
	bench new-site "$SITE" \
		--mariadb-root-password unpress \
		--admin-password admin \
		--mariadb-user-host-login-scope=%
	bench --site "$SITE" set-config developer_mode 1
	bench --site "$SITE" set-config mute_emails 1
	# headless setup wizard so the desk is usable immediately (dev credentials)
	bench --site "$SITE" execute frappe.desk.page.setup_wizard.setup_wizard.setup_complete \
		--kwargs "{'args': {'language': 'English', 'country': 'Switzerland', 'timezone': 'Europe/Zurich', 'currency': 'CHF', 'full_name': 'Dev Admin', 'email': 'dev@unpress.localhost', 'password': 'admin'}}" || true
fi

# idempotent app installs (a failed earlier boot may have left a partial site)
for app in builder wp_migrator unpress_core; do
	if ! bench --site "$SITE" list-apps 2>/dev/null | grep -q "^$app"; then
		echo "[unpress] install-app $app..."
		bench --site "$SITE" install-app "$app"
	fi
done

# upstream builder does not commit the built frontend (the v15 branch did):
# build it once so /builder serves the editor
if [ ! -d apps/builder/builder/public/frontend ]; then
	echo "[unpress] building builder frontend (vite)..."
	(cd apps/builder/frontend && yarn install --silent && yarn build) || echo "[unpress] WARN frontend build failed"
fi

# default site for the dev server
bench use "$SITE"

# asset symlinks so gunicorn/Caddy can serve /assets/<app> (bench build not run)
ln -sfn ../../apps/builder/builder/public sites/assets/builder 2>/dev/null || true
ln -sfn ../../apps/wp_migrator/wp_migrator/public sites/assets/wp_migrator 2>/dev/null || true
ln -sfn ../../apps/unpress_core/unpress_core/public sites/assets/unpress_core 2>/dev/null || true

# Codex CLI: the provider that drives a ChatGPT plan instead of a metered API
# key. The binary has to live INSIDE the container — the Studio runs here, so a
# codex installed on the host Mac is invisible to it. The login itself comes
# from the mounted ~/.codex, so no second pairing.
if ! command -v codex >/dev/null 2>&1; then
	echo "[unpress] installing the Codex CLI..."
	npm install -g @openai/codex >/dev/null 2>&1 \
		&& echo "[unpress] codex $(codex --version 2>/dev/null | head -1)" \
		|| echo "[unpress] WARN codex install failed — the AI tab will report it as not detected"
fi

echo "[unpress] starting bench (http://$SITE:8000, admin/admin)..."
exec bench start
