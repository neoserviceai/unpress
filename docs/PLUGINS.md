# Plugins

How a capability gets added to an Unpress site, switched off without losing
anything, and — for the ones that are whole Frappe apps — installed and removed.

This replaces the speculative parts of [PLUGIN-SPEC.md](PLUGIN-SPEC.md), which
described a format before any of it existed. What follows is what the code does.

## The one idea

**Frappe has no notion of "installed but off."** `frappe.get_hooks()` is
unconditional: the moment an app is in `installed_apps`, its hooks run, its
routes answer, its assets load, its doctypes exist. The only real switch is
`bench uninstall-app`, and that **drops the module's tables**.

That is the wrong trade for a site owner who wants to hide a feature. Turning
the blog off must not delete the articles.

So a plugin here is not an install. It is a row — `Website Plugin` — that says
*this capability exists on this bench, and the owner wants it on or off*.

## What "off" means, exactly

Three things, and no more:

| Effect | Where |
|---|---|
| The Studio hides its entry | `plugins.get_capabilities()` feeds a `v-if` |
| Its whitelisted endpoints refuse | `plugins.guard("name")` at the top of each |
| The public routes it owns 404 | `plugins.route_guard`, wired to `before_request` |

What it deliberately does **not** do is unload hooks or drop data. A disabled
plugin is dormant, not gone; turning it back on is instant.

Hiding the button is not access control — the endpoint is still reachable by
anyone who knows its name. That is why `guard()` exists and why every entry
point calls it.

## The registry

`Website Plugin`, one row per plugin.

| Field | Meaning |
|---|---|
| `plugin_name` | machine name and primary key |
| `title`, `description`, `icon` | how it presents; **owned by the manifest**, rewritten on every migrate |
| `app_name` | the Frappe app providing it; empty for a data-only plugin |
| `enabled` | **owned by the site**; never touched by a sync |
| `is_available` | whether the app is actually on this bench |
| `is_core` | cannot be turned off |
| `route_prefix` | the public route it owns, used by the route guard and by the site generator |
| `source` | `Built-in` · `Hub` · `Manual` |
| `version` | informational |

Two rules that matter:

- **`is_enabled()` returns `True` when there is no row.** A bench that has not
  migrated yet, or an app installed by hand, keeps working. *The registry takes
  capabilities away; it does not grant them.*
- **`sync_plugins()` rewrites presentation, never the switch.** Run on
  `after_migrate` and on `after_app_install`.

## Level 1 — a capability the bench already carries

The cheapest kind, and the one most "WordPress plugins" actually are.

Add an entry to `BUILT_INS` in `unpress_core/plugins.py`:

```python
{
    "plugin_name": "blog",
    "title": "Blog",
    "description": "Articles, categories and an RSS feed, on /blog.",
    "app_name": "blog",
    "icon": "lucide-newspaper",
    "route_prefix": "blog",
    "is_core": 0,
}
```

Then, in that order:

1. **Guard the endpoints.** At the top of every whitelisted method the plugin
   owns:
   ```python
   from unpress_core import plugins
   plugins.guard("blog")
   ```
   If the endpoints live in another app that must work without us, import
   softly:
   ```python
   try:
       from unpress_core.plugins import guard
   except ImportError:
       return          # no registry on this bench: nothing is gated
   guard("wp_migrator")
   ```
2. **Gate the Studio entry** on the capability, with `!== false` so an unknown
   plugin stays visible:
   ```vue
   <span v-if="capabilities.blog !== false" @click="showBlog = true">…</span>
   ```
3. **Add the labels to `_translatable_labels()`.** The registry stores English
   because a row outlives any one request's language; the labels are wrapped at
   the use site, and gettext cannot see through a variable.

### The route trap

A custom `page_renderer` is tried **before** `ListPage` in frappe's path
resolver. Builder declares one — so a Builder page published at route `blog`
hides the blog app's index completely, and the owner sees an empty section they
just enabled.

`generation.pages_for_site_type()` therefore removes from the plan any route a
**live** plugin serves. Plugin off → the route is free → the page is generated
as before. Give every route-owning plugin a `route_prefix` and this is handled.

### Chrome on pages Builder does not render

A Builder page calls `render_site_header/footer` from its own template. A blog
page, a portal page, `/login` — anything going through frappe's `base.html` —
knows nothing about the site chrome and would look like a different website.

