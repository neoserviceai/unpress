# Unpress Docker packaging

> **Unpress is frappe 16 only.** There is no version-15 anything here. The
> `version-15` branch of the upstream Builder line belongs to a different
> product on a different frappe; the Studio never runs on it. A v15 dev bench
> lived in `docker/dev/` until 2026-07-31 — removed, do not bring it back.

## `dev16/` — the development bench

A full bench (frappe 16 + builder-unpress + unpress_core + wp_migrator) with
the local repos bind-mounted, bootstrapped by `init-bench.sh` on first boot.

```bash
BUILDER_SRC=~/GitHub/builder-unpress docker compose -f docker/dev16/compose.yaml up -d
# → http://unpress16.localhost:8016   (admin / admin)
```

`init-bench.sh` is idempotent: re-running it skips completed steps, and it
re-syncs `unpress_core` and `wp_migrator` from the mounted repo on every boot.
The builder app is cloned once — push changes to it explicitly.

## `single/` — the published image

The all-in-one image behind the one-liner install: supervisord runs mariadb,
redis, frappe and the web server in a single container, data on a volume.

```bash
UNPRESS_IMAGE=ghcr.io/<org>/unpress:latest docker compose -f docker/single/compose.yaml up -d
```

Built by `.github/workflows/build-image.yml` on every push to `main` that
touches `apps/`, `docker/single/` or the build script. The workflow refuses to
build when the Builder checkout is on `version-15` or the Dockerfile stops
targeting frappe 16 — that pair installs cleanly and then fails at runtime in
ways that look like data corruption.

Local equivalent, same build context, for testing before pushing:

```bash
bash scripts/build-image.sh [--push]
```

The image name follows whichever GitHub org owns the repo, so moving the repo
renames the package with no edit here.
