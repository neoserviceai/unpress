# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class BuilderAIShortcode(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		category: DF.Literal["Navigation", "E-commerce", "User", "Search", "Social", "Form", "Media", "Other"]
		description: DF.Text | None
		jinja_code: DF.Code | None
		name1: DF.Data
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		shortcode: DF.SmallText
		use_when: DF.SmallText | None
	# end: auto-generated types

	pass
