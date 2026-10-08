# ProxyForge MVP v0.1

An initial functional control-plane prototype supporting local and remote agent registration, HAProxy/NGINX upstream definitions, previews, and dry-run dispatch.

## Start

```bash
cp .env.example .env
# Edit .env and set two independent, strong random tokens.
docker compose up -d --build
```

Open http://localhost:8080 and enter your ADMIN_TOKEN. Add the bundled HAProxy agent using URL `http://agent:8000` and your AGENT_TOKEN. Create an upstream, preview, and press Deploy to receive a dry-run response.

For remote access, put the UI and API behind an authenticated TLS reverse proxy and restrict agent connectivity to a trusted private network. Never expose the demo HTTP agent publicly. The `http://agent:8000` address works only within this Docker Compose network.

## Important limitations

- **No production deploy yet.** Agent refuses actual apply even if ENABLE_APPLY=true. This is intentional until full-context syntax validation, atomic installation, reload, health checks and rollback are implemented.
- No production-grade authentication or RBAC. Admin token is a temporary MVP mechanism; do not use in a shared or internet-facing environment.
- No TLS management, frontends, ACLs, log viewer, discovery, imports, diff or audit log yet.
- Upstream definitions are stored in SQLite for zero-dependency setup; migrate to PostgreSQL for production.
- NGINX OSS has different health-check capabilities from HAProxy and NGINX Plus.
- A remote agent requires HTTPS with certificate verification and network allowlisting. The central API currently stores its token in plaintext SQLite; encrypt secrets before production.
- The API's node URL field must be restricted to an administrator-approved allowlist in production to prevent SSRF.
- This demo is for local development only.
