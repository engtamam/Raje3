"""A route declared `tier: public` must have a real path through the edge — or it is a route the
open internet cannot reach no matter what credential it does or doesn't require.

WHY THIS GATE EXISTS AT ALL. Found live, the hard way: notification-service declares
`/webhooks/whatsapp` as `tier: public` — Meta's own callback, authenticated by a verify token and
an HMAC signature, deliberately never gated by our own bearer token. `deploy/edge/edge.json` is the
one file that decides what the public internet can reach (`platform/tools/edge/render.py` turns it
into the Caddyfile bring-up.sh actually ships) — and it never named `/webhooks/*` at all. Every
request Meta made, including the verification handshake itself, matched nothing but the catch-all
`/* -> console:8080` and got the LANDING PAGE back at a clean 200. "The callback URL or verify
token could not be validated" was never a token problem for as long as this gate would have caught
it — the request never reached the service holding the token to check it against.

A `tier: public` declaration is a promise the manifest is already making ("no bearer token
required to call this") — this gate is the other half of that promise: that the promise is even
reachable. A route nobody can reach is invisible in exactly the way this whole class of defect
always is: every pod healthy, every secret minted, the manifest says everything is fine, and the
one path an outside caller actually uses answers with somebody else's page.

WHAT IS DELIBERATELY EXEMPTED, AND WHY EACH ONE IS SAFE TO BE UNREACHABLE FROM THE EDGE:
  - /healthz, /readyz, /metrics — probed by kubelet and the cluster's own tooling, IN the cluster,
    never through the public edge. A route "the open internet can't reach" is the correct shape
    for these, not a gap.
  - /.well-known/jwks.json (identity-service) — every consumer today is a peer service verifying a
    token via its own in-cluster TOKEN_JWKS_URL (http://identity-service:8000/...), never a public
    client. If an external OIDC-style consumer is ever added, add its edge route AND remove it from
    this list in the same change — the exemption is for the fact pattern that holds today, not a
    blanket "identity is special".

WHAT THIS CANNOT CHECK: whether the matched edge prefix routes to the RIGHT upstream (that is a
human reading two files, not a mechanical property) — only that SOME non-catch-all prefix exists
for the route's own first path segment. A route matched by the wrong upstream is a different,
narrower bug than the one this gate exists for (a route matched by nothing at all, silently
served by whichever upstream owns the catch-all).

    python ci/check_a_public_route_is_actually_reachable_through_the_edge.py
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
EDGE_JSON = ROOT / "deploy" / "edge" / "edge.json"

C_G = "\033[32m"
C_R = "\033[31m"
C_N = "\033[0m"

# Never meant to be reached from the public edge — see this file's own module docstring for why
# each one, specifically, is exempt rather than just quietly excluded.
EXEMPT = {
    "/healthz", "/readyz", "/metrics",
    "/.well-known/jwks.json",   # identity-service — every consumer today is in-cluster
}


def _manifest_public_paths(manifest_py: pathlib.Path) -> list[str]:
    try:
        tree = ast.parse(manifest_py.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return []
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        try:
            d = ast.literal_eval(node)
        except Exception:                                       # noqa: BLE001
            continue
        if isinstance(d, dict) and d.get("tier") == "public" and "path" in d:
            found.append(d["path"])
    return found


def _edge_prefixes(edge_json: dict) -> list[str]:
    """Every non-catch-all route's own prefix, stripped of its trailing wildcard — `/api/v1/auth/*`
    becomes `/api/v1/auth`, `/*` (the catch-all) is excluded on purpose: matching it is exactly the
    silent-fallthrough this gate exists to catch, not a real route for anything."""
    prefixes = []
    for route in edge_json.get("routes", []):
        path = route.get("path", "")
        stripped = path[:-2] if path.endswith("/*") else path.rstrip("*")
        if stripped:                                              # "" is the catch-all `/*`
            prefixes.append(stripped)
    return prefixes


def _first_segment(path: str) -> str:
    """`/webhooks/whatsapp` -> `/webhooks`; `/api/v1/signup` -> `/api`."""
    parts = [p for p in path.split("/") if p]
    return f"/{parts[0]}" if parts else "/"


def main() -> int:
    if not EDGE_JSON.is_file():
        print("no deploy/edge/edge.json — this gate cannot answer, so it refuses to")
        return 1
    edge = json.loads(EDGE_JSON.read_text(encoding="utf-8"))
    prefixes = _edge_prefixes(edge)

    hits: list[str] = []
    checked = 0
    # OURS (services/) and platform/ (read-only, verification only — never edited by this gate).
    for base in (ROOT / "services", ROOT / "platform" / "services"):
        if not base.is_dir():
            continue
        for manifest_py in sorted(base.glob("*/app/manifest.py")):
            svc = manifest_py.parent.parent.name
            for path in _manifest_public_paths(manifest_py):
                # `{token}` / `{}` path params never affect prefix matching — normalise away.
                normalised = re.sub(r"\{[^}]*\}", "x", path)
                if normalised in EXEMPT or path in EXEMPT:
                    continue
                checked += 1
                seg = _first_segment(normalised)
                if not any(seg == p or normalised.startswith(p + "/") or normalised == p
                          for p in prefixes):
                    hits.append(f"{svc}: {path!r} is tier=public but deploy/edge/edge.json has no "
                                f"route for it — every request falls through to the catch-all "
                                f"(console) instead of reaching {svc}")

    if hits:
        print(f"{len(hits)} public route(s) unreachable through the edge:")
        for line in hits:
            print(f"  {C_R}x {line}{C_N}")
        print("\nAdd a `{ \"path\": \"<prefix>/*\", \"upstream\": \"<service>:8000\" }` entry to "
              "deploy/edge/edge.json ABOVE the catch-all `/*` — order matters, the renderer sorts "
              "by prefix length so this is about presence, not position, but keep it readable.")
        return 1
    print(f"{C_G}✔ {checked} public route(s) checked: every one has a real path through the "
          f"edge{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
