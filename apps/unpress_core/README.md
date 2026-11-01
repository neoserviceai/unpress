# unpress_core

Unpress core services. First brick: the **static exporter** — renders every
published page of the site to a self-contained static bundle that deploys
anywhere (Cloudflare Pages, Vercel, shared hosting via SSH/FTP, any web
server). See `docs/ARCHITECTURE.md` (Studio ≠ Site).

Usage (dev):

```bash
bench --site unpress.localhost execute unpress_core.exporter.export_site
# → sites/unpress.localhost/private/static-export/dist/
```

Forms on static sites post to a configurable endpoint (Unpress Forms) — no
PHP is ever shipped in the bundle.
