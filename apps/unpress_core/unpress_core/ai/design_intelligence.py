"""Design intelligence: professional candidates for the design brief.

Queries the vendored UI/UX Pro Max database (see design_data/README.md) with
BM25 and returns a prompt-ready CANDIDATES block: UI styles, product-aligned
color palettes, typography pairings and UX anti-patterns matched to the
business. The brief LLM picks and adapts — candidates widen its taste, they
never replace its judgment.

Best-effort by design: any failure returns None and the brief generates
exactly as before.
"""

import json
import subprocess
import sys
from pathlib import Path

try:
	from unpress_core.ai.logging import ai_log
except Exception:  # usable outside a frappe context (unit tests, CLI)
	def ai_log(level, message, **context):
		pass

SEARCH_SCRIPT = Path(__file__).parent / "design_data" / "scripts" / "search.py"

# Per-search subprocess budget; the whole candidates block stays under ~1 min
# worst-case, negligible against a multi-minute site generation.
SEARCH_TIMEOUT = 20

# The database is English; client descriptions are mostly French. BM25 has no
# stemming, so map common Swiss-French business words to English search terms —
# one matched keyword is enough to steer the ranking. Cognates (restaurant,
# elegant, boutique...) already match without help.
INDUSTRY_KEYWORDS = {
	"fromagerie": "artisan cheese dairy food craft",
	"boulangerie": "artisan bakery bread food craft",
	"boucherie": "butcher meat food artisan",
	"restaurant": "restaurant food service dining",
	"café": "coffee shop cafe food",
	"traiteur": "catering food service",
	"vigneron": "winery vineyard wine",
	# "cave" intentionally absent: too ambiguous in French (wine cellar,
	# cheese-aging cellar, basement...) — it mis-steered a fromagerie query.
	"brasserie": "brewery restaurant food",
	"menuiserie": "carpentry woodwork craft workshop",
	"charpente": "carpentry timber construction",
	"maçonnerie": "masonry construction building",
	"construction": "construction building contractor",
	"rénovation": "renovation construction home improvement",
	"peinture": "painting decorating home improvement",
	"plâtrerie": "plastering construction",
	"électricité": "electrician electrical services",
	"électricien": "electrician electrical services",
	"plomberie": "plumbing home services",
	"chauffage": "heating hvac home services",
	"sanitaire": "plumbing bathroom services",
	"jardinier": "gardening landscaping outdoor",
	"paysagiste": "landscaping garden design outdoor",
	"fiduciaire": "accounting fiduciary finance trust professional",
	"comptable": "accounting bookkeeping finance",
	"avocat": "law firm legal attorney professional",
	"notaire": "notary legal professional trust",
	"assurance": "insurance finance trust",
	"immobilier": "real estate property agency",
	"régie": "real estate property management",
	"architecte": "architecture design studio",
	"ingénieur": "engineering technical professional",
	"médecin": "medical doctor healthcare clinic",
	"dentiste": "dentist dental clinic healthcare",
	"physiothérapie": "physiotherapy health wellness clinic",
	"ostéopathe": "osteopath health wellness clinic",
	"pharmacie": "pharmacy healthcare",
	"vétérinaire": "veterinary pet clinic",
	"coiffeur": "hair salon beauty",
	"coiffure": "hair salon beauty",
	"esthétique": "beauty spa wellness aesthetics",
	"institut": "beauty spa wellness institute",
	"massage": "massage spa wellness",
	"fitness": "fitness gym sports training",
	"yoga": "yoga wellness studio",
	"garage": "auto repair garage automotive",
	"carrosserie": "auto body repair automotive",
	"transport": "transport logistics",
	"déménagement": "moving company logistics",
	"nettoyage": "cleaning services professional",
	"fleuriste": "florist flowers boutique",
	"bijouterie": "jewelry luxury boutique",
	"horlogerie": "watchmaking luxury craft swiss",
	"photographe": "photography creative studio portfolio",
	"graphiste": "graphic design creative studio",
	"agence": "agency creative professional services",
	"informatique": "it services technology software",
	"école": "school education learning",
	"formation": "training education courses",
	"crèche": "childcare nursery kids",
	"hôtel": "hotel hospitality travel",
	"tourisme": "tourism travel hospitality",
	"airsoft": "airsoft tactical sports equipment shop",
	"armurerie": "tactical equipment sports shop",
	"association": "nonprofit association community",
	"fondation": "nonprofit foundation charity",
}

