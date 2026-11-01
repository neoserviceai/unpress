# Outgoing email (SMTP) API for the builder Settings > Email tab.
# One default-outgoing Email Account, minimal fields — enough for password
# resets and site emails on a self-hosted Studio. Frappe validates the SMTP
# connection on save, so a bad host/key fails loudly and the UI shows it.
import json

import frappe
from frappe import _


def _default_outgoing_name():
	return frappe.db.get_value("Email Account", {"default_outgoing": 1}, "name")


@frappe.whitelist()
def get_email_settings():
	frappe.only_for("System Manager")
	name = _default_outgoing_name()
	if not name:
		return {"configured": False, "smtp_port": 587, "use_tls": 1}
	doc = frappe.get_doc("Email Account", name)
	return {
		"configured": True,
		"email_id": doc.email_id,
		"smtp_server": doc.smtp_server,
		"smtp_port": doc.smtp_port,
		"use_tls": doc.use_tls,
		"use_ssl": doc.use_ssl_for_outgoing,
		"has_password": bool(doc.get_password("password", raise_exception=False)),
	}


@frappe.whitelist()
def update_email_settings(settings):
	frappe.only_for("System Manager")
	if isinstance(settings, str):
		settings = json.loads(settings)

	name = _default_outgoing_name()
	doc = frappe.get_doc("Email Account", name) if name else frappe.new_doc("Email Account")
	if not doc.email_account_name:
		doc.email_account_name = "Studio Outgoing"

	doc.email_id = (settings.get("email_id") or "").strip()
	doc.smtp_server = (settings.get("smtp_server") or "").strip()
	doc.smtp_port = settings.get("smtp_port") or 587
	doc.use_tls = 1 if settings.get("use_tls") else 0
	doc.use_ssl_for_outgoing = 1 if settings.get("use_ssl") else 0
	if settings.get("password"):
		doc.password = settings["password"]

	doc.auth_method = "Basic"
	doc.enable_incoming = 0
	doc.enable_outgoing = 1
	doc.default_outgoing = 1
	doc.always_use_account_email_id_as_sender = 1

	# save() validates the SMTP connection — let failures bubble up to the UI
	doc.save()
	return {"ok": True}


@frappe.whitelist()
def send_test_email():
	frappe.only_for("System Manager")
	if not _default_outgoing_name():
		frappe.throw(_("Configure and save the SMTP account first"))
	recipient = frappe.db.get_value("User", frappe.session.user, "email")
	frappe.sendmail(
		recipients=[recipient],
		subject=_("Unpress Studio test email"),
		message=_("Your outgoing email settings work."),
		now=True,
	)
	return {"sent_to": recipient}
