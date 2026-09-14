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

# THE PATHS ARE THE REPOSITORY'S, NOT A FLAT /build. The console consumes ui/ (OUR OWN design
# system, copied from base-services' platform/ui at their v0.16.29 — 2026-08-22 — the day we
# needed to edit it ourselves) AS SOURCE — one vite alias, no npm package, no build step between —
# and its tailwind config reaches out with ../../ui/…/tailwind-preset.cjs. Copying only
# apps/console gave a tree where that path leads nowhere, and the failure was a missing MODULE,
# which reads like a bad dependency rather than a bad COPY. So the image mirrors the checkout:
# /build/apps/console beside /build/ui.
WORKDIR /build/apps/console

# Dependencies first, and from the lockfile only — `npm ci` fails loudly when the
# lockfile disagrees with package.json, where `npm install` would quietly resolve
# something newer and hand us a bundle nobody tested.
COPY apps/console/package.json apps/console/package-lock.json ./
RUN npm ci --no-audit --no-fund

# The design system is a BUILD input twice over: the preset shapes the theme, and the content
# globs scan its components — a stylesheet compiled without them is missing every class the
# library uses and renders as an unstyled page rather than as an error.
COPY ui /build/ui

# THE BRAND ACCENT'S ONE SOURCE OF TRUTH — vite.config.ts reads config/product.json directly
# (../../config/product.json from apps/console/) to inject __PRODUCT_ACCENT__. Missing this COPY
# fails the build with an ENOENT rather than a wrong colour, which is the right kind of loud.
COPY config/product.json /build/config/product.json

# THE PUBLIC LEGAL PAGES' TWO SOURCES — legalDocsPlugin.ts reads both at BUILD time, not at
# runtime, so a fresh server's console image has to carry them into the builder stage same as
# ui/ above, or the /legal/:slug route ships empty on a brand-new install with no error anyone
# would see (the plugin's own read failure, not a screen anyone opens by hand). Our own values
# (deploy/seed/legal) and the PDPL pack's clause templates (platform/, requires
# `git submodule update --init platform` — scripts/setup.sh does the full, non-sparse checkout).
COPY deploy/seed/legal /build/deploy/seed/legal
COPY platform/services/compliance-service/app/data/pdpl-templates /build/platform/services/compliance-service/app/data/pdpl-templates
COPY apps/console/ ./

# META'S IDENTIFIERS ARE NO LONGER BUILD ARGS. They used to be baked in here the same way
# Moyasar's key still is below — but neither Meta's App ID nor its Facebook Login Config ID is
# actually secret (both travel from the browser to Meta's own JS SDK in the clear already), so
# they now come from a runtime read (`GET /api/v1/whatsapp/config`, see console's own meta.ts) —
# set from the admin secrets panel, no rebuild required. See meta.ts's own docstring for the full
# reasoning and `ci/check_the_meta_versions_are_alive.py` for what still pins the Graph version.
# THE SAME SHAPE FOR MOYASAR STILL APPLIES BELOW. `payment.ts`'s `canMintToken` reads this baked
# in at build time — absent by default so the card form correctly declares itself unavailable
# rather than pretending to work with no key behind it.
ARG VITE_MOYASAR_PUBLISHABLE_KEY=""
ENV VITE_MOYASAR_PUBLISHABLE_KEY=$VITE_MOYASAR_PUBLISHABLE_KEY
# UNLIKE META/MOYASAR ABOVE, NOT AN OPERATOR CREDENTIAL — a pure feature switch with no secret
# behind it, so it defaults ON here rather than requiring deploy/target.env to supply anything.
# AssistantHint.tsx's own "؟" icon (per-screen help, assistant-service's by_anchor()) and
# Support.tsx's "خدمة العملاء" chat tab — both built and tested, left dark until now because
# nothing ever set either flag. Still overridable via VITE_ASSISTANT_*_ENABLED in
# deploy/target.env if a build ever needs either off.
ARG VITE_ASSISTANT_HELP_ICON_ENABLED="true"
ARG VITE_ASSISTANT_CHAT_ENABLED="true"
ENV VITE_ASSISTANT_HELP_ICON_ENABLED=$VITE_ASSISTANT_HELP_ICON_ENABLED VITE_ASSISTANT_CHAT_ENABLED=$VITE_ASSISTANT_CHAT_ENABLED
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

# The technical POS/till API reference, served as a real static page at /docs/pos-integration/ —
# no Caddyfile change needed: the catch-all `handle {}` already does `try_files {path} /index.html;
# file_server`, and file_server resolves a directory request to its own index.html on its own.
COPY marketing/docs /srv/docs

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
