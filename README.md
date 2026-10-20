# ProxyForge MVP — zero-config local start

Run `docker compose up -d --build` and open http://127.0.0.1:8080.

For the current MVP interface, retrieve your **randomly generated** local Admin Token with:

```bash
docker compose exec api cat /run/proxyforge/admin_token
```

Paste it into the GUI Connection form. No `.env` is needed for a local start. Three independent random credentials are generated once in a persistent Docker volume. Never expose the Admin Token publicly. To register the bundled demo agent use URL `http://agent:8000` and retrieve the Agent Token with `docker compose exec agent cat /run/proxyforge/agent_token`.

The `bootstrap` container only creates secrets that do not already exist. Do not delete the `proxyforge_secrets` volume casually, as it will rotate the local credentials.

Remote agent enrollment requires HTTPS endpoints, a trusted certificate, an exact `AGENT_ALLOWED_URLS` allowlist, and separate agent credentials. No remote endpoints are allowed by default. To configure remote enrollment, follow the enrollment section of the prior version documentation or configure these values deliberately. The local default does **not** automatically connect to 192.168.44.181.

**Limitations:** This is still a development MVP. Deployment remains dry-run / intentionally blocked; there is no production login, RBAC or full config import. Do not expose the demo publicly or use it to manage production proxies.
