# Copyright (c) 2025, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
import json
import uuid


class BuilderChatSession(Document):
	"""
	Builder Chat Session DocType for managing AI-guided site generation conversations.
	Stores all collected data and conversation history.
	"""

	def before_insert(self):
		"""Generate unique session ID before insert."""
		if not self.session_id:
			self.session_id = str(uuid.uuid4())[:8]

		if not self.user:
			self.user = frappe.session.user

	def validate(self):
		"""Validate session data."""
		self.calculate_completion()
		self.update_missing_fields()

	def add_message(self, role, content, buttons=None, extracted_data=None, attachment=None):
		"""
		Add a message to the conversation.

		Args:
			role: "user", "assistant", or "system"
			content: Message text content
			buttons: Optional list of suggestion buttons
			extracted_data: Optional dict of data extracted from this message
			attachment: Optional file attachment URL
		"""
		self.append("messages", {
			"role": role,
			"content": content or "...",
			"buttons": json.dumps(buttons) if buttons else None,
			"extracted_data": json.dumps(extracted_data) if extracted_data else None,
			"attachment": attachment
		})

	def get_conversation_history(self, include_system=True):
		"""
		Get conversation history formatted for AI API.

		Returns:
			List of dicts with role and content
		"""
		history = []
		for msg in self.messages:
			if not include_system and msg.role == "system":
				continue
			history.append({
				"role": msg.role,
				"content": msg.content
			})
		return history

	def update_extracted_data(self, new_data):
		"""
		Update session fields with newly extracted data.

		Args:
			new_data: Dict of field names and values to update
		"""
		if not new_data:
			return

		valid_fields = [
			"site_description", "site_name", "site_type",
			"theme", "primary_color", "secondary_color",
			"heading_font", "body_font", "logo_image", "logo_text",
			"pages_config", "cta_text", "cta_url", "social_links",
			"inspiration_urls", "company_data",
		]

		# Fields stored as JSON strings in the database
		json_fields = {"social_links", "pages_config", "inspiration_urls", "company_data"}

		for field, value in new_data.items():
			if field in valid_fields and value is not None:
				# Serialize dicts/lists to JSON strings for JSON-type fields
				if field in json_fields and isinstance(value, (dict, list)):
					value = json.dumps(value)

				# Merge inspiration_urls (append, deduplicate)
				if field == "inspiration_urls" and self.get("inspiration_urls"):
					try:
						existing = json.loads(self.inspiration_urls)
						new_urls = json.loads(value) if isinstance(value, str) else value
						existing_url_set = {item.get("url") for item in existing}
						for item in new_urls:
							if item.get("url") not in existing_url_set:
								existing.append(item)
								existing_url_set.add(item.get("url"))
						self.set(field, json.dumps(existing))
					except (json.JSONDecodeError, TypeError):
						self.set(field, value)
				else:
					self.set(field, value)

		self.calculate_completion()
		self.update_missing_fields()

	def calculate_completion(self):
		"""
		Calculate completion percentage based on collected fields.
		Uses weighted calculation per step.
		"""
		# Step 1: Description (40 points)
		desc_fields = {
			"site_description": 20,
			"site_name": 10,
			"site_type": 10,
		}

		# Step 2: Style (35 points)
		style_fields = {
			"theme": 15,
			"primary_color": 10,
			"secondary_color": 5,
			"heading_font": 5,
		}

		# Step 3: Pages (25 points)
		pages_fields = {
			"pages_config": 15,
			"cta_text": 5,
			"cta_url": 5,
		}

		total_weight = 0
		earned_weight = 0

		for fields_dict in [desc_fields, style_fields, pages_fields]:
			for field, weight in fields_dict.items():
				total_weight += weight
				if self.get(field):
					earned_weight += weight

		if total_weight > 0:
			self.completion_percentage = round((earned_weight / total_weight) * 100, 1)
		else:
			self.completion_percentage = 0

	def update_missing_fields(self):
		"""Update the list of missing required fields."""
		missing = []

		# Step 1: Description
		desc_required = [
			("site_description", _("Site Description")),
			("site_name", _("Site Name")),
			("site_type", _("Site Type")),
		]
		for field, label in desc_required:
			if not self.get(field):
				missing.append({"field": field, "label": str(label), "step": "description"})

		# Step 2: Style
		style_required = [
			("theme", _("Theme")),
			("primary_color", _("Primary Color")),
		]
		for field, label in style_required:
			if not self.get(field):
				missing.append({"field": field, "label": str(label), "step": "style"})

		# Step 3: Pages (pages_config auto-populated so not strictly required from user)

		self.missing_fields = json.dumps(missing)

	def get_missing_fields(self):
		"""Get list of missing fields as Python list."""
		if self.missing_fields:
			return json.loads(self.missing_fields)
		return []

	def get_validation_errors(self):
		"""Get list of validation errors as Python list."""
		if self.validation_errors:
			return json.loads(self.validation_errors)
		return []

	def set_validation_errors(self, errors):
		"""Set validation errors from Python dict."""
		self.validation_errors = json.dumps(errors) if errors else None

	def is_ready_for_generation(self):
		"""
		Check if session has all required data for site generation.

		Returns:
			Tuple of (is_ready: bool, missing: list)
		"""
		missing = self.get_missing_fields()
		is_ready = len(missing) == 0 and self.site_description and self.site_name
		return is_ready, missing
