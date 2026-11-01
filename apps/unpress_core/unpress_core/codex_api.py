# Pair the Studio with a local Codex CLI (ChatGPT plan) from Settings > AI.
#
# Two ways in, both server-side only — no credential ever reaches the browser:
#   1. device code: the CLI prints a URL + a code, the user validates them on
#      any device, we poll until the CLI reports "logged in";
#   2. access token: pasted once and piped to `codex login --with-access-token`.
# Codex stores the resulting credentials itself under CODEX_HOME.
import os
import re
import subprocess


import frappe
from frappe import _

from unpress_core.ai.providers.codex_provider import CodexProvider

# progress of a device-code login, shared with the poller
_LOGIN_CACHE_KEY = "unpress_codex_device_login"
_LOGIN_TTL = 900

# the CLI colours its output even with --color never on some paths
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
URL_RE = re.compile(r"https?://[^\s\"'<>]+")
# device codes are short, dash-separated and upper-case (e.g. ABCD-1234)
CODE_RE = re.compile(r"\b[A-Z0-9]{3,8}-[A-Z0-9]{3,8}\b")


def _only_admin():
	"""System Manager, and only where Codex is deliberately switched on.

	MULTI-TENANCY: Codex stores its credentials under CODEX_HOME, which belongs
	to the bench's Linux user — so it is shared by EVERY site on that bench,
	while each tenant is System Manager of their own site. Without this gate one
	tenant could pair their nominative ChatGPT plan and every other tenant would
	spend it. The flag therefore has to be set per site, out of band
	(`bench --site X set-config codex_enabled 1`), which a tenant cannot do.
	"""
	frappe.only_for("System Manager")
	if not frappe.utils.cint(frappe.conf.get("codex_enabled")):
		frappe.throw(
			_(
				"Codex is not enabled on this site. A ChatGPT plan is personal and its "
				"credentials are shared by every site on this server, so it must be "
				"switched on deliberately (codex_enabled in site_config.json)."
			),
			frappe.PermissionError,
		)


@frappe.whitelist()
def get_codex_status() -> dict:
	"""Is the CLI installed, and is this machine paired?"""
	_only_admin()
	binary = CodexProvider.binary()
	logged_in, message = CodexProvider.login_status()
	pending = frappe.cache().get_value(_LOGIN_CACHE_KEY) or {}
	return {
		"installed": bool(binary),
		"binary": binary,
		"logged_in": logged_in,
		"message": message,
		"pending_login": pending if not logged_in else {},
	}


def _read_instructions(proc, deadline: float) -> dict:
	"""Read the CLI's first lines (non-blocking) until it has printed the URL.

	Deliberately no worker thread: frappe's `conf`, `cache` and `db` all live in
	thread-local storage, so a thread started from a request has none of them.
	"""
	import select
	import time

	found = {"url": None, "code": None}
	fd = proc.stdout
	buffer = ""
	# keep reading a little past the URL: the code is printed on a later line
	while time.time() < deadline and not (found["url"] and found["code"]):
		ready, _w, _e = select.select([fd], [], [], 0.5)
		if not ready:
			if proc.poll() is not None:
				break
			continue
		chunk = os.read(fd.fileno(), 4096).decode("utf-8", "replace")
		if not chunk:
			break
		buffer += ANSI_RE.sub("", chunk)
		if found["url"] is None:
			match = URL_RE.search(buffer)
			if match:
				found["url"] = match.group(0).rstrip(".,")
		if found["code"] is None:
			match = CODE_RE.search(buffer)
			if match:
				found["code"] = match.group(0)
	found["output"] = buffer[-600:]
	return found


