#!/usr/bin/env python
"""Smoke test for the AI chat wizard — read-only, safe on a bench with real data.

Runs against whichever side is installed: unpress_core (the Studio) or the
version-15 branch, where the same engine lives inside the `builder` app. One
file for both, because the Studio is the source of truth and the other branches
onto it.

    cd sites && ../env/bin/python ../apps/unpress_core/scripts/smoke-ai-chat.py <site>

Deliberately never calls start_session(): on a bench with real sessions it
flips every Active one older than 24h to Abandoned. A smoke test must not
mutate the data it is checking.

Exit code 0 when everything passes, 1 otherwise — usable in CI or a nightly.
"""

import sys
import traceback

import frappe


def main(site: str) -> int:
	frappe.init(site=site)
	frappe.connect()

	installed = frappe.get_installed_apps()
	if "unpress_core" in installed:
		flavour, api, ai = "unpress_core", "unpress_core.generation", "unpress_core.ai"
	elif "builder" in installed:
		flavour, api, ai = "builder (v15)", "builder.api", "builder.ai"
	else:
		print("Neither unpress_core nor builder is installed on this site.")
		return 1

	i18n = "unpress_core.i18n" if flavour == "unpress_core" else "builder.i18n"
	ingest = f"{ai}.ingestion.content_understanding"
	passed, failed = [], []

	def check(label, fn):
		try:
			passed.append((label, fn()))
		except Exception as e:
			failed.append((label, f"{type(e).__name__}: {e}"))
			traceback.print_exc()

	def _imports():
		for path in (api, f"{ai}.config", f"{ai}.ingestion.content_understanding",
					f"{ai}.ingestion.image_matcher", i18n):
			frappe.get_module(path)
		return "modules du wizard importables"

	check("imports", _imports)

	check(
		"_image_backend_available()",
		lambda: frappe.get_attr(f"{api}._image_backend_available")(),
	)
	check(
		"get_assistant_name()",
		lambda: frappe.get_attr(f"{ai}.config.get_assistant_name")(),
	)

	endpoints = [
		f"{api}.chat_start_session", f"{api}.chat_send_message",
		f"{api}.chat_upload_logo", f"{api}.chat_upload_inspiration",
		f"{api}.chat_trigger_generation", f"{api}.chat_get_generation_status",
		f"{api}.chat_generate_images", f"{api}.chat_get_image_generation_status",
		f"{api}.chat_clear_session",
		f"{ingest}.ingest_content_assets", f"{ingest}.get_content_context",
		f"{i18n}.get_translations",
	]

	def _endpoints():
		for path in endpoints:
			frappe.get_attr(path)
		return f"{len(endpoints)} endpoints résolvables"

	check("endpoints whitelistés", _endpoints)

	def _doctypes():
		needed = ["Builder Chat Session", "Builder Chat Message", "Builder Content Asset",
				"Builder Site Inspiration", "Builder Page"]
		absent = [d for d in needed if not frappe.db.exists("DocType", d)]
		if absent:
			raise RuntimeError("manquants: " + ", ".join(absent))
		return f"{len(needed)} doctypes présents"

	check("doctypes", _doctypes)

	def _content():
		"""The client's own text must reach the generator — the whole point of
		the content library. Read-only: uses whatever session already exists."""
		row = frappe.db.sql(
			"select session_id from `tabBuilder Content Asset` "
			"where asset_type='Document' order by creation desc limit 1"
		)
		if not row:
			return "aucun document client sur ce site (rien à vérifier)"
		sid = row[0][0]
		out = frappe.get_attr(f"{ingest}.get_content_context")(sid, page_hint="accueil")
		if not out:
			raise RuntimeError(f"session {sid}: aucun contenu client ne remonte")
		return f"session {sid}: {len(out)} caractères de contenu client remontent"

	check("get_content_context (lecture seule)", _content)

	def _desk_page():
		if frappe.db.exists("Page", "builder-chat"):
			raise RuntimeError("la page desk builder-chat existe encore")
		return "absente (remplacée par la modale)"

	check("page desk retirée", _desk_page)

	def _catalog():
		frappe.local.lang = "fr"
		messages = frappe.get_attr(f"{i18n}.get_translations")()
		for probe in ("Create with AI", "Share photos and documents"):
			if probe not in messages:
				raise RuntimeError(f"msgid absent du catalogue fr: {probe}")
		return f"{len(messages)} messages fr, chaînes du wizard présentes"

	check("catalogue i18n", _catalog)

	print(f"\n{'=' * 66}\n  cible : {site}  ({flavour})\n{'=' * 66}")
	for label, result in passed:
		print(f"  PASS  {label}: {result}")
	for label, error in failed:
		print(f"  FAIL  {label}: {error}")
	print("=" * 66)
	print(f"{len(passed)} passés, {len(failed)} échecs")
	return 1 if failed else 0


if __name__ == "__main__":
	if len(sys.argv) < 2:
		print(__doc__)
		sys.exit(2)
	sys.exit(main(sys.argv[1]))
