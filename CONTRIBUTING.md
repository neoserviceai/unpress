# Contributing

Unpress is a Frappe bench with four apps on it. If you can write a Frappe app,
you can change anything here.

## Get a bench you can break

```bash
git clone https://github.com/neoserviceai/unpress
cd unpress/docker/dev16
docker compose up -d
```

That gives you the Studio on `http://unpress16.localhost:8016/builder` with the
apps mounted from your checkout, so an edit is live on the next request —
except for `hooks.py` and anything Python outside it, which need a restart:

```bash
docker compose exec bench bench restart
```

Prefer your own machine to a container? [INSTALL-BARE-METAL.md](docs/INSTALL-BARE-METAL.md)
lists what a bench needs.

## Run the tests

```bash
docker compose exec bench bench --site unpress16.localhost set-config allow_tests true
docker compose exec bench bench --site unpress16.localhost run-tests --app unpress_core
```

CI runs the same suite inside the image it is about to publish, and refuses to
publish if it fails. A pull request that leaves it red will not merge.

If you delete a test, say in the commit message what happened to its subject.
This suite once rotted for months because nothing ran it; the repair had to
prove, symbol by symbol, that what it tested no longer existed.

## What good change looks like

**Comments say why, not what.** The code already says what. A comment earns its
place by recording the thing the next reader cannot see: what broke, what was
measured, what was tried and rejected.

**Claims come with measurements.** "Faster", "cleaner", "more reliable" are
hypotheses until something is counted. Put the number in the commit message.

**User-facing strings are translatable** — `_()` in Python, `__()` in
JavaScript — and French translations live in `locale/fr.po`. Never in
`translations/*.csv`: Frappe loads PO first, so a fix made only in the CSV is
silently ignored.

**Comments and identifiers are in English**, whatever language the discussion
happened in.

## Plugins rather than patches

If you are adding a capability rather than fixing the engine, write a plugin —
it survives updates, and the site owner can switch it off.
[PLUGIN-TUTORIAL.md](docs/PLUGIN-TUTORIAL.md) goes from nothing to a working
one, and [`examples/unpress_hello`](examples/unpress_hello) is the same thing
already written.

## Reporting a bug

What you did, what happened, what you expected. Include the site's Frappe
version (`bench version`) and whether you run the image or your own bench —
several defects only appear in one of the two. If the browser is involved, the
console and the network tab usually hold the answer.

Security issues: [SECURITY.md](SECURITY.md), not the issue tracker.

## Licence

Unpress is AGPL-3.0. Contributions are accepted under the same terms. The
plugin example is MIT, deliberately: it is a scaffold to copy, and your plugin's
licence is yours to pick.
