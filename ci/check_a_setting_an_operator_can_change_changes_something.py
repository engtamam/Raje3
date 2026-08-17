"""Every setting a service declares must be read by that service.

WHAT A DEAD SETTING IS, AND WHY IT IS WORSE THAN A MISSING ONE. `SNAPSHOT_VISIT_LIMIT` was declared
in `insights/app/config.py` AND published in `deploy/services/insights.values.yaml`, where an
operator reads it as the cap on how many visits a snapshot reads. Nothing consumed it. The real
bound was a DEFAULT ARGUMENT on `peers.visits(..., limit=5000)`, so raising the declared number in
a deploy changed nothing whatsoever — and the operator had no way to discover that except by
measuring the run. `SNAPSHOT_STALE_HOURS` was the same story against a literal `30` in the route.

A missing setting announces itself the first time somebody looks for it. A setting that exists,
documents itself, appears in the values file and is read by nobody announces nothing at all: it
answers the question «can I tune this?» with a confident yes, for ever.

THE RULE: a name declared in `services/*/app/config.py` must appear somewhere else under that
service's `app/`. Not a use-count, not a taste judgement — the same name, read once, anywhere.

THE FRAMEWORK'S OWN SETTINGS ARE NOT DEAD, AND THE LIST OF THEM IS NOT WRITTEN HERE. `CORS_*`,
`AUDIT_SERVICE_URL`, `EGRESS_ALLOWED_HOSTS` and friends are inherited from the platform's service
template and consumed by ITS middleware, which lives in a tree we do not edit. They are recognised
by reading `platform/services/_template/app/config.py` — the platform is the authority on what the
platform reads, so this gate asks it rather than keeping a copy that would rot.

THAT DISTINCTION WAS FOUND BY LOOKING AT THE SHAPE OF THE ANSWER. The first sweep reported seven
dead settings in every one of the six services — the SAME seven. A finding that uniform is a fact
about the scope of the search, not about the code, and treating it as six findings would have been
a gate wrong about most of what it printed. The two that were real were the two that appeared in
one service only.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
TEMPLATE = ROOT / "platform" / "services" / "_template" / "app" / "config.py"

#: `    NAME: type = ...` inside a Settings class — the declaration form these files use.
DECLARED = re.compile(r"^    ([A-Z][A-Z0-9_]*)\s*:", re.M)


def _identifiers(source: str) -> set[str]:
    """Every name the CODE mentions — attributes and bare names, never prose.

    A COMMENT NAMING A SETTING IS NOT A USE OF IT, AND THIS GATE LEARNED THAT ON ITSELF. The first
    version searched the file text, so the sentence I wrote in `tick.py` explaining that
    `SNAPSHOT_VISIT_LIMIT` had been dead was itself enough to report it alive. The sabotage passed
    green and the gate was worthless in the one direction it existed for — the third time in this
    repository that prose has been mistaken for the thing it describes.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # `getattr(s, "NAME")` and `os.environ["NAME"]` are real reads, rare but legitimate.
            names.add(node.value)
    return names


def _identifiers_beside_declarations(source: str) -> set[str]:
    """Names the config file mentions ANYWHERE EXCEPT on the left of its own declarations.

    SUBTRACTING THE DECLARED NAMES WOULD DELETE THE USE ALONG WITH THE DECLARATION, which is what
    the first attempt did: `self.WHATSAPP_CEILING_CODES` inside its own derived property is a real
    read, and removing the name wholesale reported it dead a second time. So the DECLARATION NODE
    is skipped, not the name.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    skip = {id(n.target) for n in ast.walk(tree)
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)}
    names: set[str] = set()
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.add(node.value)
    return names


def main() -> int:
    if not SERVICES.is_dir():
        print("no services/ directory — this gate cannot answer, so it refuses to")
        return 1
    if not TEMPLATE.is_file():
        # A GATE THAT CANNOT READ ITS AUTHORITY MUST SAY SO. Without the template every framework
        # setting reads as dead, and this gate would report forty findings and be switched off.
        print("platform/services/_template/app/config.py is missing — the framework's own settings "
              "cannot be told from ours, so this gate cannot answer")
        return 1

    inherited = set(DECLARED.findall(TEMPLATE.read_text(encoding="utf-8")))
    if not inherited:
        print("the platform template declares no settings in the expected shape — this gate is "
              "reading for a form that changed and will not guess")
        return 1

    checked = 0
    dead: list[str] = []
    for cfg in sorted(SERVICES.glob("*/app/config.py")):
        svc = cfg.relative_to(SERVICES).parts[0]
        declared = [d for d in DECLARED.findall(cfg.read_text(encoding="utf-8"))
                    if d not in inherited]
        checked += len(declared)
        # CONFIG.PY IS READ TOO, MINUS THE DECLARATIONS THEMSELVES. A setting consumed by a
        # DERIVED PROPERTY beside it is alive: `whatsapp_ceiling_codes` splits
        # `WHATSAPP_CEILING_CODES` into a tuple and `message_sender` uses that. Skipping the whole
        # file called it dead, which is a gate wrong about a real hit — and one wrong hit is what
        # teaches people to skim the rest.
        seen: set[str] = _identifiers_beside_declarations(cfg.read_text(encoding="utf-8"))
        for path in sorted((SERVICES / svc / "app").rglob("*.py")):
            if path.name == "config.py":
                continue
            try:
                seen |= _identifiers(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError) as exc:
                print(f"cannot read {path.relative_to(ROOT).as_posix()}: {exc} — NOT checked")
                return 1
        for name in declared:
            if name not in seen:
                dead.append(f"{svc}: {name}")

    if not checked:
        # SILENCE IS NOT AGREEMENT.
        print("no service settings found outside the framework's own — this gate needs re-pointing")
        return 1

    if dead:
        print(f"{len(dead)} setting(s) declared and read by nobody:")
        for line in dead:
            print("  " + line)
        print("\nEach of these is published in a values file, where it reads as a knob. Changing it")
        print("does nothing, and there is no way to find that out except by measuring the run.")
        print("Either wire it to the thing it names, or delete it and the values entry with it.")
        return 1

    print(f"{checked} service setting(s) beyond the framework's: every one is read")
    return 0


if __name__ == "__main__":
    sys.exit(main())
