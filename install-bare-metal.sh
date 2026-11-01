#!/bin/bash
# Unpress installer — your own machine, your own packages, no containers.
#
#   curl -fsSL https://raw.githubusercontent.com/neoserviceai/unpress/main/install-bare-metal.sh | bash
#
# Does what docker/single/Dockerfile does, on the machine you are sitting at:
# system packages, a bench, four apps, a site, and the site told where it is
# published.
#
# Tested on Ubuntu 24.04 and 26.04. The two need different things in three
# places, so the script asks the machine rather than assuming — see
# `prepare_system`.
#
# It will install system packages. If you manage those yourself:
#   UNPRESS_NO_SYSTEM_PACKAGES=1 ./install-bare-metal.sh
# and it will check for what it needs instead, and stop with the list.
set -euo pipefail

BENCH_DIR="${UNPRESS_BENCH_DIR:-unpress-bench}"
SITE="${UNPRESS_SITE:-unpress.localhost}"
PUBLIC_URL="${UNPRESS_PUBLIC_URL:-}"
FRAPPE_BRANCH="${UNPRESS_FRAPPE_BRANCH:-version-16}"
BUILDER_REPO="${UNPRESS_BUILDER_REPO:-https://github.com/neoserviceai/builder}"
BUILDER_BRANCH="${UNPRESS_BUILDER_BRANCH:-unpress}"
BLOG_REPO="${UNPRESS_BLOG_REPO:-https://github.com/neoserviceai/blog}"
BLOG_BRANCH="${UNPRESS_BLOG_BRANCH:-version-16}"
UNPRESS_REPO="${UNPRESS_REPO:-https://github.com/neoserviceai/unpress}"
DB_ROOT_PASSWORD="${UNPRESS_DB_ROOT_PASSWORD:-}"
DB_PASSWORD_FILE="${UNPRESS_DB_PASSWORD_FILE:-$HOME/.unpress-db-root-password}"

say()  { printf "\033[1;36m[unpress]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[unpress]\033[0m %s\n" "$*"; }
fail() { printf "\033[1;31m[unpress]\033[0m %s\n" "$*" >&2; exit 1; }

# ── what machine is this ──────────────────────────────────────────────────
# /etc/os-release, not `lsb_release`: on the Infomaniak 26.04 image
# `lsb_release -ds` answers "Ubuntu 24.04.4 LTS" while os-release correctly
# says 26.04. One of them is generated at build time and left stale.
OS_ID=""; OS_VERSION=""; OS_CODENAME=""
if [ -r /etc/os-release ]; then
	# shellcheck disable=SC1091
	. /etc/os-release
	OS_ID="${ID:-}"; OS_VERSION="${VERSION_ID:-}"; OS_CODENAME="${VERSION_CODENAME:-}"
fi

# ── system packages ───────────────────────────────────────────────────────
prepare_system() {
	[ "$OS_ID" = "ubuntu" ] || [ "$OS_ID" = "debian" ] || \
		fail "automatic preparation only knows Ubuntu and Debian (found: ${OS_ID:-unknown}).
Install the prerequisites yourself, then re-run with UNPRESS_NO_SYSTEM_PACKAGES=1.
The list is in docs/INSTALL-BARE-METAL.md."

	say "preparing $PRETTY_NAME"
	export DEBIAN_FRONTEND=noninteractive
	wait_for_apt
	sudo apt-get update -qq
	# Node is handled separately below — asking apt for `npm` here would make
	# this whole line unsatisfiable on a machine that already has NodeSource
	# node: the archive's npm depends on the archive's nodejs, and the two
	# cannot coexist. That is not hypothetical, it is what a re-run after a
	# partial failure looks like: "you have held broken packages".
	sudo apt-get install -y -qq \
		git curl build-essential pkg-config \
		python3-dev python3-venv python3-pip pipx \
		redis-server mariadb-server libmariadb-dev \
		xvfb libfontconfig

	prepare_node

	# The editor's lockfile is yarn 1. Ubuntu packages yarn 4 under the name
	# `yarnpkg`, which resolves that lockfile differently — so take yarn 1 from
	# npm and leave the distribution's alone.
	command -v yarn > /dev/null 2>&1 || sudo npm install -g yarn@1.22.22 > /dev/null

	# `pip install frappe-bench` is refused on anything recent: the system
	# python is externally managed (PEP 668). pipx is the supported route.
	command -v bench > /dev/null 2>&1 || pipx install frappe-bench > /dev/null
	pipx ensurepath > /dev/null 2>&1 || true
	export PATH="$HOME/.local/bin:$PATH"

	# bench 5.31 builds the virtualenv with uv and does not declare it: without
	# it `bench init` dies on `FileNotFoundError: 'uv'` after cloning frappe.
	command -v uv > /dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null 2>&1

	prepare_wkhtmltopdf
	prepare_mariadb
}

