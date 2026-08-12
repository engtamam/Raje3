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
WORKDIR /build

# Dependencies first, and from the lockfile only — `npm ci` fails loudly when the
# lockfile disagrees with package.json, where `npm install` would quietly resolve
# something newer and hand us a bundle nobody tested.
COPY apps/console/package.json apps/console/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY apps/console/ ./
RUN npm run build

# ── runtime ──────────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

# The landing page at /, the console under /app. One origin, so a link from the
# landing page into the console is not a cross-site anything.
COPY --from=builder /build/dist /usr/share/nginx/html/app
COPY marketing/index.html /usr/share/nginx/html/index.html

# SPA ROUTING IS NOT OPTIONAL HERE. Every screen has a real URL — a customer page
# arrives as a link inside a WhatsApp message — and a reload of one of those is a
# request nginx has no file for. Without the fallback the owner sees 404 on a
# screen that works perfectly when navigated to.
RUN printf '%s\n' \
  'server {' \
  '  listen 8080;' \
  '  root /usr/share/nginx/html;' \
  '  index index.html;' \
  '  location /app/ { try_files $uri $uri/ /app/index.html; }' \
  '  location /     { try_files $uri $uri/ /index.html; }' \
  '  location = /healthz { return 200 "ok\\n"; add_header Content-Type text/plain; }' \
  '}' > /etc/nginx/conf.d/default.conf \
 && rm -f /etc/nginx/conf.d/*.conf.default

# 8080 AND NOT 80, because the container runs unprivileged and a non-root process
# cannot bind a port below 1024. nginx's own pid and cache paths move for the
# same reason — the packaged defaults are all root-owned.
RUN sed -i 's|/var/run/nginx.pid|/tmp/nginx.pid|' /etc/nginx/nginx.conf \
 && sed -i '/^user /d' /etc/nginx/nginx.conf \
 && chown -R nginx:nginx /var/cache/nginx /usr/share/nginx/html

USER nginx
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
CMD ["nginx", "-g", "daemon off;"]
