"""Render the oauth2-proxy config (and email allow-list) for m365-gate from env vars.

Runs once, as the gate-config one-shot service, before gate-proxy starts. The output
goes to a shared volume, so the distroless oauth2-proxy image needs no shell.
Secrets (client secret, cookie secret) never pass through here. gate-proxy reads
them from its own environment.
"""
import ipaddress
import os
import re
import sys
from urllib.parse import urlparse

OUT = "/config"


def env(name, default=None):
    v = os.environ.get(name, default)
    return v.strip() if isinstance(v, str) else v


host = env("GATE_HOST", "")
port = env("GATE_PORT", "443")
upstream = env("GATE_UPSTREAM", "")
tenant = env("ENTRA_TENANT_ID", "")
emails = [e.strip().lower() for e in env("ALLOWED_EMAILS", "").split(",") if e.strip()]
groups = [g.strip() for g in env("ALLOWED_GROUPS", "").split(",") if g.strip()]
expire = env("GATE_SESSION_HOURS", "12")
# Optional: proxy IPs/CIDRs allowed to set X-Forwarded-* (trusted_proxy_ips; NOT trusted_ips, which bypasses sign-in). Unset = any peer.
trusted = [c.strip() for c in env("GATE_TRUSTED_PROXY_IPS", "").split(",") if c.strip()]

errors = []
for c in trusted:
    try:
        ipaddress.ip_network(c, strict=False)
    except ValueError:
        errors.append(f"GATE_TRUSTED_PROXY_IPS entry is not an IP or CIDR: {c!r}")
if not re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}", host):
    errors.append("GATE_HOST must be a DNS name, e.g. app.example.com")
if not (port.isdigit() and 0 < int(port) < 65536):
    errors.append("GATE_PORT must be a TCP port number")
u = urlparse(upstream)
if u.scheme not in ("http", "https") or not u.hostname:
    errors.append("GATE_UPSTREAM must be a URL such as http://app:8080")
if not re.fullmatch(r"[0-9a-fA-F-]{36}", tenant):
    errors.append("ENTRA_TENANT_ID must be the directory (tenant) ID GUID")
if not emails and not groups:
    errors.append("set ALLOWED_EMAILS (UPNs, or * for the whole tenant) and/or ALLOWED_GROUPS (group object IDs)")
bad_groups = [g for g in groups if not re.fullmatch(r"[0-9a-fA-F-]{36}", g)]
if bad_groups:
    errors.append("ALLOWED_GROUPS must be Entra group object IDs (GUIDs)")
if not expire.isdigit() or not 1 <= int(expire) <= 720:
    errors.append("GATE_SESSION_HOURS must be 1-720")
if errors:
    sys.exit("m365-gate config error:\n  - " + "\n  - ".join(errors))

origin = f"https://{host}" + ("" if port == "443" else f":{port}")


def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


lines = [
    'provider = "entra-id"',
    f'oidc_issuer_url = {q(f"https://login.microsoftonline.com/{tenant}/v2.0")}',
    'scope = "openid email profile"',
    # The UPN is controlled by the tenant and is the sign-in name. The email claim can be changed by users.
    'oidc_email_claim = "preferred_username"',
    'http_address = "0.0.0.0:4180"',
    'reverse_proxy = true',
    f'redirect_url = {q(origin + "/oauth2/callback")}',
    # login.microsoftonline.com: lets /oauth2/sign_out?rd= hand off to Entra's logout endpoint.
    f'whitelist_domains = [{q(f"{host}:{port}")}, {q(host)}, "login.microsoftonline.com"]',
    f'upstreams = [{q(upstream.rstrip("/") + "/")}]',
    'skip_provider_button = true',
    # Cookies aren't isolated by port, so the cookie name includes the port. That keeps
    # two gated apps on the same hostname from overwriting each other's session.
    f'cookie_name = "_m365gate_{port}"',
    'cookie_secure = true',
    'cookie_httponly = true',
    'cookie_samesite = "lax"',
    f'cookie_expire = "{int(expire)}h"',
    # Tell the app who is signed in: X-Forwarded-Email / -User / -Preferred-Username
    'pass_user_headers = true',
    'request_logging = true',
]

if trusted:
    lines.append("trusted_proxy_ips = [" + ", ".join(q(c) for c in trusted) + "]")

if emails == ["*"] or (not emails and groups):
    lines.append('email_domains = ["*"]')
else:
    with open(f"{OUT}/allowed_emails.txt", "w") as f:
        f.write("\n".join(emails) + "\n")
    lines.append(f'authenticated_emails_file = "{OUT}/allowed_emails.txt"')

if groups:
    # Needs the app registration to emit the groups claim (groupMembershipClaims = SecurityGroup).
    lines.append("allowed_groups = [" + ", ".join(q(g) for g in groups) + "]")

with open(f"{OUT}/oauth2-proxy.cfg", "w") as f:
    f.write("\n".join(lines) + "\n")

who = "anyone in tenant" if emails == ["*"] else f"{len(emails)} email(s)" if emails else "any email"
print(f"m365-gate: {origin} -> {upstream} | allow: {who}" + (f" AND member of {len(groups)} group(s)" if groups else ""))
