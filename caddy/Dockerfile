# Caddy with the Cloudflare DNS provider module, for ACME DNS-01 certificates.
# The image holds only the binary. The Caddyfile is mounted by compose.yaml, so
# config changes never need a rebuild.
#
# Prebuilt by .github/workflows/caddy-image.yml as
#   ghcr.io/rh1gmus/m365-gate-caddy:<CADDY_VERSION>-cloudflare<CF_DNS_VERSION>-r<N>
# When bumping versions, change them here, in the workflow, and in compose.yaml's default image tag.
# The base images are pinned by digest too, so bump the digests together with CADDY_VERSION.
ARG CADDY_VERSION=2.10.2

FROM caddy:${CADDY_VERSION}-builder@sha256:01668408cc26e2e00c9d067c30cb43b2ba14ad1f2808beda55503cb2a31f59dc AS build
ARG CF_DNS_VERSION=0.2.4
RUN xcaddy build --with github.com/caddy-dns/cloudflare@v${CF_DNS_VERSION}

FROM caddy:${CADDY_VERSION}@sha256:c3d7ee5d2b11f9dc54f947f68a734c84e9c9666c92c88a7f30b9cba5da182adb
COPY --from=build /usr/bin/caddy /usr/bin/caddy
# The base image grants the binary a file capability (cap_net_bind_service=ep). A non-root container with
# no capabilities and no-new-privileges can't gain it, so exec fails with EPERM. Copying to a new file
# drops the xattr; the bytes are unchanged. compose.yaml binds low ports with a sysctl instead.
RUN cp /usr/bin/caddy /tmp/caddy.nocap && mv -f /tmp/caddy.nocap /usr/bin/caddy \
 && ! (command -v getcap >/dev/null && getcap /usr/bin/caddy | grep -q cap_)
LABEL org.opencontainers.image.source="https://github.com/rh1gmus/m365-gate" \
      org.opencontainers.image.description="Caddy with the caddy-dns/cloudflare module for m365-gate"
