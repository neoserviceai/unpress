# Studio user management — backend for the builder Settings > Users tab.
# Two levels only (keep it simple): "editor" = Website Manager (full builder
# access via the Builder Page permissions), "admin" = + System Manager.
# Passwords are set by the admin directly (self-host studios rarely have SMTP).
import frappe
from frappe import _

EDITOR_ROLE = "Website Manager"
ADMIN_ROLE = "System Manager"

PROTECTED_USERS = ("Administrator", "Guest")


def _only_admin():
	frappe.only_for(ADMIN_ROLE)


def _resolve_role(user_name):
	roles = set(frappe.get_roles(user_name))
	return "admin" if ADMIN_ROLE in roles else "editor"


@frappe.whitelist()
def list_studio_users():
	_only_admin()
	users = frappe.get_all(
		"User",
		filters={"user_type": "System User", "name": ["not in", list(PROTECTED_USERS)]},
		fields=["name", "full_name", "enabled", "last_active"],
		order_by="creation asc",
	)
	for user in users:
		user["role"] = _resolve_role(user["name"])
	return {"users": users, "current_user": frappe.session.user}


@frappe.whitelist()
def add_studio_user(email, full_name, password, role="editor"):
	_only_admin()
	if frappe.db.exists("User", email):
		frappe.throw(_("User {0} already exists").format(email))

	user = frappe.new_doc("User")
	user.email = email
	user.first_name = full_name
	user.user_type = "System User"
	user.send_welcome_email = 0
	user.new_password = password
	user.append("roles", {"role": EDITOR_ROLE})
	if role == "admin":
		user.append("roles", {"role": ADMIN_ROLE})
	user.insert()
	return {"name": user.name, "role": _resolve_role(user.name)}


@frappe.whitelist()
def toggle_studio_user(email, enabled):
	_only_admin()
	if email in PROTECTED_USERS:
		frappe.throw(_("This account cannot be modified"))
	if email == frappe.session.user:
		frappe.throw(_("You cannot disable your own account"))
	user = frappe.get_doc("User", email)
	user.enabled = int(enabled)
	user.save()
	return {"enabled": user.enabled}


@frappe.whitelist()
def set_studio_user_role(email, role):
	_only_admin()
	if email in PROTECTED_USERS:
		frappe.throw(_("This account cannot be modified"))
	if email == frappe.session.user:
		frappe.throw(_("You cannot change your own role"))
	user = frappe.get_doc("User", email)
	has_admin = ADMIN_ROLE in {r.role for r in user.roles}
	if role == "admin" and not has_admin:
		user.append("roles", {"role": ADMIN_ROLE})
		user.save()
	elif role == "editor" and has_admin:
		user.roles = [r for r in user.roles if r.role != ADMIN_ROLE]
		user.save()
	return {"role": _resolve_role(email)}


@frappe.whitelist()
def set_studio_user_password(email, password):
	_only_admin()
	if email in PROTECTED_USERS:
		frappe.throw(_("This account cannot be modified"))
	from frappe.utils.password import update_password

	update_password(email, password)
	return {"ok": True}
