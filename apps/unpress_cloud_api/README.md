# unpress_cloud_api

Provisioning API for the mutualized edition. The supastarter portal
(`neoserviceai/unpress-cloud`) calls it to create tenant sites, list them, publish,
and mint SSO edit links. Wraps `scripts/mutu/*.sh`.

Run (on the mutu server, as the user owning the scripts + docker + sudo):

```bash
python3 -m venv ~/unpress-api-venv
~/unpress-api-venv/bin/pip install fastapi uvicorn
UNPRESS_API_TOKEN=xxx ~/unpress-api-venv/bin/uvicorn api:app --host 127.0.0.1 --port 8090
```

Expose behind Caddy (TLS) at `api.unpress.cloud`. Bearer-token auth on all
`/v1/*` routes except `/v1/health`.
