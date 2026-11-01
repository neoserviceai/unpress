# Security

## Reporting

Report privately through GitHub's
[security advisories](https://github.com/neoserviceai/unpress/security/advisories/new),
never in a public issue. We answer within a few working days, and we will tell
you plainly whether we consider it a vulnerability and when a fix will land.
Credit in the advisory if you want it.

## What Unpress is, in security terms

A Frappe site. Its permissions, sessions and CSRF handling are Frappe's, and a
vulnerability in that layer belongs upstream at
[frappe/frappe](https://github.com/frappe/frappe/security).

Three things are ours and worth aiming at:

**Plugin installation.** Installing a plugin puts a Frappe app on the bench:
its code runs as the site user, its hooks run on every request. There is no
sandbox and no review — installing one is trusting its author with the server.
Which is why it is off unless `developer_mode` is on, only a System Manager can
call it, the git URL is explicit, and a site can pin an allowlist
(`unpress_plugin_sources`) or refuse installs entirely
(`unpress_allow_plugin_install: 0`). That is the right default for a hosted
fleet, where the operator decides what runs, not the tenant.

**Generated pages.** The AI writes HTML that lands on a public site. Blocks are
sanitised before they are stored, and the generation prompt is not a place to
put anything the site owner should not be able to publish. A hole here is a
stored-XSS hole; we want to hear about it.

**The Codex provider.** It runs an agent on the server, so every invocation is
sandboxed, non-interactive, given a throwaway working directory, and killed on
a timeout — the reasoning is written at the top of
`unpress_core/ai/providers/codex_provider.py`. If you can make it act on
content it merely read, that is a finding.

## Out of scope

- Attacks needing an Administrator account. Administrator can already run code
  on a Frappe site; that is the design, not a flaw.
- A publicly reachable bench in `developer_mode`. Don't.
- Missing hardening headers on a site behind your own proxy, where you set them.

## Supported versions

Unpress is pre-1.0. Only `main` and the current `:latest` image get fixes.
