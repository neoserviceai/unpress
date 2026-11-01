"""Frappe reads this file. So does Unpress — for exactly one key."""

app_name = "unpress_hello"
app_title = "Unpress Hello"
app_publisher = "you"
app_description = "An example Unpress plugin."
app_email = "you@example.com"
app_license = "MIT"

# Its own styles, scoped to its own classes. A plugin that restyles `.card` or
# `h2` will fight the site's theme and win somewhere it should not.
web_include_css = "/assets/unpress_hello/css/hello.css"

# ── Unpress ────────────────────────────────────────────────────────────────
# The host declares itself; Unpress never imports this app. An Unpress that is
# not installed simply never reads these keys, and this app keeps working as a
# plain Frappe app.

#: The registry entry. Unpress calls this on migrate and lists what it returns.
unpress_plugins = ["unpress_hello.plugin.manifest"]

#: What the site's AI should know about this plugin when it writes pages —
#: shortcodes it may use, sections it may build. Returns a Markdown string.
unpress_ai_prompt_context = ["unpress_hello.ai_context.contribute"]
