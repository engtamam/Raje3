# =============================================================================
# console — the owner's screens, and the page the domain opens on.
# Two stages: node builds, nginx serves. Nothing from the builder reaches the
# runtime but the compiled bundle — no node, no npm, no source, no lockfile.
# =============================================================================
# THIS IMAGE DID NOT EXIST UNTIL A REAL INSTALL ASKED FOR IT. The console ran on
# a laptop against a forwarded gateway for months, which was enough to build it
# and nowhere near enough to ship it: a customer opening the domain reached
# nothing at all. Six backend images and no way to see them.

FROM node:22-slim AS builder

# THE PATHS ARE THE REPOSITORY'S, NOT A FLAT /build. The console consumes platform/ui AS SOURCE —
# one vite alias, no npm package, no build step between — and its tailwind config reaches out with
# ../../platform/ui/…/tailwind-preset.cjs. Copying only apps/console gave a tree where that path
# leads nowhere, and the failure was a missing MODULE, which reads like a bad dependency rather
# than a bad COPY. So the image mirrors the checkout: /build/apps/console beside /build/platform/ui.
WORKDIR /build/apps/console

# Dependencies first, and from the lockfile only — `npm ci` fails loudly when the
# lockfile disagrees with package.json, where `npm install` would quietly resolve
# something newer and hand us a bundle nobody tested.
COPY apps/console/package.json apps/console/package-lock.json ./
RUN npm ci --no-audit --no-fund

# The design system is 530K of TypeScript and it is a BUILD input twice over: the preset shapes the
# theme, and the content globs scan its components — a stylesheet compiled without them is missing
# every class the library uses, which renders as an unstyled page and not as an error.
COPY platform/ui /build/platform/ui
COPY apps/console/ ./
RUN npm run build

# ── runtime ──────────────────────────────────────────────────────────────────
# CADDY, BECAUSE THE EDGE IS CADDY. This container serves static files inside the
# cluster and the edge in front of it terminates TLS and routes — and that edge is
# a Caddy we already run, read and reason about. Reaching for nginx here would put
# a second web server in the product for no reason but habit: two syntaxes, two
# sets of defaults, two places to look when a path 404s.
FROM caddy:2.8-alpine AS runtime

# The landing page at /, the console under /app. One origin, so a link from the
# landing page into the console is not a cross-site anything.
COPY --from=builder /build/apps/console/dist /srv/app
COPY marketing/index.html /srv/index.html

# SPA ROUTING IS NOT OPTIONAL HERE. Every screen has a real URL — a customer page
# arrives as a link inside a WhatsApp message — and a reload of one of those is a
# request with no file behind it. Without the fallback the owner sees 404 on a
# screen that works perfectly when navigated to.
COPY apps/console/Caddyfile /etc/caddy/Caddyfile

# 8080 AND UNPRIVILEGED. A process that is not root cannot bind a port below 1024,
# and Caddy writes its state and config caches under $HOME — which for a non-root
# user is not writable unless we say where. Nothing here needs to persist: the
# certificates belong to the edge, and this server never speaks TLS.
ENV XDG_DATA_HOME=/tmp XDG_CONFIG_HOME=/tmp
USER 65532:65532
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
