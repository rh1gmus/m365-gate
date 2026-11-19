# MEMORY.md — m365-gate project log

Append-only log. Earlier entries are never edited or removed.

Entry format:

```
### <ISO timestamp UTC> — <type: chat | message | tool | process>
**Action:** <what was done>
**Detail:** <command, input, or summary>
**Result:** <output summary or status>
```

Timestamps come from `date -u` on the VM.

---

## Origin

This project was split out of `rh1gmus/dockerdashboard` (local: /claude/project-dockerdash). Its log covers how the sign-in layer was first built: Entra ID via oauth2-proxy, TLS via Caddy plus the Cloudflare DNS-01 challenge, a one-shot config renderer, and a /logout that also ends the Microsoft session. The log is also published as the claude.ai artifact https://claude.ai/artifact/1Hogap6NuWs5WYvn4fsjgc.

## Decisions

### Module shape (decided 2026-11-19T08:07Z)
- **What:** a self-contained Compose file (`compose.yaml`) with three services (`gate-caddy`, `gate-config`, `gate-proxy`) and two networks (`gate_edge`, `gate_backend`). Consuming projects pull it in with Compose `include:` from a git submodule pinned to a tag, and attach their app to `gate_backend`.
- **Why:** Compose `include` (Compose ≥ 2.20; this VM has 2.40.3) lets the gate's relative build contexts and mounts resolve against the module's own directory, so a project adds about 5 lines and an `.env`. A pinned submodule keeps each project on a known version, and upgrading it is a deliberate commit.
- **Parameters, not edits:** everything specific to a project comes from env vars: `GATE_HOST`, `GATE_PORT`, `GATE_UPSTREAM`, Entra IDs and secret, `ALLOWED_EMAILS`, optional `ALLOWED_GROUPS`. No container_name values are hard-coded, so several gated projects can run on one VM on different ports.
- **One Entra app registration per project:** each project gets its own secret and redirect URI and can be revoked on its own. Documented as a checklist plus an optional `az` CLI script.
- **Prebuilt Caddy image:** compiling Caddy with the Cloudflare module takes about 12 min on a 1 vCPU VM. A GitHub Actions workflow builds `ghcr.io/rh1gmus/m365-gate-caddy` with the repo's built-in GITHUB_TOKEN, so no personal token is needed to publish it. Compose also keeps a local `build:` fallback, so the gate works even if the image can't be pulled.
- **Unchanged from dockerdash:** single-tenant Entra, the `preferred_username` (UPN) claim, an explicit allow-list, cookies that are Secure/HttpOnly/SameSite=Lax with a 12 h expiry, the dashboard (now the app) on an internal-only network, and secrets only in a git-ignored `.env`.

---

## Log

### 2026-11-19T08:07:25Z — chat
**Action:** User created GitHub repo rh1gmus/m365-gate. Asked to move to /claude/project-m365-gate, keep a new MEMORY.md there, make it a git repo synced to GitHub, then build the proposed module
**Detail:** Proposal (from the dockerdash log): a reusable Compose module with Caddy (Cloudflare DNS-01) + oauth2-proxy (Entra ID); include + pinned submodule; prebuilt Caddy image; per-project app registration with checklist and az script; optional group-based access; migrate dockerdash onto it as the reference consumer.
**Result:** Accepted. The user did not decide the GHCR token question. The plan publishes the image from GitHub Actions using the built-in GITHUB_TOKEN, which needs no personal token, and keeps a local-build fallback.

### 2026-11-19T08:07:28Z — tool
**Action:** Created project dir and git repo (Bash)
**Detail:** `mkdir -p /claude/project-m365-gate; git init -b main; git config user.name rh1gmus; git config user.email rh1gmus@localhost; git config core.sshCommand <rh1gmus GitHub key, IdentitiesOnly, rh1gmus known_hosts, StrictHostKeyChecking=yes>; git remote add origin git@github.com:rh1gmus/m365-gate.git; git ls-remote origin`
**Result:** Repo initialized with the same identity and SSH setup as dockerdash. Remote reachable and empty (no refs). The tool shell resets cwd outside /claude/project-dockerdash, so commands use absolute paths.

### 2026-11-19T08:16:00Z — tool
**Action:** Wrote module files (Write)
**Detail:** `compose.yaml` (gate-caddy, gate-config, gate-proxy; networks gate_edge and gate_backend (internal); volumes gate_caddy_data/config and gate_config; required vars use `:?` with readable messages; hardening: read_only, cap_drop ALL, no-new-privileges; caddy keeps only NET_BIND_SERVICE). `caddy/Dockerfile` (ARG CADDY_VERSION=2.10.2, CF_DNS_VERSION=0.2.4; binary only, OCI source label). `caddy/Caddyfile` (mounted, not baked; {$GATE_HOST}:{$GATE_PORT}; /logout through Entra). `config/render_config.py` (validation; GATE_PORT/GATE_UPSTREAM/ALLOWED_GROUPS/GATE_SESSION_HOURS; cookie name per port; redirect URI leaves out :443). `.github/workflows/caddy-image.yml` (GHCR via GITHUB_TOKEN, amd64, gha cache). `.env.example`, `.gitignore`, `docs/entra-app-registration.md`, `scripts/register-entra-app.sh` (az CLI; writes the secret to .env without printing it), `examples/whoami/`, `README.md`.
**Result:** Files created. The 08:16:00Z time is approximate (writes happened between 08:07:28Z and the test below).

### 2026-11-19T08:12:14Z — tool
**Action:** Offline tests (Bash)
**Detail:** (1) Throwaway consumer dir using `include: ../compose.yaml` with a dummy env file, then `docker compose config`. (2) Same with GATE_UPSTREAM removed. (3) render_config.py with 5 input sets. (4) `bash -n` on the az script. (5) YAML parse of the workflow. (6) `docker pull traefik/whoami:v1.10.3`.
**Result:** (1) Merge OK: app on gate_backend only; gate-caddy publishes 0.0.0.0:8443; gate_backend internal=true; build context and Caddyfile bind resolve to the module dir. **Bug found:** `ACME_EMAIL=   # comment` was read as the value "# empty with comment". Fixed by rewriting .env.example with comments on their own lines; documented in README. (2) Clear error: "required variable GATE_UPSTREAM is missing a value: set GATE_UPSTREAM in .env…". (3) All correct: per-port cookie names, :443 left out of the redirect, wildcard -> email_domains *, groups-only -> email_domains * + allowed_groups, emails+groups -> file + groups, bad input -> 6 specific errors. (4) OK. (5) OK. (6) Tag exists. Untested so far: a live run of the az script (no az CLI or Entra admin session here) and allowed_groups against a real groups claim.

### 2026-11-19T08:12:36Z — message
**Action:** Timestamp correction (append-only note)
**Detail:** The "Wrote module files" entry stamped 08:16:00Z used an estimated time. The writes actually finished before the 08:12:14Z test entry. Every later entry takes its time from `date -u` at the moment it is written.
**Result:** Noted; the earlier entry is left unchanged.

### 2026-11-19T08:12:36Z — process
**Action:** Committed and pushed the module
**Detail:** `git commit` (12 files) as rh1gmus; `git push -u origin main`
**Result:** 4b8daa7 on origin/main. The push includes caddy/Dockerfile and the workflow, which should trigger the caddy-image Actions run. I can't see that run from the VM (no gh CLI or API token), so the user will need to check the Actions tab.
