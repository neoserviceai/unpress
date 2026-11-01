# The site's media, and where each item is actually used.
#
# Every image a client uploads ends up in the File doctype, and its URL is
# written straight into a page's `blocks` JSON. That JSON is the only record
# of "this image is on that page", and nothing indexes it — so nobody can
# answer "can I delete this?" without opening every page.
#
# This walks the blocks once and builds the index. Same walk answers the link
# question: which pages link where, and which internal links point at a route
# that does not exist.
import json
import os
import re

import frappe
from frappe import _

MEDIA_ROLES = ("System Manager", "Website Manager")

# The builder drops uploads here, but the AI image worker writes into the
# default folder — so the media of a site is NOT "what is in one folder". It
# is every public image: a private File is an attachment to some document,
# not something the site shows.
UPLOAD_FOLDER = "Home/Builder Uploads"

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".avif", ".bmp", ".ico"}

# `url(...)` in a style, `src` in an img, and the plain string form the
# generator writes into baseStyles.
_URL_IN_CSS = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)")


def _on_disk(file_url: str) -> bool:
	"""Whether the File row still has a file behind it.

	A row can outlive its bytes — a manual cleanup, a restore, a botched
	migration. Showing it as a broken image would tell the user their upload
	failed; saying the file is missing tells them what actually happened.
	"""
	if not file_url or not file_url.startswith("/files/"):
		return True
	return os.path.isfile(frappe.get_site_path("public", file_url.lstrip("/")))


def _is_image(url: str) -> bool:
	return os.path.splitext((url or "").split("?")[0])[1].lower() in IMAGE_EXTENSIONS


def _walk(blocks, on_block):
	"""Depth-first over a block tree, without recursion.

	The trees are shallow but wide; an explicit stack keeps this usable from a
	console (where a recursive closure would not resolve its own name).
	"""
	stack = list(blocks) if isinstance(blocks, list) else [blocks]
	while stack:
		block = stack.pop()
		if not isinstance(block, dict):
			continue
		on_block(block)
		children = block.get("children")
		if children:
			stack.extend(children)


def _assets_and_links(block: dict) -> tuple[set[str], set[str]]:
	"""What one block points at: (image urls, link hrefs)."""
	images: set[str] = set()
	links: set[str] = set()

	attributes = block.get("attributes") or {}
	src = attributes.get("src")
	if src:
		images.add(str(src))
	href = attributes.get("href")
	if href:
		links.add(str(href))

	for bucket in ("baseStyles", "rawStyles", "mobileStyles", "tabletStyles"):
		styles = block.get(bucket) or {}
		if not isinstance(styles, dict):
			continue
		for value in styles.values():
			if isinstance(value, str) and "url(" in value:
				images.update(_URL_IN_CSS.findall(value))

	return images, links


def _page_index() -> tuple[dict, list]:
	"""(image url -> [pages], [link rows]) across every Builder Page.

	Published `blocks` and the editor's `draft_blocks` are both walked: an
	image only present in a draft is still in use, and deleting it would break
	the page the moment it is published.
	"""
	usage: dict[str, list] = {}
	links: list[dict] = []

	pages = frappe.get_all(
		"Builder Page",
		fields=["name", "page_title", "route", "published"],
	)
	for page in pages:
		doc = frappe.get_doc("Builder Page", page.name)
		seen_images: set[str] = set()
		seen_links: set[str] = set()

		for field in ("blocks", "draft_blocks"):
			raw = doc.get(field)
			if not raw:
				continue
			try:
				tree = json.loads(raw)
			except (TypeError, ValueError):
				continue

			def collect(block, _images=seen_images, _links=seen_links):
				images, hrefs = _assets_and_links(block)
				_images.update(images)
				_links.update(hrefs)

			_walk(tree, collect)

		where = {
			"page": page.name,
			"title": page.page_title or page.name,
			"route": page.route,
			"published": bool(page.published),
		}
		for url in seen_images:
			usage.setdefault(url, []).append(where)
		for href in seen_links:
			links.append({**where, "href": href})

	return usage, links


def _chrome_urls() -> set[str]:
	"""Images the site chrome points at — a logo is used even if no page
	mentions it."""
	urls: set[str] = set()
	for doctype in ("Website Header Footer Config", "Website Header Footer Variant"):
		if not frappe.db.exists("DocType", doctype):
			continue
		meta = frappe.get_meta(doctype)
		fields = [f.fieldname for f in meta.fields if f.fieldtype == "Attach Image"]
		if not fields:
			continue
		if meta.issingle:
			for field in fields:
				value = frappe.db.get_single_value(doctype, field)
				if value:
					urls.add(value)
			continue
		for row in frappe.get_all(doctype, fields=["name", *fields]):
			for field in fields:
				if row.get(field):
					urls.add(row[field])
	return urls


