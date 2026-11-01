#!/usr/bin/env python
"""Find (and optionally remove) what a manual UI test left behind on a bench.

Uploading a logo, a reference or a content file through the chat creates rows
in four places at once — File, Builder Content Asset, Builder Site Inspiration,
and the chat session itself. Missing one leaves a test photo in a client's
content library, where the generator will happily put it on their site.

    ../env/bin/python ../apps/unpress_core/scripts/clean-test-artifacts.py <site>          # inventaire
    ../env/bin/python ../apps/unpress_core/scripts/clean-test-artifacts.py <site> --delete # suppression

Patterns are the filenames this project's test procedures use. Pass --pattern
to add one (repeatable). Nothing is deleted without --delete.
"""

import argparse
import sys

import frappe

DEFAULT_PATTERNS = [
	"test-logo%",
	"photo-atelier%",
	"photo-vitrine%",
	"presentation%",
	"marque-test%",
	"logo-boulangerie%",
	"devanture%",
]

# doctype -> column holding the filename or file url
TARGETS = [
	("Builder Content Asset", "original_filename"),
	("Builder Site Inspiration", "image"),
	("File", "file_name"),
]


def main() -> int:
	parser = argparse.ArgumentParser()
	parser.add_argument("site")
	parser.add_argument("--delete", action="store_true", help="supprimer au lieu d'inventorier")
	parser.add_argument("--pattern", action="append", default=[], help="motif SQL LIKE supplémentaire")
	args = parser.parse_args()

	patterns = DEFAULT_PATTERNS + args.pattern

	frappe.init(site=args.site)
	frappe.connect()
	frappe.set_user("Administrator")

	total = 0
	for doctype, column in TARGETS:
		if not frappe.db.exists("DocType", doctype):
			continue
		names = []
		for pattern in patterns:
			names += frappe.db.sql(
				f"select name from `tab{doctype}` where coalesce(`{column}`, '') like %s",
				(pattern,),
				pluck=True,
			)
		names = sorted(set(names))
		if not names:
			continue
		total += len(names)
		print(f"{doctype}: {len(names)}")
		for name in names:
			print(f"    {name}")
			if args.delete:
				frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)

	if args.delete:
		frappe.db.commit()
		print(f"\n{total} enregistrement(s) supprimé(s).")
	elif total:
		print(f"\n{total} résidu(s) de test. Relancer avec --delete pour supprimer.")
	else:
		print("Aucun résidu de test.")

	# a count of what remains, to confirm real data was untouched
	print("\nRestant sur le site :")
	for doctype in ("Builder Chat Session", "Builder Content Asset",
					"Builder Site Inspiration", "Builder Page"):
		if frappe.db.exists("DocType", doctype):
			print(f"  {doctype:26} {frappe.db.count(doctype)}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