# Set by ensure_python; passed to `bench init`.
PYTHON_BIN=""

ensure_python() {
	# frappe declares `requires-python = ">=3.14,<3.15"` — not a floor, a
	# window. 26.04 ships 3.14 and needs nothing; 24.04 ships 3.12 and cannot
	# run frappe at all with its own python: `uv pip install` refuses with
	# "the current Python version (3.12.3) does not satisfy Python>=3.14,<3.15".
	#
	# uv is already required for `bench init`, and it can fetch a standalone
	# 3.14 — so the machine keeps its own python untouched and the bench gets
	# the one frappe wants.
	if python3 -c 'import sys; sys.exit(0 if (3,14) <= sys.version_info < (3,15) else 1)' 2>/dev/null; then
		PYTHON_BIN="$(command -v python3)"
		return
	fi

	say "frappe wants python 3.14; this machine has $(python3 -V 2>&1 | awk '{print $2}') — fetching one with uv"
	uv python install 3.14 > /dev/null 2>&1 || fail "could not install python 3.14 with uv"
	PYTHON_BIN="$(uv python find 3.14 2>/dev/null)"
	[ -x "$PYTHON_BIN" ] || fail "uv installed python 3.14 but did not say where"
	say "using $PYTHON_BIN"
}

NODE_MAJOR_REQUIRED=24

prepare_node() {
	# frappe-framework's package.json declares `"node": ">=24"`, and yarn
	# enforces it: `bench init` gets as far as cloning frappe and then stops on
	# "The engine node is incompatible with this module. Expected >=24."
	#
	# No Ubuntu ships it — 24.04 has 18, 26.04 has 22 — so NodeSource is not an
	# optimisation here, it is the only way through. The published image runs 24
	# for the same reason.
	local node_major
	node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"

	if [ "$node_major" -lt "$NODE_MAJOR_REQUIRED" ]; then
		say "node ${node_major:-none} is below $NODE_MAJOR_REQUIRED — installing from NodeSource"
		curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR_REQUIRED}.x" | sudo -E bash - > /dev/null
		# NodeSource's package brings its own npm; asking apt for the archive's
		# makes the transaction unsatisfiable.
		sudo apt-get install -y -qq nodejs
	fi

	command -v npm > /dev/null 2>&1 || sudo apt-get install -y -qq npm

	node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
	[ "$node_major" -ge "$NODE_MAJOR_REQUIRED" ] || \
		fail "node $node_major is still below $NODE_MAJOR_REQUIRED — frappe's build will refuse"
}

wait_for_apt() {
	# A cloud image runs unattended-upgrades on boot, so apt is often busy for
	# the first minute or two of a machine's life — and `apt-get` does not wait,
	# it exits 100 with "Unable to acquire the dpkg frontend lock". Failing an
	# install because the machine was still booting is not a real failure.
	local waited=0
	while sudo fuser /var/lib/dpkg/lock-frontend /var/lib/apt/lists/lock > /dev/null 2>&1; do
		[ "$waited" = "0" ] && say "waiting for another apt to finish"
		sleep 5
		waited=$((waited + 5))
		[ "$waited" -ge 600 ] && fail "apt has been locked for 10 minutes — is an upgrade running?"
	done
}

prepare_wkhtmltopdf() {
	if command -v wkhtmltopdf > /dev/null 2>&1 && wkhtmltopdf --version 2>&1 | grep -q "patched qt"; then
		return
	fi
	# Not in the archives of any recent Ubuntu — `apt-cache policy wkhtmltopdf`
	# answers `Candidate: (none)` on both 24.04 and 26.04. The plain build that
	# some guides suggest lays PDFs out wrong, so take the patched-qt package
	# from upstream. There is no build past jammy; it runs fine on both.
	say "installing wkhtmltopdf (patched qt) from upstream packaging"
	local v=0.12.6.1-3 tmp
	tmp="$(mktemp -d)"
	for codename in "$OS_CODENAME" noble jammy; do
		[ -n "$codename" ] || continue
		if curl -fsSLo "$tmp/wk.deb" \
			"https://github.com/wkhtmltopdf/packaging/releases/download/${v}/wkhtmltox_${v}.${codename}_amd64.deb" 2>/dev/null; then
			sudo apt-get install -y -qq "$tmp/wk.deb" && break
		fi
	done
	rm -rf "$tmp"
	command -v wkhtmltopdf > /dev/null 2>&1 || warn "wkhtmltopdf missing — PDFs will not render"
}

