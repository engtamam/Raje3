"""Every JSON-carrying value in a values file must parse as JSON.

A COMMENT TOOK THE PRODUCT DOWN. `api-gateway.values.yaml` carries its whole routing table as a
YAML block scalar (`GATEWAY_ROUTES: |`). Somebody explained one route with a `#` line INSIDE that
block — the natural place to put it, right above the route it describes. But YAML does not read
`#` inside a block scalar; it passes the line through as text. So seven lines of Arabic prose
became part of the value, the routing table stopped being valid JSON, and the gateway crash-looped
on boot: `GATEWAY_ROUTES is not valid JSON: Expecting value: line 27`.

WHAT MAKES IT WORTH A GATE RATHER THAN CARE. Every layer above was green. The file is valid YAML.
It renders against the chart — `helm template` type-checks a string as a string. The pod is
created, the image is right, the digest matches. The only thing that knows is the process, at
boot, in a log nobody reads until the front door of the product has been down for a while.

WHERE THE LINE IS. Only values whose text actually starts like JSON (`[` or `{`) are judged. A
prose value that happens to contain a brace is not a claim to be JSON; a value that opens with one
is, and the service reading it will parse it.
"""
from __future__ import annotations

import json
import pathlib
import sys

try:
    import yaml
except ImportError:                                                     # pragma: no cover
    print("pyyaml is not installed — this gate cannot answer, so it refuses to")
    sys.exit(1)

ROOT = pathlib.Path(__file__).resolve().parent.parent
VALUES = ROOT / "deploy" / "services"


def _walk(node, path: str):
    """Every scalar in the tree, with the dotted path that reaches it."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


def main() -> int:
    files = sorted(VALUES.glob("*.values.yaml"))
    if not files:
        # SILENCE IS NOT AGREEMENT: checking nothing is not the same as finding nothing.
        print("no values files found — this gate needs re-pointing")
        return 1

    bad: list[str] = []
    checked = 0
    for f in files:
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        except Exception as exc:                                        # noqa: BLE001
            # A GATE THAT CANNOT READ MUST FAIL LOUDLY.
            bad.append(f"deploy/services/{f.name}: not valid YAML at all: {exc}")
            continue
        for path, text in _walk(doc, ""):
            stripped = text.strip()
            if not stripped or stripped[0] not in "[{":
                continue
            checked += 1
            try:
                json.loads(stripped)
            except json.JSONDecodeError as exc:
                bad.append(f"deploy/services/{f.name}: {path} opens as JSON and is not: {exc}")

    if bad:
        print(f"{len(bad)} value(s) claim to be JSON and are not:")
        for line in bad:
            print("  " + line)
        print("\nA `#` line inside a block scalar is TEXT, not a comment — put the note above the "
              "key, where YAML reads it.")
        return 1
    print(f"{checked} JSON-carrying values across {len(files)} files: every one parses")
    return 0


if __name__ == "__main__":
    sys.exit(main())