`site_chrome._inject_config_chrome` points `base.html` at two Web Templates
(`Site Header`, `Site Footer`) that carry one call each. Nothing to do per
plugin; it already applies.

If the app ships Bootstrap-shaped markup, dress it from
`public/css/web_pages.css` with selectors scoped to **their** classes. Do not
fork their templates — that is a merge burden forever.

## Level 2 — a plugin that is a whole Frappe app

`unpress_core/plugin_install.py`. Installing means `bench get-app` (git clone +
pip install + yarn build) then `bench install-app` — minutes, not milliseconds,
so it runs as a background job with progress.

### What it costs you to trust

An installed Frappe app has **full server access**: its hooks run on every
request, its code runs as the site user. There is no sandbox and no review.
The guardrails are therefore about who may do it and from where:

- **System Manager only.**
- **The git URL is explicit.** Nothing installs from a name; there is no
  registry of URLs to be tricked into trusting. Local paths and ssh URLs are
  rejected — a path would let a caller point the installer anywhere on disk.
- **`unpress_plugin_sources`** in `site_config.json` pins an allowlist of hosts.
- **`unpress_allow_plugin_install`** turns the whole thing off. It defaults to
  `developer_mode`, so a hosted tenant cannot install anything unless the
  operator says so — which is the right default for a fleet.

### Removing

`bench uninstall-app` **drops the module's tables**. It takes a backup first and
the UI says plainly what it does, but disabling is the answer almost every time
and is what the screen offers first.

The registry row survives removal, marked `is_available = 0`, so the choice and
any hub metadata are still there if the app comes back.

### Two things that will bite

- **Workers hold stale imports.** After installing an app, the running workers
  cannot import it — every job then fails with `ModuleNotFoundError`. The UI
  says to restart them; on the single-container image that is a container
  restart.
- **`job_id` is reserved by `frappe.enqueue`.** It names the RQ job and never
  reaches your function. Our progress key is `progress_id` for that reason.

## Extension points

Two exist today, both the good kind — the host declares itself, the core never
imports the host.

**Registering a plugin.** An installed app contributes its own manifest, so a
third party ships a plugin without us shipping anything:

```python
# in your app's hooks.py
unpress_plugins = ["my_app.plugin.manifest"]
```

A manifest that raises, or that omits `plugin_name`, is skipped with an Error
Log rather than taking the whole registry down: one bad app must not stop the
others from appearing. A name already taken by a built-in is refused — an app
does not get to rename the blog.

See [PLUGIN-TUTORIAL.md](PLUGIN-TUTORIAL.md) to write one.

**Contributing to the AI prompt.**

```python
# in your app's hooks.py
unpress_ai_prompt_context = ["my_app.ai_context.contribute"]

def contribute(site_type: str | None = None) -> str:
    return "## My shortcodes\n..."
```

`frappe.get_attr` refuses anything outside an installed app, so a stale entry
can only log a warning.

More hooks should be designed deliberately rather than accreted. If you need
one, say what it is for before adding it.

## What does not exist yet

Named so nobody looks for it:

- **The community hub.** The registry has `source`, `version` and room for hub
  metadata, and `builder_hub` already distributes template bundles in both
  directions. What is missing is author/licence/version metadata, a package
  format, and a browse screen.
- **A package format.** There is no zip container. Everything is a directory
  tree or JSON over HTTP, which is why "download a plugin, edit it, re-upload"
  is not possible today.
- **Level-1 plugins as data.** Components and templates travelling as a bundle
  rather than as an app — the lowest-risk kind, and the one the hub should
  carry first.
- **A browse/install screen.** Registering works; discovering does not. You
  distribute a plugin yourself today, with a git URL.
- **Any audit of level-2 apps.** Installing one is trusting its author with the
  server. Treat the allowlist as the control until that changes.

## Checklist for a new plugin

- [ ] `BUILT_INS` entry, with `route_prefix` if it serves public routes
- [ ] `plugins.guard()` at every whitelisted entry point
- [ ] `v-if="capabilities.x !== false"` on its Studio entry
- [ ] Labels in `_translatable_labels()`, and the French in `locale/fr.po`
- [ ] If it has web views: check they wear the site chrome, and scope any CSS
      to its own classes
- [ ] If it owns a route the generator plans: confirm the page is skipped when
      the plugin is on
- [ ] Turn it off and confirm — entry gone, endpoint refuses, route 404s,
      **and nothing was lost when you turned it back on**
