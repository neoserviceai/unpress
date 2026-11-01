"""Installing and removing plugins that are Frappe apps.

Level 1 — a plugin the bench already carries — is a row and a switch
(`plugins.py`). This is level 2: putting a new app on the bench, which is a
different kind of operation and deserves to be treated as one.

What it actually costs. `bench get-app` is a git clone, a pip install, a yarn
build and a restart — minutes, not milliseconds, and it writes to the bench
directory. `bench install-app` then creates the app's tables on the site. So
this runs as a background job with progress, never in a request.

What it can do. An installed Frappe app has full server access: its hooks run
on every request, its code runs as the site user. There is no sandbox and no
review here. Which is why:

- only System Manager may call it;
- the git URL is explicit and echoed back — nothing is installed from a name
  alone, and there is no registry of URLs to be tricked into trusting;
- a site can pin an allowlist (`unpress_plugin_sources` in site_config) and
  then only those hosts are reachable;
- the whole thing can be switched off (`unpress_allow_plugin_install: 0`),
  which is the right default for a hosted fleet where the operator, not the
  tenant, decides what runs.

Removing is the mirror image and is genuinely destructive: `bench uninstall-app`
drops the module's tables. Disabling — which keeps everything — is the answer
almost every time, so it is the one the UI offers first.
"""

import os
import re
import subprocess

import frappe
from frappe import _

from unpress_core import plugins

PROGRESS_PREFIX = "unpress_plugin_install:"
PROGRESS_TTL = 3600

# git URL, nothing else. No local paths (a path would let a caller point the
# installer at anything on the filesystem), no ssh with embedded credentials.
GIT_URL = re.compile(r"^https://[A-Za-z0-9._~-]+(?:\.[A-Za-z]{2,})(?:/[A-Za-z0-9._~/-]+?)(?:\.git)?/?$")
BRANCH = re.compile(r"^[A-Za-z0-9._/-]{1,100}$")


def _bench_path() -> str:
	"""The bench directory — two levels above sites/."""
	return os.path.abspath(os.path.join(frappe.utils.get_bench_path()))


def installs_allowed() -> bool:
	"""Off by default on a hosted site; the operator decides what runs there."""
	value = frappe.conf.get("unpress_allow_plugin_install")
	if value is None:
		# a self-hosted bench in developer mode is the case this is for
		return bool(frappe.conf.get("developer_mode"))
	return bool(value)


def _check_source(git_url: str):
	if not GIT_URL.match(git_url or ""):
		frappe.throw(_("That does not look like an https git URL."))

	allowed = frappe.conf.get("unpress_plugin_sources")
	if not allowed:
		return
	host = git_url.split("/")[2].lower()
	if host not in {str(h).lower() for h in allowed}:
		frappe.throw(_("{0} is not an allowed plugin source on this site.").format(host))


def _progress(progress_id: str, step: str, status: str = "running", **extra):
	frappe.cache().set_value(
		PROGRESS_PREFIX + progress_id,
		{"job_id": progress_id, "status": status, "step": step, **extra},
		expires_in_sec=PROGRESS_TTL,
	)


def _run(command: list, progress_id: str, step: str) -> str:
	"""One bench command, with its output kept for the failure message."""
	_progress(progress_id, step)
	result = subprocess.run(
		command,
		cwd=_bench_path(),
		capture_output=True,
		text=True,
		# a yarn build on a cold cache is the long pole here
		timeout=1800,
	)
	if result.returncode != 0:
		tail = (result.stderr or result.stdout or "").strip().splitlines()[-12:]
		raise RuntimeError(f"{step}\n" + "\n".join(tail))
	return result.stdout


@frappe.whitelist()
def install_plugin(git_url: str, branch: str | None = None) -> dict:
	"""Put a new app on the bench and install it on this site."""
	frappe.only_for("System Manager")
	if not installs_allowed():
		frappe.throw(
			_("Installing plugins from a URL is turned off on this site."),
			frappe.PermissionError,
		)

	git_url = (git_url or "").strip()
	branch = (branch or "").strip() or None
	_check_source(git_url)
	if branch and not BRANCH.match(branch):
		frappe.throw(_("That branch name is not valid."))

	progress_id = frappe.generate_hash(length=10)
	_progress(progress_id, _("Queued"), git_url=git_url, branch=branch)

	frappe.enqueue(
		"unpress_core.plugin_install._install_worker",
		queue="long",
		timeout=2400,
		progress_id=progress_id,
		git_url=git_url,
		branch=branch,
		site=frappe.local.site,
	)
	return {"job_id": progress_id}


