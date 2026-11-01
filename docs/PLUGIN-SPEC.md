# Unpress Plugin & Store Standard — draft 0.1 (2026-07-10)

> [!note]
> **Superseded in part.** What is built is documented in
> [PLUGINS.md](PLUGINS.md): the registry, the three effects of switching a
> plugin off, and installing a level-2 app from a git URL. This file remains
> the record of the *store* design — manifest, curation, audited publishing —
> none of which is code yet.

Goal: WordPress-grade extensibility ("install a feature in two clicks from a
store") on Frappe foundations, without repeating the WordPress security
story. Inspired by the EmDash marketplace (manifest + AI-audited publishing +
plugin CLI) and by what Frappe already provides (apps, hooks, fixtures).

## Two plugin levels (deliberately distinct)

### Level 1 — Components & Templates (Builder data, no code)

Design-level extensions: reusable sections, widgets recreated from Elementor,
page templates, full themes.

- **What they are**: JSON payloads (`builder_component`, `block_template`,
  Builder Page templates, variables/fonts) — pure data.
- **Install**: insert documents. No restart, no migration, instantly
  available in the editor. Uninstall = delete.
- **Security**: near-zero risk (no server code; client scripts sandboxed by
  review policy).
- **Infrastructure**: the Builder fork's template hub with staged publishing
  (staging → promote) already implements distribution. The store wraps it.
- This level covers the majority of "WordPress plugin" use cases for
  brochure sites (galleries, pricing sections, sliders, hero variants...).

### Level 2 — Apps (Frappe apps, server code)

Functional extensions: advanced forms, booking, SEO pack, analytics,
real-estate listings, e-commerce bridge...

- **What they are**: standard Frappe apps (`hooks.py`, doctypes, APIs) with a
  Unpress manifest on top.
- **Install**: orchestrated `bench get-app (pinned ref) && install-app &&
  migrate && restart`, driven from the Unpress admin UI by a store agent
  inside the container. Only store-listed, version-pinned sources — no
  arbitrary git URLs in the UI (power users keep the bench CLI).
- **Security reality check**: a Frappe app has full server access — there is
  no EmDash-style capability sandbox. Mitigations, in order:
  1. **Curated store**: publishing pipeline with automated audit (static
     checks + AI code review — EmDash pattern) and human review for
     first-party listing.
  2. **Declared permissions in the manifest** (informative at install time:
     "this app sends email, calls external APIs, reads all content") — shown
     to the user, enforced by review policy, not by runtime. Honest label,
     not a sandbox.
  3. Version pinning + signed index; updates re-audited.
  4. (Later, research) runtime hardening via Frappe permission hooks /
     restricted service users for store apps.

## The manifest — `unpress.json`

One file at plugin root, both levels:

```json
{
  "id": "realestate-listings",
  "level": "app",                          // "app" | "component" | "template" | "theme"
  "name": "Real Estate Listings",
  "description": "Property collection, grid sections, detail pages.",
  "version": "1.2.0",
  "license": "AGPL-3.0",
  "author": { "name": "Neoservice", "url": "https://unpress.cloud" },
  "compat": { "unpress": ">=0.1", "builder": ">=1.28" },
  "permissions": ["content:read", "content:write", "email:send"],
  "provides": { "doctypes": ["Property"], "components": ["property-grid"] },
  "source": { "git": "https://github.com/unpress-store/realestate-listings", "ref": "v1.2.0" },
  "screenshots": ["assets/grid.png"]
}
```

## The store

- **Index**: a signed JSON catalog (this repo's `store/index.json` to start;
  a dedicated registry service later). The Studio ships with the official
  index; additional indexes can be added explicitly (like F-Droid repos).
- **Client**: store page in the Unpress admin — browse, screenshots,
  permissions display, install/update/remove. Level 1 installs are instant;
  level 2 installs show the permission summary and run the orchestrated
  bench flow.
- **Publishing pipeline** (later phase): submit → automated audit (lint,
  dependency scan, AI code review — EmDash does this on Workers AI) → human
  approval → signed index update.
- **Monetization-ready**: manifest supports `pricing` later (free now;
  paid plugins/themes are a natural revenue stream alongside the managed
  edition).

## Non-goals (v1)

- No decentralized registry (EmDash uses atproto — interesting, not now).
- No runtime capability sandbox (be honest about it; curate instead).
- No WordPress plugin compatibility layer (we migrate *sites*, not plugins).