SITE_TYPE_KEYWORDS = {
	"vitrine": "business showcase landing website",
	"ecommerce": "ecommerce online store shop product",
	"e-commerce": "ecommerce online store shop product",
	"boutique": "ecommerce online store shop product",
	"portfolio": "portfolio creative showcase",
	"blog": "blog editorial content magazine",
	"landing": "landing page conversion marketing",
	"onepage": "one page landing website",
	"restaurant": "restaurant food menu",
	"association": "nonprofit association community",
}

# Noisy/huge CSV columns we never inject into the prompt.
EXCLUDED_COLUMNS = {
	"No",
	"Light Mode ✓",
	"Dark Mode ✓",
	"Performance",
	"Mobile-Friendly",
	"Conversion-Focused",
	"Framework Compatibility",
	"Era/Origin",
	"Complexity",
	"CSS/Technical Keywords",
	"Implementation Checklist",
	"Code Example Good",
	"Code Example Bad",
	"Platform",
}

MAX_FIELD_CHARS = 260


def build_search_query(description: str, site_type: str = "", theme: str = "") -> str:
	"""Compose an English-leaning BM25 query from a (usually French) description."""
	text = f"{description or ''} {site_type or ''}".lower()
	parts = []
	for fr_word, en_terms in INDUSTRY_KEYWORDS.items():
		if fr_word in text:
			parts.append(en_terms)
	for type_word, en_terms in SITE_TYPE_KEYWORDS.items():
		if type_word in (site_type or "").lower():
			parts.append(en_terms)
			break
	if theme:
		parts.append(theme)
	# Keep the raw description last: cognates and any English words still score.
	parts.append((description or "")[:200])
	return " ".join(p for p in parts if p).strip()


def run_search(query: str, domain: str, max_results: int) -> list[dict]:
	"""One BM25 search via the vendored CLI; [] on any failure."""
	cmd = [
		sys.executable,
		str(SEARCH_SCRIPT),
		query,
		"--domain",
		domain,
		"--json",
		"--max-results",
		str(max_results),
	]
	result = subprocess.run(cmd, capture_output=True, text=True, timeout=SEARCH_TIMEOUT)
	if result.returncode != 0:
		ai_log("warning", "design_intelligence search failed",
			domain=domain, stderr=result.stderr[:300])
		return []
	payload = json.loads(result.stdout)
	return payload.get("results") or []


def format_rows(rows: list[dict]) -> str:
	lines = []
	for row in rows:
		fields = []
		for key, value in row.items():
			if key in EXCLUDED_COLUMNS or not value:
				continue
			value = str(value).strip()
			if len(value) > MAX_FIELD_CHARS:
				value = value[:MAX_FIELD_CHARS] + "…"
			fields.append(f"{key}: {value}")
		lines.append("- " + " | ".join(fields))
	return "\n".join(lines)


def get_design_candidates(
	description: str,
	site_type: str = "",
	theme: str = "",
	colors_imposed: bool = False,
) -> str | None:
	"""Prompt-ready CANDIDATES block for the brief, or None (best-effort)."""
	try:
		query = build_search_query(description, site_type, theme)
		if not query:
			return None

		sections = []
		searches = [
			("style", 2, "UI STYLE candidates"),
			("color", 2, "PALETTE candidates (full token sets)"),
			("typography", 2, "TYPOGRAPHY pairing candidates"),
			("ux", 3, "UX RULES for this kind of product (respect the Don'ts)"),
		]
		for domain, max_results, title in searches:
			rows = run_search(query, domain, max_results)
			if rows:
				sections.append(f"### {title}\n{format_rows(rows)}")

		if not sections:
			return None

		palette_note = (
			"Palette candidates are SECONDARY here: the client brand colors above are "
			"imposed — use candidates only for supporting tones and token structure.\n"
			if colors_imposed
			else ""
		)
		body = "\n\n".join(sections)
		ai_log("info", "design_intelligence candidates built",
			query=query[:120], sections=len(sections))
		return (
			"**DESIGN CANDIDATES — curated professional database (BM25-matched to this "
			"business):**\n"
			f"{palette_note}\n"
			f"{body}\n\n"
			"Treat candidates as a professional moodboard: pick the direction that truly "
			"fits THIS business — or reject them for a better idea of yours. ADAPT hex "
			"values and pairings to the brand; never copy a candidate verbatim, and keep "
			"the §1 art-direction rules in charge."
		)
	except Exception as e:
		ai_log("warning", "design_intelligence unavailable", error=str(e)[:300])
		return None
