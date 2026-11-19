# Entra ID app registration for a gated project

Create **one app registration per project**. Each project then has its own secret and redirect URI, and you can revoke it without affecting the others.

## Portal checklist

1. **Entra admin center → Applications → App registrations → New registration**
   - **Name:** the project, e.g. `doda dashboard`
   - **Supported account types:** *Accounts in this organizational directory only* (single tenant)
   - **Redirect URI:** platform **Web**, value `https://<GATE_HOST>:<GATE_PORT>/oauth2/callback`
     - On port 443, leave the port out: `https://<GATE_HOST>/oauth2/callback`
2. **Overview:** copy **Application (client) ID** → `ENTRA_CLIENT_ID` and **Directory (tenant) ID** → `ENTRA_TENANT_ID`.
3. **Certificates & secrets → New client secret:** copy the secret's **Value** (not the Secret ID) → `ENTRA_CLIENT_SECRET`. Note the expiry date. When it expires, sign-in fails with `AADSTS7000222`.
4. **API permissions:** the default `Microsoft Graph → User.Read` is enough. Nothing else is needed.

## Optional: restrict who can sign in, in Entra instead of `.env`

- **Assignment required:** Enterprise applications → *your app* → Properties → **Assignment required? = Yes**, then add users or groups under *Users and groups*. Anyone not assigned is stopped by Microsoft before reaching the gate. Combine with `ALLOWED_EMAILS=*`.
- **Group-based allow-list (`ALLOWED_GROUPS`):** App registration → Token configuration → **Add groups claim** → *Security groups*. Then put the group **object IDs** in `ALLOWED_GROUPS`. Users in more than 200 groups get an "overage" token without the list. Use assignment-required for such users.

## CLI alternative

`scripts/register-entra-app.sh` does steps 1–3 with the Azure CLI and writes the IDs and the secret straight into your `.env`, without printing the secret:

```bash
az login --allow-no-subscriptions
./m365-gate/scripts/register-entra-app.sh "doda dashboard" doda.rhigmus.com 9090 ./.env
```

## Troubleshooting

| Symptom | Cause |
|---|---|
| `AADSTS50011` redirect URI mismatch | The redirect URI in Entra doesn't exactly match `https://GATE_HOST[:GATE_PORT]/oauth2/callback` |
| `AADSTS700016` application not found | Wrong `ENTRA_CLIENT_ID` or wrong tenant |
| `AADSTS7000215` / `7000222` | Wrong secret (Secret ID used instead of Value) / secret expired |
| Signed in, then **403 Forbidden** | UPN not in `ALLOWED_EMAILS`, or not in any `ALLOWED_GROUPS` group |
