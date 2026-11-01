# wp_migrator

Frappe app: WordPress → Unpress importer.

Pipeline (see Unpress vault note 04 for the full design):

1. **Probe** a WordPress URL (public, no auth): detect WP, count content,
   detect the page builder and form provider, show a capability table.
2. **Acquire**: WXR upload (Tools → Export) → full `_elementor_data`;
   later: "Unpress Exporter" WP plugin with a migration key (EmDash pattern).
3. **Convert**: Elementor tree → Builder blocks tree (mechanical for core
   widgets, tagged `data-unpress-todo` placeholders for unknown ones —
   nothing silently dropped); Gutenberg/classic HTML → simple blocks.
4. **Media**: download from source, dedupe by content hash, rewrite URLs.
5. **Finish**: menus → header/footer config, SEO metas, redirect map,
   idempotent re-runs keyed by WordPress IDs.

Current state (pre-alpha): standalone converter modules, proven on a real
production site (391 widgets, 92% converted mechanically —
"A propos" page 100%, home 25/27). No Frappe wiring yet.

- `wp_migrator/converter/elementor.py` — tree-to-tree converter prototype
- `wp_migrator/converter/inventory.py` — WXR widget inventory/quoting tool
