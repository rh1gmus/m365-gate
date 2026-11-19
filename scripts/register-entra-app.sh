#!/usr/bin/env bash
# Create a single-tenant Entra ID app registration for an m365-gate project and write
# ENTRA_TENANT_ID / ENTRA_CLIENT_ID / ENTRA_CLIENT_SECRET into an env file.
# The secret is never printed.
#
# usage: register-entra-app.sh "<display name>" <GATE_HOST> [GATE_PORT=443] [ENV_FILE=./.env]
# needs: Azure CLI, signed in (az login --allow-no-subscriptions) as someone allowed to register apps
set -euo pipefail

name=${1:?display name}; host=${2:?GATE_HOST}; port=${3:-443}; envfile=${4:-./.env}
command -v az >/dev/null || { echo "Azure CLI (az) is not installed" >&2; exit 1; }

origin="https://${host}"; [ "$port" = "443" ] || origin="${origin}:${port}"
redirect="${origin}/oauth2/callback"

tenant=$(az account show --query tenantId -o tsv)
echo "Tenant:       ${tenant}"
echo "Registering:  ${name}  (redirect ${redirect})"

app_id=$(az ad app create --display-name "$name" --sign-in-audience AzureADMyOrg \
  --web-redirect-uris "$redirect" --query appId -o tsv)
az ad sp create --id "$app_id" >/dev/null
secret=$(az ad app credential reset --id "$app_id" --display-name "m365-gate $(date +%F)" \
  --years 1 --query password -o tsv)

umask 077
touch "$envfile"
set_kv() {  # replace KEY=... if present, else append
  local k=$1 v=$2 tmp; tmp=$(mktemp "${envfile}.XXXX")
  grep -v "^${k}=" "$envfile" > "$tmp" || true
  printf '%s=%s\n' "$k" "$v" >> "$tmp"
  mv "$tmp" "$envfile"
}
set_kv ENTRA_TENANT_ID "$tenant"
set_kv ENTRA_CLIENT_ID "$app_id"
set_kv ENTRA_CLIENT_SECRET "$secret"
chmod 600 "$envfile"
unset secret

echo "Client ID:    ${app_id}"
echo "Wrote ENTRA_TENANT_ID, ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET to ${envfile} (mode 600)."
echo "The secret expires in 1 year. Optional hardening: see docs/entra-app-registration.md."
