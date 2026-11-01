# Copyright (c) 2026, the host and contributors
# For license information, please see license.txt

import os

import frappe
from frappe.model.document import Document


class BuilderContentAsset(Document):
	"""A single piece of client-provided content (image or document) uploaded
	for a site generation. A background "understanding" pass (vision for
	images, text extraction + classification for documents) fills the
	structured fields so the generator can use real client content as context.
	"""

	def before_insert(self):
		# Derive a human-friendly filename from the file URL when not given.
		if not self.original_filename and self.file:
			self.original_filename = os.path.basename(self.file.split("?")[0])

	def get_full_path(self) -> str | None:
		"""Resolve the on-disk path of the attached file, or None."""
		if not self.file:
			return None
		try:
			file_doc = frappe.get_doc("File", {"file_url": self.file})
			return file_doc.get_full_path()
		except frappe.DoesNotExistError:
			return None
