# Unpress Cloud provisioning API — the bridge the supastarter portal calls to
# create/list/publish tenant sites and mint edit (SSO) links. Wraps the mutu
# shell scripts. Bearer-token auth; bind to 127.0.0.1, expose via Caddy+TLS.
import glob
import os
import subprocess

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, constr

TOKEN = os.environ["UNPRESS_API_TOKEN"]
SCRIPTS = os.path.expanduser("~/GitHub/unpress/scripts/mutu")
SITES_ROOT = os.environ.get("UNPRESS_SITES_ROOT", "/var/www/sites")
BASE = os.environ.get("UNPRESS_BASE_DOMAIN", "unpress.cloud")

app = FastAPI(title="Unpress Cloud Provisioning API", version="0.1")


def _auth(authorization: str | None):
	if authorization != f"Bearer {TOKEN}":
		raise HTTPException(status_code=401, detail="unauthorized")


def _run(args, timeout):
	r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
	if r.returncode != 0:
		raise HTTPException(status_code=500, detail=(r.stderr or r.stdout)[-600:])
	return r.stdout.strip()


def _urls(slug: str):
	return {
		"slug": slug,
		"site_url": f"https://{slug}.sites.{BASE}",
		"studio_url": f"https://{slug}.studio.{BASE}/builder",
	}


class SiteIn(BaseModel):
	slug: constr(pattern=r"^[a-z0-9][a-z0-9-]{1,40}$")
	name: str | None = None


@app.get("/v1/health")
def health():
	return {"ok": True}


@app.get("/v1/sites")
def list_sites(authorization: str = Header(None)):
	_auth(authorization)
	slugs = sorted(
		os.path.basename(p) for p in glob.glob(f"{SITES_ROOT}/*") if os.path.isdir(p)
	)
	return {"sites": [_urls(s) for s in slugs]}


@app.post("/v1/sites")
def create_site(body: SiteIn, authorization: str = Header(None)):
	_auth(authorization)
	_run(["bash", f"{SCRIPTS}/add-unpress-site.sh", body.slug, body.name or body.slug], timeout=900)
	return _urls(body.slug)


@app.post("/v1/sites/{slug}/publish")
def publish(slug: str, authorization: str = Header(None)):
	_auth(authorization)
	out = _run(["bash", f"{SCRIPTS}/publish-site.sh", slug, f"{slug}.studio.localhost"], timeout=600)
	return {"published": True, "detail": out.splitlines()[-1] if out else ""}


@app.get("/v1/sites/{slug}/edit-link")
def edit_link(slug: str, authorization: str = Header(None)):
	_auth(authorization)
	out = _run(["bash", f"{SCRIPTS}/edit-link.sh", slug], timeout=90)
	return {"url": out.splitlines()[-1] if out else ""}
