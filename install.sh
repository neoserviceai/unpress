#!/bin/bash
# Unpress installer — single-site edition.
#
#   curl -fsSL https://raw.githubusercontent.com/neoserviceai/unpress/main/install.sh | bash
#
# Requires: Docker with the compose plugin. Creates ./unpress/ with a
# compose file, generates credentials, boots the stack.
set -euo pipefail

REPO_RAW="${UNPRESS_REPO_RAW:-https://raw.githubusercontent.com/neoserviceai/unpress/main}"
DIR="${UNPRESS_DIR:-unpress}"

say() { printf "\033[1;36m[unpress]\033[0m %s\n" "$*"; }

command -v docker > /dev/null || { echo "Docker is required: https://docs.docker.com/engine/install/"; exit 1; }
docker compose version > /dev/null 2>&1 || { echo "Docker Compose plugin is required"; exit 1; }

say "setting up in ./$DIR"
mkdir -p "$DIR"
cd "$DIR"

curl -fsSL "$REPO_RAW/docker/single/compose.yaml" -o compose.yaml

if [ ! -f .env ]; then
	ADMIN_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)
	DB_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)
	SITE="${UNPRESS_SITE:-unpress.localhost}"
	cat > .env << ENV
UNPRESS_SITE=$SITE
UNPRESS_ADMIN_PASSWORD=$ADMIN_PASSWORD
UNPRESS_DB_ROOT_PASSWORD=$DB_PASSWORD
# Set your domain and run:  docker compose --profile tls up -d
# UNPRESS_DOMAIN=$SITE
ENV
	say "credentials generated in $DIR/.env"
fi

say "pulling and starting (first boot builds your site — a few minutes)..."
# `up -d` alone reuses whatever `:latest` is already in the local cache, so
# re-running the installer to update silently keeps the old image. Ask for the
# pull explicitly; on a first install it costs nothing.
docker compose pull
docker compose up -d

# shellcheck disable=SC1091
source .env
say "done!"
# *.localhost resolves to 127.0.0.1 in every modern browser — use the site
# hostname, not bare localhost (the editor requires the real site host).
say "  Site:     http://${UNPRESS_SITE}:${UNPRESS_HTTP_PORT:-8080}"
say "  Studio:   http://${UNPRESS_SITE}:${UNPRESS_HTTP_PORT:-8080}/builder"
say "  Login:    Administrator / $UNPRESS_ADMIN_PASSWORD"
say "  Follow:   docker compose logs -f unpress"
say "For public TLS: set UNPRESS_DOMAIN in .env, point DNS here, then: docker compose --profile tls up -d"
