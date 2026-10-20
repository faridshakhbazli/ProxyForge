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


## Automatic agent discovery (experimental)

The Linux agent detects installed `haproxy` and `nginx` binaries, selected engine, standard config path and systemd service state via authenticated `GET /discover`. It does not modify configuration. Install the agent on the target VM and configure:

```bash
export AGENT_TOKEN='<unique-agent-token-at-least-32-characters>'
export PROXY_ENGINE=haproxy
export NODE_NAME=lb-01
export CONTROLLER_URL=https://proxyforge.example.internal
export AGENT_PUBLIC_URL=https://lb-01.example.internal:8443
export ENROLLMENT_TOKEN='<same-enrollment-secret-as-control-plane>'
uvicorn main:app --host 127.0.0.1 --port 8000
```

Publish the agent with a TLS reverse proxy using a trusted certificate; the agent's built-in Uvicorn listener above is loopback-only. Configure the control plane's `AGENT_ALLOWED_URLS` as an exact comma-separated allowlist of trusted agent HTTPS origins, and `ENROLLMENT_TOKEN` as a distinct strong secret. Expose the control plane through a trusted HTTPS endpoint reachable from the VM; the default Compose API is bound to Windows loopback and is **not** reachable from remote VMs. The agent attempts enrollment every 60 seconds; the GUI refreshes the node list every 15 seconds. Enrollment with an existing node name requires matching engine and URL; agent tokens rotate on re-enrollment. Protect the enrollment token: anyone possessing it can register a node from an allowed URL. Rotate after provisioning and restrict access to the enrollment endpoint.

**Scope:** this adds automatic detection and enrollment, not safe real configuration deployment. The existing deploy button remains dry-run/blocked; never point it at a production HAProxy without full-context validation, backup and rollback. This version cannot automatically import arbitrary ACLs or edit existing configs.