def _install_worker(progress_id: str, git_url: str, branch: str | None, site: str):
	# bench names the directory after the repo; that is the app name
	app_name = git_url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
	try:
		# An app removed from a site stays on the bench, so re-adding it to the
		# site must not try to clone over a directory that is already there.
		if os.path.isdir(os.path.join(_bench_path(), "apps", app_name)):
			_progress(progress_id, _("Already on this bench"), app_name=app_name)
		else:
			command = ["bench", "get-app", "--resolve-deps"]
			if branch:
				command += ["--branch", branch]
			command.append(git_url)
			_run(command, progress_id, _("Fetching and building the app"))

		_run(
			["bench", "--site", site, "install-app", app_name],
			progress_id,
			_("Installing on the site"),
		)

		_progress(progress_id, _("Registering"), app_name=app_name)
		plugins.sync_plugins(app_name)
		_register_unknown(app_name, git_url, branch)

		_progress(
			progress_id,
			_("Installed"),
			status="done",
			app_name=app_name,
			# the new app's hooks are only live for workers started after this
			needs_restart=True,
		)
	except Exception as e:
		frappe.log_error("Plugin install failed", f"{git_url}\n{e}")
		_progress(progress_id, str(e)[:600], status="failed", app_name=app_name)


def _register_unknown(app_name: str, git_url: str, branch: str | None):
	"""An app with no built-in manifest still gets a row, so it can be switched.

	Without this, installing something we do not ship would leave a capability
	with no off switch — which is the whole point of the registry.
	"""
	if not frappe.db.exists("DocType", plugins.REGISTRY_DOCTYPE):
		return
	if app_name in plugins.BUILT_IN_BY_NAME or frappe.db.exists(plugins.REGISTRY_DOCTYPE, app_name):
		return

	doc = frappe.new_doc(plugins.REGISTRY_DOCTYPE)
	doc.plugin_name = app_name
	doc.title = app_name.replace("_", " ").title()
	doc.description = git_url + (f" ({branch})" if branch else "")
	doc.app_name = app_name
	doc.icon = "lucide-puzzle"
	doc.source = "Manual"
	doc.is_available = 1
	doc.enabled = 1
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	plugins.clear_cache()


@frappe.whitelist()
def install_status(job_id: str) -> dict:
	frappe.only_for("System Manager")
	return frappe.cache().get_value(PROGRESS_PREFIX + job_id) or {
		"job_id": job_id,
		"status": "unknown",
		"step": _("No such job"),
	}


@frappe.whitelist()
def uninstall_plugin(plugin_name: str) -> dict:
	"""Remove the app from the site. This drops its tables.

	Deliberately separate from disabling, and deliberately not the thing the UI
	suggests: a plugin that is off keeps every article, every migration, every
	setting, and comes back instantly. Removal does not.
	"""
	frappe.only_for("System Manager")
	if not installs_allowed():
		frappe.throw(
			_("Removing plugins is turned off on this site."),
			frappe.PermissionError,
		)

	doc = frappe.get_doc(plugins.REGISTRY_DOCTYPE, plugin_name)
	if doc.is_core:
		frappe.throw(_("{0} cannot be removed.").format(_(doc.title)))
	if not doc.app_name:
		frappe.throw(_("{0} is not a separate app; there is nothing to remove.").format(_(doc.title)))

	progress_id = frappe.generate_hash(length=10)
	_progress(progress_id, _("Queued"), app_name=doc.app_name)

	frappe.enqueue(
		"unpress_core.plugin_install._uninstall_worker",
		queue="long",
		timeout=1800,
		progress_id=progress_id,
		app_name=doc.app_name,
		plugin_name=plugin_name,
		site=frappe.local.site,
	)
	return {"job_id": progress_id}


def _uninstall_worker(progress_id: str, app_name: str, plugin_name: str, site: str):
	try:
		# bench takes a backup first unless told not to; keep that.
		_run(
			["bench", "--site", site, "uninstall-app", app_name, "--yes"],
			progress_id,
			_("Removing from the site"),
		)
		if frappe.db.exists(plugins.REGISTRY_DOCTYPE, plugin_name):
			frappe.db.set_value(plugins.REGISTRY_DOCTYPE, plugin_name, "is_available", 0)
			frappe.db.commit()
			plugins.clear_cache()
		_progress(progress_id, _("Removed"), status="done", app_name=app_name)
	except Exception as e:
		frappe.log_error("Plugin uninstall failed", f"{app_name}\n{e}")
		_progress(progress_id, str(e)[:600], status="failed", app_name=app_name)


@frappe.whitelist()
def install_capability() -> dict:
	"""Whether the UI should offer installing at all."""
	frappe.only_for(("System Manager", "Website Manager"))
	return {
		"allowed": installs_allowed() and "System Manager" in frappe.get_roles(),
		"sources": frappe.conf.get("unpress_plugin_sources") or [],
	}
