"""Every value `deploy/mint-our-secrets.sh` seals into a service's secret must be a field that
service's own `Settings` actually declares — or it is a credential sitting in a pod, read by
nothing, held in reserve for a use that does not exist.

WHY THIS GATE EXISTS AT ALL. It found a real one on the day it was written: OBJECTSTORE_ACCESS_KEY
and OBJECTSTORE_SECRET_KEY were minted into all seven OURS services identically, and not one of
them ever set OBJECTSTORE_DRIVER to "s3" (the default is "local", and no deploy/services/*.values
.yaml file for any of the seven overrode it) — seven pods holding a credential that unlocks a real
object store, exercised by zero of them. Not a leak by itself, but pure blast radius: the day one
of those seven services is compromised, an attacker who reads its environment holds a working
object-store key nobody meant to hand them, for a feature that service does not use.

A minted-but-unread credential is invisible from the script alone — mint-our-secrets.sh looks
correct in isolation, because it IS correctly copying a real value. The defect only shows up by
crossing it against what the recipient's own Settings class declares, which is exactly what this
gate does and nothing else can from a git checkout: no live secret is read, no cluster is touched.

WHAT THIS CANNOT CATCH: a key the service DOES declare but never actually reads in a code path
(that is check_a_deployed_config_boots_its_own_service.py's territory, and a different question —
"is this field wired to a real guard", not "does this field exist to receive the value at all").
Nor can it catch a value sourced some OTHER way than this one script (gen-secrets.py's own minting
for affiliate-service/portal is platform's, not read here).
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "deploy" / "mint-our-secrets.sh"

C_G = "\033[32m"
C_R = "\033[31m"
C_N = "\033[0m"


def _service_list(text: str, var: str) -> list[str]:
    m = re.search(rf'^{var}="([^"]*)"', text, re.MULTILINE)
    if not m:
        return []
    return [s for s in m.group(1).split() if s]


def _literal_keys_in_loop(text: str) -> list[str]:
    """Every `--from-literal="KEY=...` inside the `for svc in $OURS; do ... done` block — the
    per-service keys minted fresh, as opposed to SHARED (patched from an existing platform value)."""
    m = re.search(r'for svc in \$OURS; do(.*?)\ndone\n', text, re.DOTALL)
    if not m:
        return []
    return re.findall(r'--from-literal="([A-Z_][A-Z0-9_]*)=', m.group(1))


def main() -> int:
    if not SCRIPT.is_file():
        print("no deploy/mint-our-secrets.sh — this gate cannot answer, so it refuses to")
        return 1
    text = SCRIPT.read_text(encoding="utf-8")

    ours = _service_list(text, "OURS")
    shared = _service_list(text, "SHARED")
    per_service = _literal_keys_in_loop(text)
    if not ours:
        print("could not read $OURS from mint-our-secrets.sh — this gate needs re-pointing")
        return 1

    keys = sorted(set(shared) | set(per_service))
    hits: list[str] = []
    checked = 0
    for svc in ours:
        cfg = ROOT / "services" / svc / "app" / "config.py"
        if not cfg.is_file():
            print(f"{svc} is in \\$OURS but has no services/{svc}/app/config.py — this gate "
                  f"needs re-pointing")
            return 1
        body = cfg.read_text(encoding="utf-8")
        for key in keys:
            checked += 1
            if not re.search(rf'^\s*{key}\s*:', body, re.MULTILINE):
                hits.append(f"{svc}: minted {key} — services/{svc}/app/config.py declares no "
                            f"such Settings field")

    if hits:
        print(f"{len(hits)} minted value(s) with no reader:")
        for line in hits:
            print(f"  {C_R}x {line}{C_N}")
        print("\nEither the service's Settings needs this field (it is meant to read it), or "
              "mint-our-secrets.sh should stop sealing it — a credential in a pod that nothing "
              "reads is blast radius nobody is spending.")
        return 1
    print(f"{C_G}✔ {checked} minted value(s) across {len(ours)} service(s): every one is a "
          f"field its own Settings declares{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