@frappe.whitelist()
def start_codex_login() -> dict:
	"""Kick off the device-code flow and return the URL + code to show.

	The CLI process is left running (detached) while the user validates on
	another device; `check_codex_login` polls the resulting login state.
	"""
	_only_admin()
	binary = CodexProvider.binary()
	if not binary:
		frappe.throw(_("Codex CLI not found on this server"))

	logged_in, message = CodexProvider.login_status()
	if logged_in:
		return {"status": "already", "message": message}

	import time

	proc = subprocess.Popen(
		[binary, "login", "--device-auth"],
		stdin=subprocess.DEVNULL,
		stdout=subprocess.PIPE,
		stderr=subprocess.STDOUT,
		env=CodexProvider._env(),
		start_new_session=True,  # survives the end of this request
	)
	found = _read_instructions(proc, deadline=time.time() + 25)

	state = {
		"status": "waiting_for_user" if found["url"] else "failed",
		"url": found["url"],
		"code": found["code"],
		"pid": proc.pid,
		"error": None if found["url"] else (found["output"] or "the CLI printed no URL"),
	}
	frappe.cache().set_value(_LOGIN_CACHE_KEY, state, expires_in_sec=_LOGIN_TTL)
	return state


@frappe.whitelist()
def check_codex_login() -> dict:
	"""Poll while the user validates the device code."""
	_only_admin()
	logged_in, message = CodexProvider.login_status()
	state = frappe.cache().get_value(_LOGIN_CACHE_KEY) or {}
	if logged_in:
		frappe.cache().delete_value(_LOGIN_CACHE_KEY)
	return {
		"logged_in": logged_in,
		"message": message,
		"status": "done" if logged_in else state.get("status", "unknown"),
		"url": state.get("url"),
		"code": state.get("code"),
		"error": state.get("error"),
	}


@frappe.whitelist()
def login_with_token(token: str) -> dict:
	"""Pair using an access token, for servers where opening a browser-based
	device flow is impractical. The token is piped on stdin and never stored by
	us — Codex writes its own credentials under CODEX_HOME."""
	_only_admin()
	binary = CodexProvider.binary()
	if not binary:
		frappe.throw(_("Codex CLI not found on this server"))
	if not (token or "").strip():
		frappe.throw(_("Paste an access token first"))

	proc = subprocess.run(
		[binary, "login", "--with-access-token"],
		input=token.strip(),
		capture_output=True,
		text=True,
		timeout=60,
		env=CodexProvider._env(),
	)
	logged_in, message = CodexProvider.login_status()
	if not logged_in:
		detail = (proc.stderr or proc.stdout or "").strip().splitlines()
		frappe.throw(_("Pairing failed: {0}").format(detail[-1][:200] if detail else message))
	return {"logged_in": True, "message": message}


@frappe.whitelist()
def logout_codex() -> dict:
	"""Unpair this server (removes the credentials Codex stored)."""
	_only_admin()
	binary = CodexProvider.binary()
	if not binary:
		frappe.throw(_("Codex CLI not found on this server"))
	subprocess.run([binary, "logout"], capture_output=True, text=True, timeout=60, env=CodexProvider._env())
	logged_in, message = CodexProvider.login_status()
	return {"logged_in": logged_in, "message": message}


@frappe.whitelist()
def test_codex() -> dict:
	"""One tiny structured round-trip, to prove text generation works."""
	_only_admin()
	logged_in, message = CodexProvider.login_status()
	if not logged_in:
		return {"success": False, "message": message}

	provider = CodexProvider()
	schema = {
		"type": "object",
		"properties": {"ok": {"type": "boolean"}, "language": {"type": "string"}},
		"required": ["ok", "language"],
		"additionalProperties": False,
	}
	try:
		raw = provider._run(
			"Answer with ok=true and language set to the language of this sentence.",
			schema=schema,
			timeout=180,
		)
	except Exception as e:
		return {"success": False, "message": str(e)[:300]}
	return {
		"success": True,
		"backend": "codex",
		"message": _("Connected — {0}, model: {1}").format(
			message, provider.model or _("the plan's default")
		),
		"sample": raw[:200],
	}
