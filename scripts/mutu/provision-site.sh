#!/bin/bash
# Provision a mutualized Unpress site: just a webroot. The Caddy wildcard
# block (*.sites.unpress.cloud, single wildcard certificate via DNS-01) maps
# any subdomain to /var/www/sites/<slug> — no per-site vhost, no caddy
# reload, HTTPS is live instantly. Idempotent.
#
#   sudo bash provision-site.sh <slug> [display-name]
set -euo pipefail

SLUG="${1:?usage: provision-site.sh <slug> [display-name]}"
NAME="${2:-$SLUG}"
BASE_DOMAIN="${UNPRESS_SITES_DOMAIN:-sites.unpress.cloud}"
SITES_ROOT="${UNPRESS_SITES_ROOT:-/var/www/sites}"

[[ "$SLUG" =~ ^[a-z0-9][a-z0-9-]{1,40}$ ]] || { echo "invalid slug: $SLUG"; exit 1; }

WEBROOT="$SITES_ROOT/$SLUG"
DOMAIN="$SLUG.$BASE_DOMAIN"

sudo mkdir -p "$WEBROOT"

# initial landing (a fresh, unedited site) if empty
if [ ! -f "$WEBROOT/index.html" ]; then
	sudo tee "$WEBROOT/index.html" > /dev/null << HTML
<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>$NAME — Unpress</title>
<style>body{margin:0;font-family:system-ui,sans-serif;min-height:100vh;display:grid;place-items:center;
background:linear-gradient(135deg,#f5d0fe,#c7f0ff)}.c{text-align:center;padding:2rem}
h1{font-size:2.4rem;margin:0 0 .5rem}p{color:#444;font-size:1.1rem}
.b{display:inline-block;margin-top:1.5rem;padding:.7rem 1.4rem;background:#6d5cf5;color:#fff;
border-radius:999px;text-decoration:none;font-weight:600}</style></head>
<body><div class="c"><h1>$NAME</h1><p>Votre nouveau site Unpress est prêt.</p>
<a class="b" href="https://studio.unpress.cloud/builder">Commencer à éditer</a></div></body></html>
HTML
fi

echo "[provision] $DOMAIN -> $WEBROOT (HTTPS immediate via wildcard cert)"
