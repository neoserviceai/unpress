# Copyright (c) 2026, Neoservice
# License: AGPL-3.0

import json

import frappe
import requests
from frappe import _
from frappe.model.document import Document

from wp_migrator.converter import elementor
from wp_migrator.converter.live_scrape import scrape_site_logo, scrape_uc_post_grid
from wp_migrator.converter.wxr import parse_wxr

REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (Unpress WP Migrator)"}


class WPMigration(Document):
	def validate(self):
		if self.source_url and not self.source_url.startswith(("http://", "https://")):
			self.source_url = "https://" + self.source_url
		self.source_url = (self.source_url or "").rstrip("/")

	@frappe.whitelist()
	def probe(self):
		"""Probe the source URL: is it WordPress, what content is public,
		which builder/form plugins are detected."""
		url = self.source_url
		results = {"url": url, "is_wordpress": False}

		try:
			# wp-json discovery
			resp = requests.get(f"{url}/wp-json/", headers=REQUEST_HEADERS, timeout=15)
			if resp.ok:
				data = json.loads(resp.text, strict=False)
				results["is_wordpress"] = True
				results["site_name"] = data.get("name", "")
				results["description"] = data.get("description", "")

			# public content counts via REST headers
			counts = {}
			for rest_base in ("pages", "posts", "media"):
				try:
					head = requests.get(
						f"{url}/wp-json/wp/v2/{rest_base}?per_page=1",
						headers=REQUEST_HEADERS,
						timeout=15,
					)
					counts[rest_base] = int(head.headers.get("X-WP-Total", 0))
				except Exception:
					counts[rest_base] = None
			results["counts"] = counts

			# builder / plugin detection from the homepage HTML
			html = requests.get(url, headers=REQUEST_HEADERS, timeout=15).text
			detected = {}
			for marker, label in {
				"elementor": "Elementor",
				"elementor-pro": "Elementor Pro",
				"elementskit": "ElementsKit",
				"unlimited-elements": "Unlimited Elements",
				"metform": "MetForm",
				"wpforms": "WPForms",
				"contact-form-7": "Contact Form 7",
				"wp-content/themes/": "theme",
			}.items():
				if marker in html:
					detected[label] = True
			results["detected"] = sorted(k for k in detected if k != "theme")
			results["uses_elementor"] = "Elementor" in detected

			self.status = "Probed"
			results["next_step"] = _(
				"Upload the WXR export file (WordPress: Tools > Export > All content) "
				"to get Elementor layout data, then run Import."
			)
		except Exception as e:
			results["error"] = str(e)
			self.status = "Failed"

		self.probe_results = json.dumps(results, indent=2, ensure_ascii=False)
		self.save()
		return results

	@frappe.whitelist()
	def start_import(self):
		"""Parse the attached WXR and create Builder Pages (idempotent by route)."""
		if not self.wxr_file:
			frappe.throw(_("Attach a WordPress export file (.xml) first"))

		self.status = "Importing"
		self.save()

		try:
			report = self._run_import()
			self.report = json.dumps(report, indent=2, ensure_ascii=False)
			self.status = "Imported"
		except Exception:
			self.status = "Failed"
			self.report = json.dumps(
				{"error": frappe.get_traceback(with_context=False)[-2000:]}, indent=2
			)
			raise
		finally:
			self.save()

		return json.loads(self.report)

	def _set_progress(self, stage, detail=""):
		"""Persist the current import stage so the wizard UI can poll it."""
		frappe.db.set_value(
			"WP Migration", self.name, "progress",
			json.dumps({"stage": stage, "detail": detail}, ensure_ascii=False),
			update_modified=False,
		)
		frappe.db.commit()

	def _run_import(self):
		self._set_progress(_("Reading the WordPress export"))
		file_doc = frappe.get_doc("File", {"file_url": self.wxr_file})
		xml_text = file_doc.get_content()
		if isinstance(xml_text, bytes):
			xml_text = xml_text.decode("utf-8", errors="replace")

		wxr = parse_wxr(xml_text)

		entries = list(wxr["pages"])
		if self.import_templates:
			entries += wxr["templates"]

		self._set_progress(_("Analyzing the live site"), _("dynamic widgets"))
		self._collect_live_widget_data(entries)

		pages_report = []
		todo_counter = {}

		total = len(entries)
		for idx, entry in enumerate(entries, 1):
			# the detail is a raw progress counter (data, not prose): not translated
			self._set_progress(_("Converting pages"), f"{idx}/{total} — {entry['title'][:40]}")
			if entry["status"] not in ("publish", "draft"):
				continue
			if not entry.get("elementor_data"):
				# Non-Elementor page: plain HTML fallback into a single block
				blocks = [
					elementor.block(
						"div", {"maxWidth": "900px", "margin": "0 auto"},
						inner_html=entry["content_html"], name="imported-html",
					)
				]
			else:
				elementor.stats.clear()
				blocks = [elementor.convert(el) for el in entry["elementor_data"]]
				for key, count in elementor.stats.items():
					if key.startswith("TODO:"):
						todo_counter[key[5:]] = todo_counter.get(key[5:], 0) + count

			fonts = self._collect_fonts(blocks)
			if fonts:
				families = "&family=".join(
					f.replace(" ", "+") + ":wght@400;500;600;700" for f in sorted(fonts)
				)
				blocks.insert(0, elementor.block(
					"style", {},
					inner_html=f"@import url('https://fonts.googleapis.com/css2?family={families}&display=swap');",
					name="imported-fonts",
				))

			root = elementor.block(
				"div",
				{"display": "flex", "flexDirection": "column", "alignItems": "center", "width": "100%"},
				blocks,
				name="root",
			)
			route = entry["slug"] or frappe.scrub(entry["title"])

			existing = frappe.db.get_value("Builder Page", {"route": route}, "name")
			if existing:
				page = frappe.get_doc("Builder Page", existing)
				page.draft_blocks = json.dumps([root])
				page.save()
				action = "updated"
			else:
				page = frappe.get_doc(
					{
						"doctype": "Builder Page",
						"page_title": entry["title"],
						"route": route,
						"draft_blocks": json.dumps([root]),
						"published": 0,
					}
				).insert()
				action = "created"

			if self.publish_pages:
				page.publish()

			pages_report.append(
				{
					"title": entry["title"],
					"route": route,
					"builder_page": page.name,
					"action": action,
					"editor": f"/builder/page/{page.name}",
				}
			)

		frappe.db.commit()

		self._set_progress(_("Linked pages discovered"), _("scraping the live site"))
		discovered = self._import_discovered_pages(pages_report)

		media_report = None
		if self.import_media and pages_report:
			self._set_progress(_("Downloading media"))
			media_report = self._import_referenced_media(pages_report)
			frappe.db.commit()

		self._set_progress(_("Rewriting internal links"))
		links_rewritten = self._relativize_internal_links(pages_report)

		self._set_progress(_("Applying site chrome"), _("menu, logo, footer"))
		chrome_report = self._apply_site_chrome(wxr)
		home_route = self._set_home_page()
		self._set_progress(_("Done"))

		return {
			"discovered_pages": discovered,
			"internal_links_rewritten": links_rewritten,
			"site_chrome": chrome_report,
			"home_page": home_route,
			"site": wxr["site"],
			"pages_imported": len(pages_report),
			"pages": pages_report,
			"attachments_found": len(wxr["attachments"]),
			"media": media_report
			or {"note": _("Media import disabled — image URLs still point to the source site.")},
			"widgets_to_rebuild": todo_counter,
			"templates_skipped": 0 if self.import_templates else len(wxr["templates"]),
		}

	SYSTEM_FONTS = {"arial", "helvetica", "sans-serif", "serif", "monospace", "georgia", "times", "inherit"}

	def _collect_fonts(self, blocks):
		"""Collect non-system font families used by converted blocks so their
		Google Fonts import can be injected (WordPress loaded them, we must too)."""
		fonts = set()

		def walk(node):
			for styles_key in ("baseStyles", "tabletStyles", "mobileStyles", "rawStyles"):
				fam = (node.get(styles_key) or {}).get("fontFamily")
				if fam:
					primary = fam.split(",")[0].strip().strip("'\"")
					if primary and primary.lower() not in self.SYSTEM_FONTS:
						fonts.add(primary)
			for child in node.get("children") or []:
				walk(child)

		for b in blocks:
			walk(b)
		return fonts

	DISCOVERED_MAX = 20

	def _import_discovered_pages(self, pages_report):
		"""Create detail pages for CPT entries discovered through live grids
		(WordPress refuses to export those post types). Each page is scraped
		from the live site and rebuilt as an editable component page."""
		from urllib.parse import urlparse

		from wp_migrator.converter.components import build_property_page
		from wp_migrator.converter.live_scrape import scrape_property_page

		items = (elementor.LIVE_DATA.get("ucaddon_post_grid") or [])[: self.DISCOVERED_MAX]
		created = []
		for item in items:
			try:
				route = urlparse(item["link"]).path.strip("/")
				if not route:
					continue
				data = scrape_property_page(item["link"])
				component = build_property_page(data, uid=route.rsplit("/", 1)[-1][:12])
				root = elementor.block(
					"div",
					{"display": "flex", "flexDirection": "column", "alignItems": "center", "width": "100%"},
					[component],
					name="root",
				)
				existing = frappe.db.get_value("Builder Page", {"route": route}, "name")
				if existing:
					page = frappe.get_doc("Builder Page", existing)
					page.draft_blocks = json.dumps([root])
					page.save()
				else:
					page = frappe.get_doc(
						{
							"doctype": "Builder Page",
							"page_title": data["title"],
							"route": route,
							"draft_blocks": json.dumps([root]),
							"published": 0,
						}
					).insert()
				if self.publish_pages:
					page.publish()
				entry = {
					"title": data["title"],
					"route": route,
					"builder_page": page.name,
					"action": "discovered",
					"editor": f"/builder/page/{page.name}",
				}
				pages_report.append(entry)
				created.append(route)
			except Exception as e:
				created.append(f"ERROR {item.get('link', '?')}: {str(e)[:80]}")
		frappe.db.commit()
		return created

	def _relativize_internal_links(self, pages_report):
		"""Turn remaining absolute links to the source site into relative
		paths: the migrated site must not send visitors back to WordPress.
		Runs after media import (media URLs are already local)."""
		import re
		from urllib.parse import urlparse

		host = urlparse(self.source_url).netloc.replace("www.", "")
		prefix_re = re.compile(r"https?://(?:www\.)?" + re.escape(host))
		pages_changed = 0
		for entry in pages_report:
			page = frappe.get_doc("Builder Page", entry["builder_page"])
			changed = False
			for field in ("draft_blocks", "blocks"):
				blob = page.get(field)
				if not blob:
					continue
				new_blob = prefix_re.sub("", blob)
				if new_blob != blob:
					page.set(field, new_blob)
					changed = True
			if changed:
				page.flags.ignore_version = True
				page.save()
				pages_changed += 1
		frappe.db.commit()
		return pages_changed

	def _apply_site_chrome(self, wxr):
		"""Configure the site header/footer (logo, menu, CTA) from the source
		site. On the clean upstream base this builds two Builder Components
		(one shared header, one shared footer) referenced by every page; on
		the legacy fork it fills Website Header Footer Config."""
		if not frappe.db.exists("DocType", "Website Header Footer Config"):
			return self._apply_site_chrome_components(wxr)
		return self._apply_site_chrome_legacy(wxr)

	def _menu_from_wxr(self, wxr):
		pages_by_id = {p["wp_id"]: p for p in wxr["pages"]}
		items = []
		for m in wxr.get("menu") or []:
			target = pages_by_id.get(m.get("object_id"))
			url = "/" + target["slug"] if target else (m.get("url") or "/")
			label = m.get("label") or (target and target["title"]) or url
			items.append({"label": label, "url": url})
		return items

	def _mine_contacts(self, wxr):
		"""mailto:/tel: links mined from the exported content."""
		import re

		blob = " ".join(
			(e.get("content_html") or "") for e in (wxr.get("pages", []) + wxr.get("templates", []))
		)
		contacts, seen = [], set()
		for mail in re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", blob):
			mail = mail.rstrip(".")
			if mail.lower() not in seen and not mail.endswith((".png", ".jpg", ".svg", ".webp")):
				seen.add(mail.lower())
				contacts.append({"label": mail, "href": f"mailto:{mail}"})
			if len(contacts) >= 2:
				break
		for tel in re.findall(r"tel:([+0-9][0-9 ().-]{6,})", blob)[:1]:
			contacts.append({"label": tel.strip(), "href": f"tel:{tel.strip()}"})
		return contacts

	def _download_logo(self, logo_url):
		if not logo_url:
			return None
		try:
			import requests

			from frappe.utils.file_manager import save_file

			r = requests.get(logo_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
			r.raise_for_status()
			fname = logo_url.rstrip("/").rsplit("/", 1)[-1].split("?")[0] or "logo.png"
			f = save_file(fname, r.content, "WP Migration", self.name, is_private=0)
			return f.file_url
		except Exception:
			return logo_url  # fall back to hotlink rather than no logo

	def _apply_site_chrome_components(self, wxr):
		from wp_migrator.converter import chrome, live_scrape

		report = {"mode": "builder-components"}
		menu_items = self._menu_from_wxr(wxr)
		site_name = (wxr.get("site") or {}).get("title") or ""

		logo_url = None
		try:
			logo_url = live_scrape.scrape_site_logo(self.source_url)
		except Exception:
			pass
		local_logo = self._download_logo(logo_url)
		report["logo"] = local_logo

		cta = next(
			({"label": i["label"], "url": i["url"]} for i in menu_items if "contact" in i["url"].lower()),
			None,
		)
		contacts = self._mine_contacts(wxr)
		copyright_text = _("© {0} — all rights reserved").format(site_name) if site_name else ""

		header = chrome.build_header_block(menu_items, local_logo, cta, site_name)
		footer = chrome.build_footer_block(menu_items, contacts, local_logo, site_name, copyright_text)

		for comp_id, comp_name, tree in (
			(chrome.HEADER_COMPONENT_ID, "Site Header", header),
			(chrome.FOOTER_COMPONENT_ID, "Site Footer", footer),
		):
			existing = frappe.db.get_value("Builder Component", {"component_id": comp_id})
			if existing:
				comp = frappe.get_doc("Builder Component", existing)
				comp.block = json.dumps(tree)
				comp.save()
			else:
				frappe.get_doc(
					{
						"doctype": "Builder Component",
						"component_name": comp_name,
						"component_id": comp_id,
						"block": json.dumps(tree),
					}
				).insert()
		report["components"] = ["Site Header", "Site Footer"]
		report["menu_items"] = len(menu_items)
		report["contacts"] = len(contacts)

		# reference the components at the top/bottom of every imported page
		pages = frappe.get_all("Builder Page", filters={"is_template": 0}, pluck="name")
		wrapped = 0
		for name in pages:
			page = frappe.get_doc("Builder Page", name)
			blob = page.draft_blocks or page.blocks
			if not blob:
				continue
			blocks = json.loads(blob)
			# drop any previous chrome refs, then re-inject fresh ones (repairs
			# refs from older imports and keeps re-imports idempotent)
			blocks = [b for b in blocks if not b.get("extendedFromComponent")]
			blocks = (
				[chrome.component_ref(chrome.HEADER_COMPONENT_ID, f"hdr-{page.name}", header)]
				+ blocks
				+ [chrome.component_ref(chrome.FOOTER_COMPONENT_ID, f"ftr-{page.name}", footer)]
			)
			page.draft_blocks = json.dumps(blocks)
			page.flags.ignore_version = True
			page.save()
			if page.published:
				page.publish()
			wrapped += 1
		report["pages_wrapped"] = wrapped

		frappe.db.commit()
		return report

	def _set_home_page(self):
		"""The front page of the import becomes the site home. Runs in the
		main import flow so BOTH chrome paths get it (it used to live only
		in the legacy components path — config-driven imports ended up with
		an empty home_page and the site root served the login page)."""
		home = frappe.db.get_value("Builder Page", {"route": "accueil"}) or frappe.db.get_value(
			"Builder Page", {"route": "home"}
		)
		if not home:
			return None
		route = frappe.db.get_value("Builder Page", home, "route")
		frappe.db.set_single_value("Website Settings", "home_page", route)
		frappe.db.commit()
		return route

	def _unwrap_component_chrome(self):
		"""Remove component-based chrome refs (a config-driven chrome is now
		active — avoid double headers when both subsystems are installed)."""
		for name in frappe.get_all("Builder Page", filters={"is_template": 0}, pluck="name"):
			page = frappe.get_doc("Builder Page", name)
			blob = page.draft_blocks or page.blocks
			if not blob or "extendedFromComponent" not in blob:
				continue
			blocks = [b for b in json.loads(blob) if not b.get("extendedFromComponent")]
			page.draft_blocks = json.dumps(blocks)
			page.flags.ignore_version = True
			page.save()
			if page.published:
				page.publish()

	def _apply_site_chrome_legacy(self, wxr):
		"""Legacy fork subsystem (Website Header Footer Config)."""
		self._unwrap_component_chrome()

		pages_by_id = {p["wp_id"]: p for p in wxr["pages"]}
		config = frappe.get_doc("Website Header Footer Config")
		report = {}

		# menu from WXR nav_menu_items (labels resolved from target pages)
		if wxr.get("menu"):
			config.set("menu_items", [])
			for m in wxr["menu"]:
				target = pages_by_id.get(m.get("object_id"))
				if m.get("object") == "page" and target:
					label = m["label"] or target["title"]
					url = "/" + target["slug"]
				elif m.get("url"):
					label, url = m["label"] or m["url"], m["url"]
				else:
					continue
				config.append("menu_items", {"label": label, "url": url})
			report["menu_items"] = len(config.menu_items)

		# live logo (downloaded locally)
		try:
			logo_url = scrape_site_logo(self.source_url)
			if logo_url:
				resp = requests.get(logo_url, headers=REQUEST_HEADERS, timeout=30)
				resp.raise_for_status()
				from frappe.utils.file_manager import save_file

				fname = logo_url.rsplit("/", 1)[-1].split("?")[0] or "logo"
				f = save_file(fname, resp.content, "WP Migration", self.name, is_private=0)
				config.logo_type = "Image"
				config.logo_image = f.file_url
				report["logo"] = f.file_url
				if "white" in fname.lower():
					# a white logo needs a dark chrome to be visible
					config.header_bg_color = "#111111"
					config.header_text_color = "#ffffff"
					config.footer_bg_color = "#111111"
					config.footer_text_color = "#ffffff"
					report["dark_chrome"] = True
		except Exception as e:
			report["logo_error"] = str(e)[:120]

		# CTA to the contact page when one exists
		contact = next((p for p in wxr["pages"] if "contact" in p["slug"]), None)
		if contact:
			config.show_cta = 1
			config.cta_text = contact["title"]
			config.cta_url = "/" + contact["slug"]
			report["cta"] = config.cta_url

		# footer: mirror the menu + contact details found in source templates
		import re as _re

		blob = json.dumps([t.get("elementor_data") for t in wxr.get("templates", [])])
		email = _re.search(r"mailto:([\w.+-]+@[\w.-]+)", blob)
		phone = _re.search(r"tel:([+\d][\d ()./-]{6,20})", blob)
		config.footer_template = "Standard"
		config.footer_logo_type = "Same as Header"
		site_title = wxr["site"].get("title") or ""
		config.copyright_text = f"© {{year}} " + site_title
		config.set("footer_links", [])
		for m in (wxr.get("menu") or [])[:6]:
			target = pages_by_id.get(m.get("object_id"))
			if target:
				config.append("footer_links", {"label": m["label"] or target["title"], "url": "/" + target["slug"]})
		if email:
			config.append("footer_links", {"label": email.group(1), "url": "mailto:" + email.group(1), "is_external": 1})
			report["footer_email"] = email.group(1)
		if phone:
			tel = phone.group(1).strip()
			config.append("footer_links", {"label": tel, "url": "tel:" + tel.replace(" ", ""), "is_external": 1})
			report["footer_phone"] = tel

		config.save()
		frappe.db.commit()
		return report

	def _collect_live_widget_data(self, entries):
		"""Some widgets (post grids, multisource cards) resolve their items from
		post types WordPress does not export. Scrape them from the live site
		and hand them to the converter (elementor.LIVE_DATA)."""
		elementor.LIVE_DATA.clear()

		def widget_types(els, acc):
			for el in els or []:
				if el.get("elType") == "widget":
					acc.add(el.get("widgetType", ""))
				widget_types(el.get("elements"), acc)

		for entry in entries:
			types = set()
			widget_types(entry.get("elementor_data"), types)
			if "ucaddon_post_grid" in types and "ucaddon_post_grid" not in elementor.LIVE_DATA:
				try:
					items = scrape_uc_post_grid(f"{self.source_url}/{entry['slug']}/")
					if items:
						elementor.LIVE_DATA["ucaddon_post_grid"] = items
						# the home's expanding cards showcase the same entities
						elementor.LIVE_DATA.setdefault("ucaddon_expanding_content_cards", items)
				except Exception:
					pass

	MEDIA_MAX_FILES = 300
	MEDIA_MAX_BYTES = 25 * 1024 * 1024  # per file

	def _import_referenced_media(self, pages_report):
		"""Download media referenced by the imported pages from the source
		site, dedupe by content hash, rewrite URLs inside the blocks."""
		import hashlib
		import re
		from urllib.parse import urlparse

		from frappe.utils.file_manager import save_file

		source_host = urlparse(self.source_url).netloc.replace("www.", "")
		url_re = re.compile(r"https?://(?:www\.)?" + re.escape(source_host) + r"/[^\s\"'\\)]+")

		media_ext = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".avif",
			".mp4", ".webm", ".pdf", ".woff", ".woff2", ".ttf", ".ico")

		# 1) collect referenced source URLs across all imported pages
		page_docs = {}
		urls = set()
		for entry in pages_report:
			page = frappe.get_doc("Builder Page", entry["builder_page"])
			page_docs[page.name] = page
			blob = (page.draft_blocks or "") + (page.blocks or "")
			for raw in url_re.findall(blob):
				url = raw.replace("&amp;", "&").rstrip("\\'\").,;")
				if url.lower().split("?")[0].endswith(media_ext):
					urls.add(url)

		urls = sorted(urls)[: self.MEDIA_MAX_FILES]

		# 2) download + dedupe + save
		url_map = {}
		downloaded, reused, failed = 0, 0, []
		for url in urls:
			try:
				resp = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
				resp.raise_for_status()
				content = resp.content
				if len(content) > self.MEDIA_MAX_BYTES:
					failed.append({"url": url, "error": _("File too large")})
					continue
				content_hash = hashlib.md5(content).hexdigest()  # matches frappe File.content_hash
				existing = frappe.db.get_value(
					"File", {"content_hash": content_hash, "is_private": 0}, "file_url"
				)
				if existing:
					url_map[url] = existing
					reused += 1
					continue
				filename = urlparse(url).path.rsplit("/", 1)[-1] or "media"
				f = save_file(filename, content, "WP Migration", self.name, is_private=0)
				url_map[url] = f.file_url
				downloaded += 1
			except Exception as e:
				failed.append({"url": url, "error": str(e)[:200]})

		# 3) rewrite URLs in every imported page (raw and HTML-escaped forms)
		pages_rewritten = 0
		for page in page_docs.values():
			changed = False
			for field in ("draft_blocks", "blocks"):
				blob = page.get(field)
				if not blob:
					continue
				new_blob = blob
				for src, dest in url_map.items():
					new_blob = new_blob.replace(src, dest).replace(src.replace("&", "&amp;"), dest)
				if new_blob != blob:
					page.set(field, new_blob)
					changed = True
			if changed:
				page.flags.ignore_version = True
				page.save()
				pages_rewritten += 1

		return {
			"referenced_urls": len(urls),
			"downloaded": downloaded,
			"deduplicated": reused,
			"failed": failed[:20],
			"pages_rewritten": pages_rewritten,
		}
