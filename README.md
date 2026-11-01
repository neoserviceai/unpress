# Unpress

**A real alternative to WordPress + Elementor** — a visual drag & drop website builder with built-in WordPress/Elementor migration, powered by [Frappe](https://frappe.io) and [Frappe Builder](https://github.com/frappe/builder).

> Status: pre-alpha, under active construction.

## Install (single-site, Docker)

```bash
curl -fsSL https://raw.githubusercontent.com/neoserviceai/unpress/main/install.sh | bash
```

Requires Docker with the compose plugin. The installer creates `./unpress/`,
generates credentials (shown at the end and stored in `.env`), and boots the
stack. First boot creates your site (~2 min), then:

- Studio: `http://unpress.localhost:8080/builder` — log in as `Administrator`
  (`*.localhost` resolves natively in modern browsers, no hosts-file edit)
- Import a WordPress site: `/studio-import` (URL probe → import → editable pages)
- Generate a site with AI: `/studio-chat` — configure your API key first in
  Studio > Settings > AI (Moonshot recommended; OpenAI/OpenRouter/Ollama/custom
  also supported). No server config needed.
- Public TLS: set `UNPRESS_DOMAIN` in `.env`, point your DNS at the machine
  (both `example.com` and `www.example.com`), then
  `docker compose --profile tls up -d`. Caddy obtains the certificates,
  redirects `www` to the apex, and the site is told its own public address —
  which is what makes canonical tags, the sitemap and links in mail come out
  as `https://example.com/...` instead of the container's internal port.

Frappe is the engine, not the interface: everything happens in the Studio
(`/builder`), the desk is never part of the flow.

The engine image is built with `scripts/build-image.sh` (bench + Builder +
Unpress apps baked in).

## Why

- **Your clients edit their site themselves** (real visual builder) but cannot break it: no plugin updates, no PHP vulnerabilities, no maintenance burden.
- **One-click migration from WordPress**: probe a URL, import content, media, menus and SEO — and convert Elementor layouts tree-to-tree into editable Builder blocks (not frozen HTML).
- **Publish anywhere**: the published site is exported as a static bundle that runs on any host — Vercel/Cloudflare Pages/GitHub Pages (free), classic shared hosting (Infomaniak, FTP/SSH), or served dynamically by the Unpress server itself.
- **AI-native**: site generation, content ingestion and visual verification loops built on the Builder fork's AI layer.

## Architecture (short version)

```
┌─────────────────────────────┐   publish    ┌──────────────────────────────┐
│  Unpress Studio (Docker)    │ ───────────► │  Static site bundle          │
│  Frappe + Builder + Import  │              │  → Vercel / CF Pages (free)  │
│  runs locally or on a VPS   │              │  → Infomaniak / any FTP      │
└─────────────────────────────┘              │  → GitHub Pages              │
        │                                    └──────────────────────────────┘
        └── or keep it online and serve the site dynamically (classic mode)
```

Two deployment modes for the published site:

1. **Static export (default for cheap/free hosting)** — the editor runs only when you edit (local Docker) and pushes a static bundle to your host. Forms post to **Unpress Forms** (hosted endpoint, free tier) or any custom endpoint URL you configure — no PHP, ever.
2. **Dynamic (classic)** — the Unpress server stays online (VPS/self-host) and serves the site itself: live forms, search, dynamic content.

Prefer your own server, your own packages? There is an installer for that too:

```bash
curl -fsSL https://raw.githubusercontent.com/neoserviceai/unpress/main/install-bare-metal.sh | bash
```

It checks what your machine is missing and stops with the list rather than
failing halfway. [docs/INSTALL-BARE-METAL.md](docs/INSTALL-BARE-METAL.md)
explains each step if you would rather run them yourself.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and
[docs/AI-WIZARD.md](docs/AI-WIZARD.md) for what the AI reads from the client
(logo → brand colours, references, photos and documents) and how a host app
extends its prompt. Hosted and self-hosted share **one** code path: what a
site can do is a server answer, never a component fork.

## Build on it

A plugin is a normal Frappe app that declares itself and asks permission — no
Unpress packaging, no build step. Start with
[docs/PLUGIN-TUTORIAL.md](docs/PLUGIN-TUTORIAL.md), copy
[examples/unpress_hello](examples/unpress_hello) if you would rather read
working code, and see [docs/PLUGINS.md](docs/PLUGINS.md) for why "off" is a
registry row rather than `bench uninstall-app` — turning the blog off must not
delete the articles.

For what is deliberately **not** built yet — a media library, and plugins with
a community hub — see
[docs/ROADMAP-MEDIA-ET-COMMUNAUTE.md](docs/ROADMAP-MEDIA-ET-COMMUNAUTE.md): it
states what exists today and what each piece would cost.

## Repository layout

```
apps/unpress_core/   Frappe app: AI site generation (chat, brief, pages, validators),
                     site chrome (header/footer/theme), static export, SSO, Studio settings
apps/wp_migrator/    Frappe app: WordPress/Elementor importer (WXR parser + tree-to-tree converter)
docker/              Docker packaging (single-container install + dev composes)
docs/                Architecture and specs (hosting model, plugin/store standard)
store/               Unpress store index (apps + Builder components/templates) — draft
```

The visual editor itself is [our Builder fork](https://github.com/neoserviceai/builder)
(branch `unpress` = upstream develop + a thin Unpress layer: site-chrome hooks,
AI settings tab, one-interface cleanups). Unpress runs on **frappe 16 only**.
The `version-15` branch of that repository is a different product on a different
frappe; the Studio never runs on it.

## License

AGPL-3.0 (aligned with Frappe Builder). See [docs/PLUGINS.md](docs/PLUGINS.md) and [docs/PLUGIN-SPEC.md](docs/PLUGIN-SPEC.md) for the store/plugin licensing model.
