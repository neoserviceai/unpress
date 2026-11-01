# Live-render scraping: some Elementor widgets resolve their data server-side
# or via AJAX from post types that WordPress does not export (can_export=false
# CPTs). For those, the deployed site itself is the source of truth.
# Pure functions, no Frappe dependency.
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Unpress WP Migrator)"}


def fetch(url):
	req = urllib.request.Request(url, headers=UA)
	return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", errors="replace")


def scrape_uc_post_grid(url):
	"""Extract items from an Unlimited Elements post grid (server-rendered).

	Returns [{title, link, img}] in page order.
	"""
	html = fetch(url)
	items = []
	# split on grid items (the CSS block above them has no hrefs, so it yields
	# no matches); each item block: <a href> + uc_post_image <img> + ue_p_title
	for block in re.split(r'class="[^"]*uc_post_grid_style_one_item[^"]*"', html)[1:]:
		link = re.search(r"href='([^']+)'", block)
		img = re.search(r'<img[^>]+src="([^"]+)"', block)
		title = re.search(r"ue_p_title[^>]*>([^<]+)<", block)
		if link and title:
			items.append(
				{
					"link": link.group(1),
					"title": title.group(1).strip(),
					"img": img.group(1) if img else None,
				}
			)
	# dedupe by link, keep order
	seen, out = set(), []
	for it in items:
		if it["link"] in seen:
			continue
		seen.add(it["link"])
		out.append(it)
	return out


def scrape_site_logo(url):
	"""Best-effort extraction of the site logo image URL from the live page.
	Last 'logo' filename wins (headers usually render after preloaded assets)."""
	html = fetch(url)
	candidates = re.findall(r'src="([^"]*logo[^"]*\.(?:svg|png|webp)[^"]*)"', html, re.I)
	if candidates:
		return candidates[-1]
	m = re.search(r'<img[^>]+class="[^"]*logo[^"]*"[^>]+src="([^"]+)"', html, re.I)
	return m.group(1) if m else None


def scrape_property_page(url):
	"""Extract a property detail page rendered by an Elementor single-post
	template: title, price-ish info lines, description paragraphs, gallery."""
	html = fetch(url)

	title = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
	title = re.sub(r"<[^>]+>", "", title.group(1)).strip() if title else url.rstrip("/").rsplit("/", 1)[-1]

	# info lines (elementor post-info / icon-list items) — price, location...
	infos = []
	for it in re.findall(r"elementor-icon-list-item[^>]*>(.*?)</li>", html, re.S):
		txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", it)).strip()
		if txt and txt not in infos and len(txt) < 90:
			infos.append(txt)

	# descriptive paragraphs: long, clean text (skip nav/price artifacts)
	paragraphs = []
	for p in re.findall(r"<p[^>]*>(.*?)</p>", html, re.S):
		txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p)).strip()
		if len(txt) > 80 and "Revenir au" not in txt and not txt.startswith("CHF"):
			paragraphs.append(txt)

	# gallery: content uploads, full-size unique, no logos/thumbs/youtube covers
	seen, gallery = set(), []
	for src in re.findall(r'<img[^>]+src="(https?://[^"]*/wp-content/uploads/[^"]+)"', html):
		base = re.sub(r"-\d+x\d+(\.\w+)$", r"\1", src.split("?")[0])
		name = base.rsplit("/", 1)[-1].lower()
		if "logo" in name or "youtube" in name or base in seen:
			continue
		seen.add(base)
		gallery.append(base)

	return {"title": title, "infos": infos[:6], "paragraphs": paragraphs[:6], "gallery": gallery[:16]}
