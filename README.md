# m365-gate

A drop-in **Microsoft 365 (Entra ID) sign-in + HTTPS** front door for any HTTP app run with Docker Compose. Add about 5 lines to a project's compose file and fill in a `.env`. The app gets:

- **HTTPS** with an automatic Let's Encrypt certificate via the Cloudflare DNS-01 challenge. It works on any port and doesn't need 80/443.
- **Microsoft sign-in** for your tenant, limited to an allow-list of UPNs and/or Entra groups.
- **`/logout`**, which ends both the app session and the Microsoft session.
- **The signed-in identity** passed to your app as `X-Forwarded-Email`, `X-Forwarded-User` and `X-Forwarded-Preferred-Username` headers, so the app needs no auth code. The `/oauth2/userinfo` endpoint gives the same as JSON for browser code.
- **A private app:** it sits on an internal Docker network with no published port, so it can only be reached through the gate.

```
browser ──HTTPS :GATE_PORT──▶ gate-caddy ──▶ gate-proxy ──▶ your app
                              TLS            oauth2-proxy    gate_backend network
                              (Let's         Entra ID        (internal, no ports)
                              Encrypt)       + allow-list
```

| Service | Role |
|---|---|
| `gate-caddy` | Caddy + Cloudflare DNS module: TLS, security headers, `/logout` |
| `gate-config` | One-shot job that validates settings and renders the oauth2-proxy config |
| `gate-proxy` | [oauth2-proxy](https://oauth2-proxy.github.io/oauth2-proxy/) v7.15.6 with the `entra-id` provider |

## Add it to a project

```bash
cd your-project
git submodule add -b main git@github.com:rh1gmus/m365-gate.git m365-gate
git -C m365-gate checkout v0.1.0          # pin a release
cp m365-gate/.env.example .env && chmod 600 .env    # then fill it in
echo .env >> .gitignore
```

```yaml
# your-project/docker-compose.yml
include:
  - path: ./m365-gate/compose.yaml
    env_file: ./.env

services:
  app:
    build: .
    networks: [gate_backend]   # and no `ports:`. The gate is the only way in.
```

In `.env`, set `GATE_UPSTREAM=http://app:8080`, i.e. your service name and the port the app listens on inside its container. Then:

```bash
docker compose build app && docker compose up -d
```

Add `m365-gate` to your app's `.dockerignore` if the build context is the project root.

### Before the first start

1. **DNS:** an A record for `GATE_HOST` pointing at the host. On Cloudflare, set it to **DNS only** (grey cloud). Cloudflare's proxy only forwards a few ports.
2. **Cloudflare API token:** the **Edit zone DNS** template, scoped to the zone, in `CF_DNS_API_TOKEN`.
3. **Entra app registration:** one per project. Follow [docs/entra-app-registration.md](docs/entra-app-registration.md), or run `scripts/register-entra-app.sh`, which uses the Azure CLI and writes the IDs and secret into `.env` without printing the secret.
4. **Cookie secret:** `head -c 32 /dev/urandom | base64 | tr '+/' '-_' | tr -d '='` → `OAUTH2_PROXY_COOKIE_SECRET`.

## Settings (`.env`)

| Variable | Required | Meaning |
|---|---|---|
| `GATE_HOST` | yes | Public DNS name |
| `GATE_PORT` | no (443) | HTTPS port to publish |
| `GATE_UPSTREAM` | yes | App URL on `gate_backend`, e.g. `http://app:8080` |
| `CF_DNS_API_TOKEN` | yes | Cloudflare token for DNS-01 |
| `ACME_EMAIL` | no | Let's Encrypt contact |
| `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET` | yes | App registration |
| `ALLOWED_EMAILS` | one of these two | Comma-separated UPNs, or `*` for the whole tenant |
| `ALLOWED_GROUPS` | one of these two | Comma-separated group object IDs. If both are set, a user must match both. |
| `OAUTH2_PROXY_COOKIE_SECRET` | yes | 32 random bytes, base64url |
| `GATE_SESSION_HOURS` | no (12) | Sign-in lifetime |
| `GATE_BIND` | no (0.0.0.0) | Host interface to bind |
| `GATE_CADDY_IMAGE` | no | Override the Caddy image |

Keep comments in `.env` on their own lines. Compose reads `KEY=   # note` as the value `# note`.

To change who can sign in, edit `.env`, then run `docker compose up -d --force-recreate gate-config gate-proxy`.

## Several gated apps on one host

Give each project its own `GATE_PORT`, or its own `GATE_HOST` on a different port. Each project's gate is fully separate, with its own containers, networks, certificate and app registration. Session cookies are named per port (`_m365gate_<port>`), so apps sharing a hostname don't overwrite each other's sign-in.

## The Caddy image

Caddy needs a custom build to include the Cloudflare DNS module. Compiling it takes about 12 minutes on a 1 vCPU VM, so `.github/workflows/caddy-image.yml` builds it on GitHub and publishes `ghcr.io/rh1gmus/m365-gate-caddy:2.10.2-cloudflare0.2.4-r<N>` (`r<N>` is the workflow's `IMAGE_REV`; it goes up when the Dockerfile changes without a version bump, so old digests stay valid). Compose pulls that image and falls back to building `./caddy` locally if the pull fails.

The package inherits this repo's **private** visibility. To pull it without a login, set the package to public under GitHub → Packages → m365-gate-caddy → Package settings. It contains only the Caddy binary. Or run `docker login ghcr.io` with a token that has `read:packages`.

**Don't use a bare `docker compose up --build`** in a consuming project. It rebuilds every service that has a `build:` section, so it recompiles Caddy even when the image is already present. Build only your app (`docker compose build app`), then run `docker compose up -d`.

To bump versions, change `CADDY_VERSION` / `CF_DNS_VERSION` in `caddy/Dockerfile` and the workflow, and the default tag in `compose.yaml`.

### Updating pins

Every image is pinned by digest (`tag@sha256:…`), so a moved or replaced tag can't change what runs. When you bump one:

1. Get the new digest: for the Caddy image, the `caddy-image` run summary prints it. For others, `docker buildx imagetools inspect <image:tag>` or the registry's `Docker-Content-Digest` header.
2. Check what you are about to trust. For a Caddy build, `caddy build-info` lists each Go module's hash, which can be compared with `https://sum.golang.org/lookup/<module>@<version>`.
3. Update the digest in `compose.yaml` (and `caddy/Dockerfile` for its base images). The workflow's actions are pinned to commit SHAs; the comment beside each names its release.

`gate-caddy` runs as a non-root user with no capabilities, so the first start after upgrading runs the one-shot `gate-caddy-perms`, which re-owns the certificate volumes. The image's Dockerfile strips the binary's file capability, which non-root Caddy could not start with.

## Security notes

- Single-tenant app registration plus an explicit allow-list. Identity comes from the `preferred_username` (UPN) claim, which the tenant controls, not the user-editable `email` claim.
- Session cookies are encrypted, `Secure`, `HttpOnly` and `SameSite=Lax`. HSTS, `X-Frame-Options: DENY` and `nosniff` are set.
- Hardening: every service runs read-only (Caddy keeps a `/tmp` tmpfs and its data volumes), with all capabilities dropped and `no-new-privileges`. `gate-caddy` runs as a non-root user (65532) and binds low ports through a container-scoped sysctl.
- Requests for any other Host name on the gate port get `421` and no body, not an empty `200`.
- Images and workflow actions are pinned by digest or commit SHA. See "Updating pins".
- Secrets live only in the consuming project's git-ignored `.env`. Don't share `docker compose config` output, because it prints them.
- Only `/ping` (oauth2-proxy liveness) is reachable without signing in.

## Example

[`examples/whoami`](examples/whoami) puts a tiny echo server behind the gate, so you can see the identity headers it passes. The reference consumer is [rh1gmus/dockerdashboard](https://github.com/rh1gmus/dockerdashboard).

## Layout

```
compose.yaml                     the module (include this)
caddy/Dockerfile, caddy/Caddyfile
config/render_config.py          validates settings, renders the oauth2-proxy config
scripts/register-entra-app.sh    optional: create the Entra app with the Azure CLI
docs/entra-app-registration.md   portal checklist, access options, troubleshooting
.github/workflows/caddy-image.yml   publishes the Caddy image to GHCR
examples/whoami/                 minimal consumer
MEMORY.md                        build and decision log
```
