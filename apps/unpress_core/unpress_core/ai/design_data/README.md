# Vendored: UI/UX Pro Max design intelligence

Source: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
Vendored: 2026-07-18, upstream commit `f8ac5e1266dba8354ea96e19994d9f4345e7ec31` (MIT — see LICENSE).

What we take:

- `data/*.csv` — the design database: 84 UI styles, 192 product-aligned color
  palettes, font pairings, chart types, UX guidelines/anti-patterns, and the
  161 industry reasoning rules.
- `scripts/core.py|search.py|design_system.py|validate_data.py` — the BM25
  search engine and design-system generator (Python stdlib only, no deps).

What we intentionally leave out:

- `data/stacks/` (per-framework guidance: React, Flutter…) — we generate
  Builder blocks, not framework code. `search_stack()` therefore fails here;
  nothing in unpress_core calls it.
- Platform templates, CLI installer, tests.

How it is consumed: `unpress_core.ai.design_intelligence` shells out to
`scripts/search.py <query> --domain <d> --json` (subprocess keeps the vendored
code untouched and avoids importing generic module names like `core` into the
frappe process). Results are injected as CANDIDATES into the design-brief
prompt — the LLM picks and adapts, it never copies blindly.

Updating: re-copy the same files from upstream, rerun
`python3 scripts/validate_data.py`, update the commit hash above.
