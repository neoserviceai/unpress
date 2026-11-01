# unpress_hello — a plugin you can read in one sitting

A working Unpress plugin, deliberately small. It adds one public page, one
Studio-guarded endpoint, and one contribution to the AI's prompt — which is
every extension point Unpress has today. Copy it, rename it, delete what you
do not need.

**It is a normal Frappe app.** There is no Unpress-specific packaging: if you
can write a Frappe app, you can write a plugin. What makes it a *plugin* is
that it declares itself to the registry and asks permission before doing
anything.

```
unpress_hello/
├── hooks.py              ← declares the app to Frappe and to Unpress
├── modules.txt           ← required: bench ignores an app without it
├── patches.txt           ← required: both sections, even empty
├── plugin.py             ← the registry entry + the guard
├── api.py                ← a whitelisted endpoint, guarded
├── ai_context.py         ← what the AI should know about this plugin
├── www/hello.py|html     ← a public page that wears the site chrome
└── public/css/hello.css  ← its own styles, scoped to its own classes
```

> `modules.txt` and `patches.txt` are not decoration. Bench decides whether a
> directory is a Frappe app by looking for `hooks.py`, `modules.txt` **and**
> `patches.txt`; miss one and `bench get-app` clones your repo, pip-installs
> it, and then leaves it out of `sites/apps.txt` — so `install-app` fails with
> `App <name> not in apps.txt` and nothing explains why. `bench new-app`
> writes all three for you; a hand-built plugin has to remember.

## Install it

```bash
bench get-app https://github.com/you/unpress_hello
bench --site your.site install-app unpress_hello
bench --site your.site migrate
```

Then in the Studio: **Réglages → Extensions**. It is on by default — a plugin
that ships with a bench starts enabled; the owner turns it *off*, they should
not have to turn it on to get what they installed.

## Try the switch

Turn it off in the Studio, then:

- `/hello` answers **404** — the route guard
- the API refuses with a `PermissionError` — the endpoint guard
- its entry disappears from the Studio
- **nothing is deleted.** Turn it back on: the page and its data are there.

That last line is the whole point. See `docs/PLUGINS.md` in Unpress for why
"off" cannot be `bench uninstall-app`.
