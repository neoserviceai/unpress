# Unpress Architecture — hosting model

Decided 2026-07-10. The single most important architectural decision of the
open-source edition: **editing and hosting are decoupled**.

## The problem

The editor stack (Frappe: Python workers + MariaDB + Redis + scheduler +
socketio) is a stateful multi-process application. It does NOT run on:

- **Vercel / Netlify** — serverless functions only, no persistent processes,
  no embedded MariaDB/Redis. Definitive no for the editor.
- **Shared web hosting** (Infomaniak Web Hosting, Hostpoint, etc.) — PHP +
  MySQL + at most one managed Node.js app. No Python daemons, no Redis,
  no root. Definitive no for the editor.

But those platforms are exactly where our target users want their site to
live, because they are cheap or free.

## The answer: Studio ≠ Site

```
             ┌──────────────────────────────────────────────┐
             │ Unpress Studio (the editor)                  │
             │ Frappe + Builder fork + wp_migrator + store  │
             │                                              │
             │ Runs on:                                     │
             │  • your machine (Docker, free)               │
             │  • any VPS (~5 CHF/month)                    │
             │  • Unpress managed cloud (the commercial     │
             │    multi-tenant edition)                     │
             └───────────────┬──────────────────────────────┘
                             │ "Publish"
             ┌───────────────▼──────────────────────────────┐
             │ Static site bundle                           │
             │ HTML/CSS/JS + media, sitemap, redirects,     │
             │ optional forms endpoint                      │
             │                                              │
             │ Deploys to:                                  │
             │  • Cloudflare Pages / Vercel / GH Pages: FREE│
             │  • Infomaniak & any shared hosting: SSH/FTP  │
             │  • any web server (nginx/Apache)             │
             └──────────────────────────────────────────────┘
```

### Mode 1 — Static export (default)

The Studio renders every published route server-side (Builder already renders
pages to plain HTML), crawls them, rewrites asset URLs, and produces a
self-contained bundle. Deploy adapters:

| Target | Transport | Cost |
|---|---|---|
| Cloudflare Pages | wrangler / direct upload | free |
| Vercel | vercel deploy | free tier |
| GitHub Pages | git push | free |
| Infomaniak Web Hosting / any shared host | SSH/rsync or FTP | ~7.55 CHF/mo (often already paid) |
| Any server | rsync | — |

Dynamic features under static hosting:

- **Forms**: client-side JS posts to a configurable endpoint URL. Default:
  **Unpress Forms** (`forms.unpress.cloud`, hosted by us — free tier, natural
  bridge to the managed edition; submissions land in the site owner's inbox
  and later in their cloud dashboard). Alternatively any custom endpoint the
  user configures at publish time. Brand principle: **no PHP is ever
  shipped** — the product that frees you from WordPress does not deploy PHP.
- **Search**: pre-built client-side index (lunr-style) generated at publish
  time.
- **Blog/lists**: regenerated on publish (acceptable for brochure sites).

Trade-off: content changes require re-publishing (one click in the Studio;
the Studio does not need to stay online).

### Mode 2 — Dynamic (classic self-host)

The Studio stays online (VPS/Docker) and serves the site itself: live forms
into the database, instant publishing, dynamic content, authenticated pages.
This is also exactly how the commercial multi-tenant edition serves sites.

## Docker packaging (open-source edition)

Two artifacts, same image family:

1. `docker compose up` — multi-container (frappe_docker pattern: app, db,
   redis, websocket, scheduler, nginx). The serious self-host path.
2. `docker run unpress/unpress` — single-container all-in-one (supervisord
   manages mariadb+redis+frappe+nginx). Less orthodox, unbeatable for
   "try it in 60 seconds" and for local-first editing. Data on a volume.

First-run wizard: create admin → choose language → "import from WordPress?"
(URL probe) or "generate with AI" → editing.

## Free-hosting recipes (documented for users)

- **100% free site**: Studio in local Docker + static publish to Cloudflare
  Pages/GitHub Pages. Editor runs only when editing.
- **Swiss shared hosting**: static publish to existing Infomaniak web hosting
  via SSH/FTP adapter, forms posting to Unpress Forms. (An Infomaniak hosting cannot run the
  Studio itself — Python/Redis are not available there.)
- **Always-free VPS-class**: Oracle Cloud Always Free (4 ARM OCPU / 24 GB)
  runs the full Studio in Docker — power users only.
- **Simplest paid**: any 5 CHF/mo VPS, dynamic mode, one-liner install.

## Unpress Desktop (Electron) — decided direction 2026-07-10

The Studio also ships as a desktop app. Two phases:

- **Phase A — Electron shell + containerized engine.** The app manages the
  lifecycle of the local Unpress container (assisted runtime install, start/
  stop/update, volumes, backups), renders the Builder UI in its window, and
  integrates publish connections (Vercel/Cloudflare OAuth tokens, SSH/FTP
  for shared hosting — stored in the OS keychain). Auto-update for both the
  app and the engine image. The Docker image stays the single engine
  artifact across desktop, self-host and managed cloud.
- **Phase B — natively embedded engine (no container).** Only if traction
  justifies it: bundling Python+MariaDB+Redis per-OS is a permanent
  packaging burden (instructive precedent: Frappe Books is Electron but
  deliberately avoids embedding the Frappe framework — Vue+SQLite only;
  Frappe does not support SQLite).

Reality check shown to users: the engine needs a container runtime
(macOS: embeddable Colima/Apple container, assisted; Windows: Docker
Desktop/WSL2 — real friction) and ~1-1.5 GB RAM while editing. With the
static publish model the Studio only runs while you edit.
