# Copyright (c) 2026, Neoservice and contributors
# For license information, please see license.txt

"""Per-website-profile header/footer configuration (multi-site hosts).

One document per secondary Website Profile. Shares every field and rendering
helper with the global "Website Header Footer Config" Single (subclass), so
templates can consume either transparently. The default site keeps using the
Single — resolution happens in unpress_core.hf_utils.header_footer.
"""

from unpress_core.unpress_core.doctype.website_header_footer_config.website_header_footer_config import (
	WebsiteHeaderFooterConfig,
)


class WebsiteHeaderFooterVariant(WebsiteHeaderFooterConfig):
	def on_update(self):
		# Unlike the Single, a variant never syncs menu_items into Website
		# Settings top_bar_items (that belongs to the default site) — it only
		# invalidates the rendered-page caches so its site refreshes.
		self.clear_website_cache()
