# Fetch the WXR export straight from a WordPress site: log into wp-admin with
# the customer's credentials and download /wp-admin/export.php. This is what
# unlocks a real 1-click migration (no manual export step for the user).
import requests

import frappe
from frappe import _

UA = "Mozilla/5.0 (compatible; UnpressMigrator/1.0)"


def fetch_wxr(base_url: str, username: str, password: str) -> str:
	base = base_url.rstrip("/")
	session = requests.Session()
	session.headers["User-Agent"] = UA

	# prime cookies (some setups require the test cookie)
	session.get(f"{base}/wp-login.php", timeout=30)
	session.cookies.set("wordpress_test_cookie", "WP Cookie check")

	login = session.post(
		f"{base}/wp-login.php",
		data={
			"log": username,
			"pwd": password,
			"wp-submit": "Log In",
			"redirect_to": f"{base}/wp-admin/",
			"testcookie": "1",
		},
		timeout=30,
		allow_redirects=True,
	)
	if not any(c.name.startswith("wordpress_logged_in") for c in session.cookies):
		frappe.throw(_("WordPress login failed — check the username and password"))

	export = session.get(
		f"{base}/wp-admin/export.php",
		params={"download": "true", "content": "all"},
		timeout=180,
	)
	text = export.text
	if export.status_code != 200 or "<rss" not in text[:2000]:
		frappe.throw(_("Could not download the WordPress export (export.php)"))
	return text