prepare_mariadb() {
	# Frappe's collation. Without it, site creation fails on the first
	# non-ASCII character it stores.
	if [ ! -f /etc/mysql/mariadb.conf.d/60-unpress.cnf ]; then
		sudo tee /etc/mysql/mariadb.conf.d/60-unpress.cnf > /dev/null <<-'CNF'
			[mysqld]
			character-set-client-handshake = FALSE
			character-set-server = utf8mb4
			collation-server = utf8mb4_unicode_ci
		CNF
		sudo systemctl restart mariadb
	fi

	# A fresh MariaDB authenticates root through the unix socket, which bench
	# cannot use — it wants a password. Set one if the caller did not.
	[ -n "$DB_ROOT_PASSWORD" ] && return

	# A password we generated on an earlier run. It lives outside the bench
	# directory on purpose: a retry deletes the bench, and a script that
	# forgets the password it set locks itself out of its own database.
	if [ -r "$DB_PASSWORD_FILE" ]; then
		DB_ROOT_PASSWORD="$(cat "$DB_PASSWORD_FILE")"
		return
	fi

	# Socket authentication is how a fresh MariaDB lets root in. Where it no
	# longer works, root has a password that is the operator's — not ours to
	# guess, and not ours to reset.
	if ! sudo mysql -e "SELECT 1" > /dev/null 2>&1; then
		fail "MariaDB root already has a password, and this script did not set it.
Re-run with it:  UNPRESS_DB_ROOT_PASSWORD='…' $0"
	fi

	DB_ROOT_PASSWORD="$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)"
	sudo mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED VIA mysql_native_password USING PASSWORD('$DB_ROOT_PASSWORD'); FLUSH PRIVILEGES;"
	( umask 077; printf '%s\n' "$DB_ROOT_PASSWORD" > "$DB_PASSWORD_FILE" )
	say "MariaDB root password set (kept in $DB_PASSWORD_FILE)"
}

