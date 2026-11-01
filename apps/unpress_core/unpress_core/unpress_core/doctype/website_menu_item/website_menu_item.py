# Copyright (c) 2025, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class WebsiteMenuItem(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		is_external: DF.Check
		label: DF.Data
		open_in_new_tab: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		url: DF.Data
	# end: auto-generated types

	pass
