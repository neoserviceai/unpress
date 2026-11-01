# The site logo, in one place.
#
# A logo can arrive from two doors — the Theme tab, or dropped into the AI chat
# — and both must land in the same spot: the site chrome that every page
# renders. Anything else means a client uploads their logo to the assistant and
# their site keeps showing someone else's.
#
# STABLE PATH. The file is always written to /files/logo-default.png, whatever
# the uploaded file was called. A managed fleet references that one path across
# every instance (provisioning drops a per-client file there), so a new upload
# has to REPLACE the bytes, never mint a new URL. The rendered <img> carries a
# ?v= token derived from the content so browsers still see the change.
import hashlib
import os

import frappe
from frappe import _

LOGO_PATH = "/files/logo-default.png"
LOGO_ROLES = ("System Manager", "Website Manager")


def _public_files_dir() -> str:
    return frappe.get_site_path("public", "files")


def logo_disk_path() -> str:
    return os.path.join(_public_files_dir(), os.path.basename(LOGO_PATH))


def logo_version() -> str:
    """Short content hash, or '' when no logo has been uploaded.

    Used as a cache-buster in the rendered URL so the stable path can change
    content without every visitor keeping the old image.
    """
    path = logo_disk_path()
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    except OSError:
        return ""


def logo_url() -> str:
    """The stable path, with a version token when a logo exists."""
    version = logo_version()
    return f"{LOGO_PATH}?v={version}" if version else LOGO_PATH


def _read_uploaded(file_url: str) -> bytes:
    """Bytes of an uploaded File doc, private or public."""
    name = frappe.db.get_value("File", {"file_url": file_url}, "name")
    if not name:
        frappe.throw(_("That file is not attached to this site."))
    return frappe.get_doc("File", name).get_content()


def apply_logo(file_url: str, config_name: str | None = None) -> dict:
    """Write an uploaded image to the stable logo path and point the chrome at it.

    Callable from the server (the chat's upload_logo does exactly this) as well
    as from the whitelisted endpoint below.
    """
    content = _read_uploaded(file_url)
    if not content:
        frappe.throw(_("That file is empty."))

    os.makedirs(_public_files_dir(), exist_ok=True)
    with open(logo_disk_path(), "wb") as f:
        f.write(content)

    # Point the chrome at the stable path — never at the uploaded file's own
    # URL, which would defeat the whole purpose.
    doctype, name = _chrome_target(config_name)
    frappe.db.set_value(doctype, name, "logo_image", LOGO_PATH)
    frappe.db.set_value(doctype, name, "logo_type", "Image")
    frappe.clear_cache()

    return {"success": True, "url": logo_url(), "version": logo_version()}


def _chrome_target(config_name: str | None) -> tuple[str, str]:
    """Which chrome doc to write: a profile's variant when one is targeted,
    otherwise the site-wide Single."""
    if config_name and frappe.db.exists("Website Header Footer Variant", config_name):
        return "Website Header Footer Variant", config_name
    return "Website Header Footer Config", "Website Header Footer Config"


@frappe.whitelist()
def set_logo(file_url: str, profile: str | None = None) -> dict:
    """Theme tab entry point."""
    frappe.only_for(LOGO_ROLES)
    if not file_url:
        frappe.throw(_("No file provided."))
    return apply_logo(file_url, profile)


@frappe.whitelist()
def get_logo(profile: str | None = None) -> dict:
    """What the Theme tab shows: the current logo and where it comes from."""
    frappe.only_for(LOGO_ROLES)
    doctype, name = _chrome_target(profile)
    configured = frappe.db.get_value(doctype, name, "logo_image")
    if configured and configured != LOGO_PATH:
        # someone set an explicit URL by hand — respect it
        return {"url": configured, "custom": True}
    return {"url": logo_url() if logo_version() else "", "custom": False}
