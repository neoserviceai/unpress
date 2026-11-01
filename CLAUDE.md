# Working in this repository

Unpress is a Frappe bench with four apps on it. This file is the map; the
reasoning lives in `docs/`.

## What is where

```
apps/unpress_core/     the engine: AI generation, site chrome, plugins, themes
apps/wp_migrator/      WordPress/Elementor import
apps/unpress_cloud_api/  provisioning API for the managed edition
docker/single/         the published image + its compose stack
docker/dev16/          the development bench
examples/unpress_hello/  a plugin you can read in one sitting
internal/              never ships — see internal/README.md
```

Two apps are **not** here and are fetched at build time:

| App | Where | Branch |
|---|---|---|
| `builder` | `neoserviceai/builder`, our fork of `frappe/builder` | `unpress` |
| `blog` | `neoserviceai/blog`, our fork of `frappe/blog` | `version-16` |

The editor's front end lives in the Builder fork, not in this repository. A
change to the Studio UI is a commit there, then a rebuild here.

## Installing it elsewhere

Two installers, and they must stay in step with `docker/single/Dockerfile`,
which is the executable truth — every published image is built from it.

| | |
|---|---|
| `install.sh` | containers: pulls the published image, boots the stack |
| `install-bare-metal.sh` | your own machine: bench, four apps, site, public URL |

A change to the app list, a branch or a repository has to land in all three.

## Running it

```bash
cd docker/dev16 && docker compose up -d      # Studio on :8016/builder
docker compose exec bench bench restart      # after any Python change
```

Assets under `public/` are served immediately — `sites/assets/<app>` is a
symlink. `hooks.py` and everything else Python needs the restart; clearing the
cache is not enough, and the page will keep serving the old version while you
wonder why.

Only one heavy operation at a time in the container. Two concurrent `yarn build`
runs wedge the Docker daemon.

## Tests

```bash
docker compose exec bench bench --site unpress16.localhost set-config allow_tests true
docker compose exec bench bench --site unpress16.localhost run-tests --app unpress_core
```

CI runs the same suite **inside the image it is about to publish**, and refuses
to publish if it fails. That gate exists because the suite once rotted for
months: nothing ran it, so nothing said so.

## Conventions

- **Comments and identifiers in English**, whatever language the discussion
  happened in. Comments say *why*; the code already says what.
- **User-facing strings are translatable** — `_()` in Python, `__()` in JS.
- **French translations go in `locale/fr.po`, never `translations/*.csv`.**
  Frappe loads PO first, so a fix made only in the CSV is silently ignored.
- **`frappe.log_error(title, message)`** — title first, 140 characters max.
  A single long f-string gets truncated exactly where the useful part was.
- **Capability is a server answer, never a fork of a component.** What an
  install can do is decided server-side and rendered; there is no second copy
  of a screen for a second kind of deployment.

## Things that have cost time

Each of these is written up where it belongs; this is the index.

- `web_include_css` never reaches Builder-rendered pages. The site chrome ships
  its CSS inline for that reason.
- A prompt rule placed in the user message loses against the JSON example in
  the system prompt. Structural rules go last, in the system prompt.
- `frappe.db.has_column()` takes a **doctype**, not a table name, and raises on
  a doctype with no table. A patch that raises aborts the whole migration.
- A Single doctype has no table: its values live in `tabSingles`, and a `Check`
  that was never written reads `0` — indistinguishable from a deliberate off.
- bench recognises an app by **three** files: `hooks.py`, `modules.txt`,
  `patches.txt`. Miss one and `get-app` clones it, pip installs it, then
  `install-app` fails with a message about `apps.txt` that names no cause.
- Absolute URLs — canonical, sitemap, mail — come from the request the server
  sees, which behind a proxy is plain HTTP on an internal port. Hence
  `unpress_core/site_url.py`.
