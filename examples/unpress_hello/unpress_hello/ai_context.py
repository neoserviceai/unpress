"""What the AI is told about this plugin when it writes a page.

Contributed through the `unpress_ai_prompt_context` hook. Keep it short and
concrete: this text is spent from the same budget as the design brief, and a
paragraph of prose buys nothing that an example does not.
"""

from .plugin import is_enabled


def contribute(site_type: str | None = None) -> str:
	"""Return Markdown for the page-generation prompt, or nothing.

	Returning "" when the plugin is off matters: otherwise the AI writes a page
	around a shortcode whose route 404s, and the page ships broken.
	"""
	if not is_enabled():
		return ""

	return (
		"## Hello plugin\n"
		"- Greeting block: `{% include \"unpress_hello/templates/greeting.html\" %}`\n"
		"  Put it in a full-width `<section>`, never inside a grid or flex row.\n"
	)
