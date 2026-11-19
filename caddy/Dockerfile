# Caddy with the Cloudflare DNS provider module, for ACME DNS-01 certificates.
# The image holds only the binary. The Caddyfile is mounted by compose.yaml, so
# config changes never need a rebuild.
#
# Prebuilt by .github/workflows/caddy-image.yml as
#   ghcr.io/rh1gmus/m365-gate-caddy:<CADDY_VERSION>-cloudflare<CF_DNS_VERSION>
# When bumping versions, change them here, in the workflow, and in compose.yaml's default image tag.
ARG CADDY_VERSION=2.10.2

FROM caddy:${CADDY_VERSION}-builder AS build
ARG CF_DNS_VERSION=0.2.4
RUN xcaddy build --with github.com/caddy-dns/cloudflare@v${CF_DNS_VERSION}

FROM caddy:${CADDY_VERSION}
COPY --from=build /usr/bin/caddy /usr/bin/caddy
LABEL org.opencontainers.image.source="https://github.com/rh1gmus/m365-gate" \
      org.opencontainers.image.description="Caddy with the caddy-dns/cloudflare module for m365-gate"