# A generated image weighs a couple of megabytes. Thirty of them as grid
# thumbnails is sixty megabytes for a screen that shows them 200px wide, so the
# grid asks for a thumbnail and frappe makes one the first time it is needed.
THUMBNAIL_SIZE = 320
NO_THUMBNAIL = {".svg", ".gif", ".ico"}


def _ensure_thumbnail(name: str, file_url: str, existing: str | None) -> str:
	"""The small version of an image, or the original when there cannot be one.

	Never fatal: a thumbnail that cannot be produced (a corrupt file, an
	unsupported mode) must not take the media screen down with it.
	"""
	if existing:
		return existing
	if not _on_disk(file_url):
		return file_url
	extension = os.path.splitext((file_url or "").split("?")[0])[1].lower()
	if extension in NO_THUMBNAIL:
		# an SVG is already small, and a GIF loses its animation
		return file_url
	try:
		doc = frappe.get_doc("File", name)
		thumbnail = doc.make_thumbnail(
			set_as_thumbnail=True, width=THUMBNAIL_SIZE, height=THUMBNAIL_SIZE
		)
		return thumbnail or file_url
	except Exception:
		return file_url


@frappe.whitelist()
def list_media(search: str | None = None, unused_only: int | str = 0) -> dict:
	"""Every image the site holds, with where it is used."""
	frappe.only_for(MEDIA_ROLES)

	usage, _ = _page_index()
	chrome = _chrome_urls()

	files = frappe.get_all(
		"File",
		filters={"is_folder": 0, "is_private": 0},
		fields=[
			"name", "file_name", "file_url", "file_size", "creation",
			"is_private", "folder", "thumbnail_url",
		],
		order_by="creation desc",
	)

	items = []
	for row in files:
		if not _is_image(row.file_url or row.file_name):
			continue
		if search and search.lower() not in (row.file_name or "").lower():
			continue
		used_in = usage.get(row.file_url, [])
		in_chrome = row.file_url in chrome
		if frappe.utils.cint(unused_only) and (used_in or in_chrome):
			continue
		items.append({
			"name": row.name,
			"file_name": row.file_name,
			"file_url": row.file_url,
			"thumbnail_url": _ensure_thumbnail(row.name, row.file_url, row.thumbnail_url),
			"missing": not _on_disk(row.file_url),
			"file_size": row.file_size,
			"creation": row.creation,
			"is_private": bool(row.is_private),
			"folder": row.folder,
			"used_in": used_in,
			"in_chrome": in_chrome,
		})

	# An image can be on a page without ever having been a File row — the AI
	# writes remote URLs, and a WordPress import can leave absolute ones.
	# Reporting them as media the user cannot manage would be a lie; counting
	# them is still worth it.
	known = {row.file_url for row in files}
	external = sorted({
		url for url in usage
		if _is_image(url) and url not in known and not url.startswith("/assets/")
	})

	return {
		"items": items,
		"total": len(items),
		"external": external,
		"unused": sum(1 for item in items if not item["used_in"] and not item["in_chrome"]),
	}


@frappe.whitelist()
def list_links() -> dict:
	"""Every link the site's pages carry, and the internal ones that lead nowhere."""
	frappe.only_for(MEDIA_ROLES)

	_, rows = _page_index()

	routes = {
		(r.route or "").strip("/")
		for r in frappe.get_all("Builder Page", fields=["route"])
		if r.route
	}
	routes.add("")  # the home page

	internal, external, broken = [], [], []
	for row in rows:
		href = (row["href"] or "").strip()
		if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
			continue
		if href.startswith(("http://", "https://", "//")):
			external.append(row)
			continue
		target = href.split("?")[0].split("#")[0].strip("/")
		row = {**row, "target": target}
		internal.append(row)
		if target not in routes:
			broken.append(row)

	return {
		"internal": internal,
		"external": external,
		"broken": broken,
		"counts": {
			"internal": len(internal),
			"external": len(external),
			"broken": len(broken),
		},
	}


@frappe.whitelist()
def delete_media(file_url: str) -> dict:
	"""Delete an image — but never one a page or the chrome still points at.

	Deleting a used image does not error anywhere: the page simply renders a
	broken box, and nobody notices until a visitor does.
	"""
	frappe.only_for(MEDIA_ROLES)
	if not file_url:
		frappe.throw(_("No file provided."))

	dangling = not _on_disk(file_url)
	usage, _ = _page_index()
	if file_url in usage and not dangling:
		titles = ", ".join(sorted({page["title"] for page in usage[file_url]}))
		frappe.throw(_("Still used on: {0}").format(titles))
	if file_url in _chrome_urls() and not dangling:
		frappe.throw(_("This image is the site's logo."))

	name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not name:
		frappe.throw(_("That file is not attached to this site."))
	frappe.delete_doc("File", name, ignore_permissions=True)
	frappe.db.commit()
	return {"deleted": file_url}