check_system() {
	local missing=()
	for cmd in git python3 node yarn redis-server bench uv; do
		command -v "$cmd" > /dev/null 2>&1 || missing+=("$cmd")
	done
	command -v mysql > /dev/null 2>&1 || command -v mariadb > /dev/null 2>&1 || missing+=("mariadb-server")
	command -v wkhtmltopdf > /dev/null 2>&1 || missing+=("wkhtmltopdf (the patched-qt build)")

	if [ ${#missing[@]} -gt 0 ]; then
		printf "\033[1;31m[unpress]\033[0m missing, install these first:\n" >&2
		printf "  - %s\n" "${missing[@]}" >&2
		printf "\nOr drop UNPRESS_NO_SYSTEM_PACKAGES and let the script install them.\n" >&2
		printf "The full list is in docs/INSTALL-BARE-METAL.md.\n" >&2
		exit 1
	fi
}

export PATH="$HOME/.local/bin:$PATH"
if [ "${UNPRESS_NO_SYSTEM_PACKAGES:-0}" = "1" ]; then
	check_system
else
	prepare_system
fi

ensure_python

[ -e "$BENCH_DIR" ] && fail "$BENCH_DIR already exists — remove it or set UNPRESS_BENCH_DIR"

# ── the bench ─────────────────────────────────────────────────────────────
say "creating the bench (this compiles wheels — several minutes)"
bench init --frappe-branch "$FRAPPE_BRANCH" --python "$PYTHON_BIN" "$BENCH_DIR"
cd "$BENCH_DIR"

say "fetching the editor"
bench get-app "$BUILDER_REPO" --branch "$BUILDER_BRANCH"

say "fetching the blog"
bench get-app "$BLOG_REPO" --branch "$BLOG_BRANCH"

# unpress_core and wp_migrator live inside one repository rather than each
# having their own — and `bench get-app <path>` cannot take them: it runs git
# on the directory it is given, and a subdirectory of a repository is not a
# repository. It fails with `InvalidGitRepositoryError` after everything else
# has already been built.
#
# So do what the Dockerfile does: copy the app in, install it editable, and
# register it. `bench install-app` then finds it like any other.
say "fetching the engine"
git clone --depth 1 "$UNPRESS_REPO" ../unpress-src

install_local_app() {
	local src="$1" name
	name="$(basename "$src")"
	rm -rf "apps/$name"
	cp -R "$src" "apps/$name"
	./env/bin/pip install --quiet -e "apps/$name"
	# apps.txt is read line by line, and bench writes it without a trailing
	# newline. Appending blind glues the new name onto the last one.
	[ -s sites/apps.txt ] && [ -n "$(tail -c 1 sites/apps.txt)" ] && printf '\n' >> sites/apps.txt
	grep -qx "$name" sites/apps.txt 2>/dev/null || printf '%s\n' "$name" >> sites/apps.txt
	mkdir -p sites/assets
	ln -sfn "../../apps/$name/$name/public" "sites/assets/$name"
}

install_local_app ../unpress-src/apps/unpress_core
install_local_app ../unpress-src/apps/wp_migrator

# The editor's front end is not committed; the published image builds it too.
#
# Node sizes its heap from the memory it can see, so on a 2 GB machine it caps
# itself around 1 GB and aborts — `FATAL ERROR: Ineffective mark-compacts near
# heap limit`, exit 134 — without ever touching the swap. Raising the cap is
# what lets it spill instead of dying. 4096 is what the fleet already uses for
# `bench build`.
say "building the editor front end"
(cd apps/builder/frontend && yarn install --silent && NODE_OPTIONS=--max-old-space-size=4096 yarn build)

# ── the site ──────────────────────────────────────────────────────────────
ADMIN_PASSWORD="${UNPRESS_ADMIN_PASSWORD:-$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)}"

say "creating the site $SITE"
if [ -n "$DB_ROOT_PASSWORD" ]; then
	bench new-site "$SITE" --admin-password "$ADMIN_PASSWORD" --mariadb-root-password "$DB_ROOT_PASSWORD" --mariadb-user-host-login-scope=%
else
	bench new-site "$SITE" --admin-password "$ADMIN_PASSWORD"
fi
for app in builder wp_migrator unpress_core blog; do
	bench --site "$SITE" install-app "$app"
done
bench use "$SITE"

# Frappe v16's `bench use` no longer writes currentsite.txt, and host
# resolution needs it: without it, any host that is not the site name is a 404.
echo "$SITE" > sites/currentsite.txt

# The Studio user must never meet the Frappe desk onboarding.
bench --site "$SITE" execute frappe.desk.page.setup_wizard.setup_wizard.setup_complete \
	--kwargs "{'args': {'language': '${UNPRESS_LANGUAGE:-English}', 'country': '${UNPRESS_COUNTRY:-Switzerland}', 'timezone': '${UNPRESS_TIMEZONE:-Europe/Zurich}', 'currency': '${UNPRESS_CURRENCY:-CHF}', 'full_name': 'Site Owner', 'email': 'owner@${SITE}', 'password': '$ADMIN_PASSWORD'}}" > /dev/null 2>&1 || true

# ── where it is published ─────────────────────────────────────────────────
# The step people skip, and the one that costs the most. Frappe builds every
# absolute URL — canonical tags, the sitemap, og:url, links inside mail — from
# the request it happens to see. Behind a reverse proxy that request is plain
# HTTP on an internal port, so without this the sitemap advertises
# `http://your.site:8000/contact`: wrong scheme, and a port nobody can reach.
if [ -z "$PUBLIC_URL" ]; then
	PUBLIC_URL="http://${SITE}:8000"
	say "no UNPRESS_PUBLIC_URL given — assuming $PUBLIC_URL"
	say "  behind a proxy or a domain, re-run:"
	say "  bench --site $SITE execute unpress_core.site_url.apply_public_url --kwargs \"{'public_url': 'https://your.domain'}\""
fi
bench --site "$SITE" execute unpress_core.site_url.apply_public_url \
	--kwargs "{'public_url': '$PUBLIC_URL'}" > /dev/null

say "done!"
say "  Start it:  cd $BENCH_DIR && bench start"
say "  Site:      $PUBLIC_URL"
say "  Studio:    $PUBLIC_URL/builder"
say "  Login:     Administrator / $ADMIN_PASSWORD"
say ""
say "For a real deployment rather than \`bench start\`:"
say "  sudo bench setup production \$USER && sudo bench setup lets-encrypt $SITE"
