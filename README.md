# ProxyForge MVP — controller and agent

Start the Windows controller with `docker compose up -d --build`. Open `http://127.0.0.1:8080`.

## Central Admin Token configuration

Set `ADMIN_TOKEN` in the `.env` file next to `docker-compose.yml`:

```dotenv
ADMIN_TOKEN=replace-with-a-unique-random-secret-of-at-least-32-characters
```

Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
Apply changes with `docker compose up -d --force-recreate api`. The API uses the environment variable **first**. If it is empty or unset, the controller uses its auto-generated token in the persistent `proxyforge_secrets` volume. An explicitly configured token shorter than 8 characters fails with a clear configuration error (never silently falls back). When the variable is empty or absent, a persistent generated token is used.

When no environment override is configured, retrieve the generated token with `docker compose exec -T api cat /run/proxyforge/admin_token`. **When ADMIN_TOKEN is configured, the file is not the active token.** Use the configured environment value in the GUI instead.

Check authorization (PowerShell):

```powershell
$token = (Get-Content .env | Where-Object { $_ -match '^ADMIN_TOKEN=' } | Select-Object -First 1) -replace '^ADMIN_TOKEN=', ''
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/nodes' -Headers @{ 'X-Admin-Token' = $token }
```

The repository contains an empty `.env` template. **Never commit real token values:** `.env` is tracked; check `git diff` before committing and keep real secrets out of commits and chats. A previously exposed token must be rotated. Changing ADMIN_TOKEN invalidates the previous token after the API container is recreated.

## Limitations

The controller and remote agent are development MVP components. Remote agent enrollment requires HTTPS, trusted certificates, explicit allowlists, and separate agent credentials. Agent apply is dry-run / intentionally blocked; there is no production login, RBAC, or full config import. Do not expose the MVP publicly.

## Agent token configuration

Both controller and agent accept explicit secrets from the same local `.env` format:

```dotenv
ADMIN_TOKEN=<unique-random-value-at-least-32-characters>
AGENT_TOKEN=<different-unique-random-value-at-least-32-characters>
```

Edit `.env` directly, then set **different randomly generated 8+ character values** for `ADMIN_TOKEN` and `AGENT_TOKEN`. Never use `changeme123`: do not use it as a real credential. To use a generated controller token instead, leave `ADMIN_TOKEN` empty. Keep `.env` out of Git. On the controller run `docker compose up -d --force-recreate api`; on the Linux VM run `docker compose -f docker-compose.agent.yml up -d --force-recreate agent`. A configured `ADMIN_TOKEN` is authoritative: an invalid short value produces an explicit startup error rather than using another token. When unset, the controller uses the persistent generated token.

## Private-network HTTP agents (development only)

Remote nodes require HTTPS by default. For a lab agent such as `http://192.168.44.181:8001`, set `ALLOW_HTTP_AGENTS=true` in the **controller's** local `.env`, then run `docker compose up -d --force-recreate api`. The GUI can then register the private-IP HTTP URL. This setting does not permit public-IP HTTP endpoints or arbitrary HTTP DNS hostnames. It does **not** encrypt the agent token on the network; use HTTPS outside isolated labs. Leave `ALLOW_HTTP_AGENTS=false` for production.
