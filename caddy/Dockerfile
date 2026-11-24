# Caddy with the Cloudflare DNS provider module, for ACME DNS-01 certificates.
# The image holds only the binary. The Caddyfile is mounted by compose.yaml, so
# config changes never need a rebuild.
#
# Prebuilt by .github/workflows/caddy-image.yml as
#   ghcr.io/rh1gmus/m365-gate-caddy:<CADDY_VERSION>-cloudflare<CF_DNS_VERSION>-r<N>
# When bumping versions, change them here, in the workflow, and in compose.yaml's default image tag.
# The base images are pinned by digest too, so bump the digests together with CADDY_VERSION.
ARG CADDY_VERSION=2.11.9

FROM caddy:${CADDY_VERSION}-builder@sha256:cda07fe9d82728c7ac44d844306d435e98131423dc7b114f05a8a8ecfff94707 AS build
ARG CF_DNS_VERSION=0.2.4
RUN xcaddy build --with github.com/caddy-dns/cloudflare@v${CF_DNS_VERSION}

FROM caddy:${CADDY_VERSION}@sha256:4851e54a46b206517c574821bb5cc67f170d2156041e9fbc4c9193b45e84a75b
COPY --from=build /usr/bin/caddy /usr/bin/caddy
# The base image grants the binary a file capability (cap_net_bind_service=ep). A non-root container with
# no capabilities and no-new-privileges can't gain it, so exec fails with EPERM. Copying to a new file
# drops the xattr; the bytes are unchanged. compose.yaml binds low ports with a sysctl instead.
RUN cp /usr/bin/caddy /tmp/caddy.nocap && mv -f /tmp/caddy.nocap /usr/bin/caddy \
 && ! (command -v getcap >/dev/null && getcap /usr/bin/caddy | grep -q cap_)
LABEL org.opencontainers.image.source="https://github.com/rh1gmus/m365-gate" \
      org.opencontainers.image.description="Caddy with the caddy-dns/cloudflare module for m365-gate"
