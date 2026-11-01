# Write a plugin

From nothing to a working plugin. Read [PLUGINS.md](PLUGINS.md) for *why* the
design is what it is; this page is *how*.

A ready-made version of everything below lives in
[`examples/unpress_hello`](../examples/unpress_hello) — clone it and rename if
you would rather start from working code.

---

## What a plugin is

**A normal Frappe app.** There is no Unpress packaging, no manifest file, no
build step. If you can write a Frappe app, you can write a plugin.

What makes it a plugin is two habits:

1. it **declares itself** through a hook, so the site owner sees it and can
   switch it off;
2. it **asks permission** before doing anything, so switching it off actually
   switches it off.

Everything else is your app.

---

## 1. Create the app

```bash
bench new-app my_plugin
bench --site your.site install-app my_plugin
```

Use `bench new-app` even if you plan to delete most of what it writes. Bench
decides whether a directory is a Frappe app by looking for three files —
`hooks.py`, `modules.txt` **and** `patches.txt` — and it says nothing when one
is missing. What you get instead, much later, is `bench get-app` cloning your
repo and pip-installing it, then `install-app` failing with
`App my_plugin not in apps.txt`: the app was silently left out of
`sites/apps.txt` because bench never counted it as an app. `patches.txt` may be
empty, but both of its section headers have to be there.

## 2. Declare it

Two files. First the registry entry:

```python
# my_plugin/plugin.py
import frappe
from frappe import _

PLUGIN_NAME = "my_plugin"        # stable: renaming it makes every site forget
                                 # whether the owner had turned it off

def manifest() -> dict:
    return {
        "plugin_name": PLUGIN_NAME,
        "title": _("My Plugin"),
        "description": _("What it does, in one line."),
        "app_name": "my_plugin",
        "icon": "lucide-puzzle",       # see the note below before changing it
        "route_prefix": "my-plugin",   # omit if it serves no public route
    }
```

Then the hook:

```python
# my_plugin/hooks.py
unpress_plugins = ["my_plugin.plugin.manifest"]
```

`bench migrate` (or installing the app) makes it appear in
**Réglages → Extensions**, on by default.

> `icon` is a wish, not a guarantee. The Studio compiles its icon CSS by
> scanning its own source, so a lucide name that appears nowhere in it has no
> rule behind it. Your entry then shows the puzzle piece rather than an empty
> square — which is the Studio being honest, not ignoring you. Leave it at
> `lucide-puzzle` unless you know the name is already bundled.

> A plugin that ships with a bench starts **enabled**. The owner turns it off;
> they should not have to hunt for a checkbox to get what they just installed.

## 3. Ask permission

Add this to `plugin.py`:

```python
def is_enabled() -> bool:
    # The registry answers to two package names: `unpress_core` on Unpress,
    # and `builder` on builds that carry it inside the Builder app itself.
    # Same code, two import paths. Try only one and your plugin will believe
    # it is always enabled on the other.
    for module in ("unpress_core.plugins", "builder.plugins"):
        try:
            registry = frappe.get_module(module)
        except Exception:
            continue
        return bool(registry.is_enabled(PLUGIN_NAME))
    return True      # plain Frappe bench: the app works on its own


def guard() -> None:
    if not is_enabled():
        frappe.throw(_("This plugin is turned off."), frappe.PermissionError)
```

Now call `guard()` **first** in every whitelisted method:

```python
# my_plugin/api.py
@frappe.whitelist()
def do_something(payload: str = ""):
    guard()                      # before validation, before anything
    ...
```

> Guard before validating arguments. An endpoint that validates and *then*
> refuses still tells a caller whether their input was well-formed.

## 4. Serve a page (optional)

```python
# my_plugin/www/my-plugin.py
def get_context(context):
    if not is_enabled():
        raise frappe.DoesNotExistError
    context.no_cache = 1
    return context
```

```jinja
{# my_plugin/www/my-plugin.html #}
{% extends "templates/web.html" %}
{% block page_content %}
  ...
{% endblock %}
```

Extending `templates/web.html` is what wraps your page in the site's header,
footer and page header. A plugin page that builds its own `<html>` reads as a
different website.

The `route_prefix` in your manifest makes the whole prefix **404** when the
plugin is off — you get that for free.

## 5. Teach the AI about it (optional)

If your plugin offers something the site's AI could use when it writes pages:

```python
# my_plugin/hooks.py
unpress_ai_prompt_context = ["my_plugin.ai_context.contribute"]
```

```python
# my_plugin/ai_context.py
def contribute(site_type: str | None = None) -> str:
    if not is_enabled():
        return ""        # otherwise the AI builds a page around a dead route
    return "## My plugin\n- Block: `{% include \"my_plugin/templates/x.html\" %}`\n"
```

Keep it short and concrete. This text is spent from the same budget as the
design brief, and a paragraph of prose buys nothing an example does not.

## 6. Style it

```python
web_include_css = "/assets/my_plugin/css/my_plugin.css"
```

Scope **everything** to your own classes, and consume the theme's tokens rather
than fixed values:

```css
.my-plugin__card {
    background: var(--surface-color);
    border-radius: var(--radius, 8px);
    max-width: var(--container-width, 1280px);
}
```

A plugin that styles `.card`, `h2` or `.btn` will collide with the site's theme
somewhere, and the owner will have no idea which app did it.

---

## Before you ship

- [ ] `guard()` at **every** whitelisted entry point
- [ ] `route_prefix` set if you serve public routes
- [ ] `is_enabled()` tries **both** package names
- [ ] AI context returns `""` when the plugin is off
- [ ] CSS scoped to your own classes, tokens rather than fixed values
- [ ] Labels wrapped in `_()`, French in `locale/fr.po`
- [ ] Web pages extend `templates/web.html`

And the test that matters, run it for real:

> Turn the plugin **off** in the Studio. Whatever it added to the interface is
> gone, its endpoints refuse, its routes 404, and its AI context is empty. Turn
> it back **on**: everything returns and **nothing was lost**.

Its row in **Extensions** stays either way, switch flipped — that is the switch
you need to turn it back on.

That last clause is the whole design. Off is not `bench uninstall-app`, which
drops your module's tables. See [PLUGINS.md](PLUGINS.md#the-one-idea).

---

## Two traps, both found the hard way

**Importing one edition only.** `from unpress_core import plugins` raises
`ImportError` wherever the registry ships under the `builder` package instead,
and a `try/except` around it makes your plugin believe it is always enabled. Its
endpoints then keep answering after the owner switched it off. Try both module
names.

**Assuming "off" is handled for you.** The registry withdraws your capability
from the Studio and blocks your `route_prefix`. It cannot know about your
endpoints, your scheduled jobs or your document hooks — those are yours to
guard.

---

## What does not exist yet

- **No hub.** You distribute your plugin yourself: a git URL, a `bench get-app`.
  Browsing and one-click install are coming.
- **No package format.** No zip container; everything is a directory tree.
- **No audit.** Installing a level-2 plugin is trusting its author with the
  server. On a hosted bench, installs are off unless `developer_mode` is on,
  and an allowlist can restrict which sources are accepted.
