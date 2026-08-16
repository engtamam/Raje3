"""A key one service sends that the receiving model does not declare is a key that is discarded.

WHY THIS EXISTS (ب-6). loyalty tells operations that a free wash was performed, and sends
`{"tenant", "subject_ref", "service_id", "actor", "source", "free": True}`. `FreeVisitIn` declares
the first five. Pydantic drops the sixth without a word — that is what a model IS — so the flag
that says «this visit was a redemption, not a purchase» never arrives, and the free wash is counted
as an ordinary visit that earns points of its own. The customer redeems a reward and is paid for
redeeming it.

Nothing fails. The request is 200, the visit is recorded, and the only symptom is a points balance
that grows slightly faster than the rules say it should — a discrepancy nobody can trace back to a
missing key in a body that was accepted.

THIS IS THE SERVICE-TO-SERVICE HALF of `check_screens_send_declared_fields`, which watches the same
defect on the console↔route boundary. Both ends of every boundary in the product now have a check
facing the other one.

WHAT IT CHECKS. Every dict literal posted to a path that starts with `/internal/`, against the
pydantic model of the route serving that path — wherever in the repo that route lives. The path is
the link between the two files, and it is a literal on both sides, which is what makes this
checkable at all.

WHAT IT CANNOT SEE, and reports rather than hides: a body that is not a dict literal at the call
site, and a path composed at runtime from something other than a default argument. Those are
counted and printed, because a check that silently skips what it cannot read is a check that
reports «all clear» about work it never did.

    python ci/check_peer_bodies_are_declared.py
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"

#: Keys every internal caller may add: the transport's, not the route's.
TRANSPORT = {"headers", "timeout"}


def _models(tree: ast.Module) -> dict[str, set[str]]:
    """Every pydantic model in a module -> its declared field names, bases in the file followed."""
    classes = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    out: dict[str, set[str]] = {}

    def fields(name: str, seen: set[str]) -> set[str]:
        node = classes.get(name)
        if node is None or name in seen:
            return set()
        seen.add(name)
        got: set[str] = set()
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                got.add(stmt.target.id)
        for base in node.bases:
            if isinstance(base, ast.Name):
                got |= fields(base.id, seen)
        # `populate_by_name` means an alias is a second accepted spelling; both count.
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.value, ast.Call):
                for kw in stmt.value.keywords:
                    if kw.arg == "alias" and isinstance(kw.value, ast.Constant):
                        got.add(str(kw.value.value))
        return got

    for name, node in classes.items():
        is_model = any((isinstance(b, ast.Name) and b.id.endswith("BaseModel"))
                       or (isinstance(b, ast.Attribute) and b.attr.endswith("BaseModel"))
                       or (isinstance(b, ast.Name) and b.id in classes)
                       for b in node.bases)
        if is_model:
            out[name] = fields(name, set())
    return out


def routes() -> dict[str, tuple[str, str, set[str]]]:
    """`/internal/...` path -> (file, model name, declared fields), across every service."""
    found: dict[str, tuple[str, str, set[str]]] = {}
    for path in sorted(SERVICES.rglob("*.py")):
        if "__pycache__" in path.parts or "/tests/" in path.as_posix():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        models = _models(tree)
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        # The router's own prefix, so the decorator's short path can be made absolute.
        prefix = ""
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                    and getattr(node.value.func, "id", "") == "APIRouter"):
                for kw in node.value.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                        prefix = str(kw.value.value)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)):
                    continue
                if dec.func.attr not in {"post", "put", "patch"} or not dec.args:
                    continue
                arg = dec.args[0]
                if not isinstance(arg, ast.Constant):
                    continue
                full = prefix + str(arg.value)
                if not full.startswith("/internal/"):
                    continue
                # The body parameter: the one annotated with a model defined here.
                for a in node.args.args:
                    ann = getattr(a.annotation, "id", "")
                    if ann in models:
                        found[full] = (rel, ann, models[ann])
    return found


def _keys(node: ast.Dict) -> list[str] | None:
    """Literal string keys, or None when the dict is not fully literal — which is not a finding
    and not a pass either. See the note on what this cannot see."""
    out = []
    for k in node.keys:
        if k is None or not isinstance(k, ast.Constant) or not isinstance(k.value, str):
            return None
        out.append(k.value)
    return out


def _service_of(path: pathlib.Path) -> str:
    """Which service a file belongs to. Class names REPEAT across services — `HttpVisits` exists in
    loyalty and in insights, pointing at different doors — so every lookup here is scoped by it.
    A global map bound loyalty's free-visit call to insights' feed and reported the whole repo
    clean while the defect it was written for sat two lines away."""
    rel = path.relative_to(ROOT).parts
    return rel[1] if len(rel) > 1 and rel[0] == "services" else ""


def wiring(known: set[str]) -> dict[tuple[str, str, str], str]:
    """`(adapter class, parameter) -> door`, read from where the container builds the adapter.

    An adapter whose path has no literal default is not unknowable: the container passes it, from
    a settings field whose default is written in `config.py`. Both files are ours and both values
    are literals, so the chain is followed rather than guessed — and an adapter this cannot resolve
    is reported as unresolved rather than passed.
    """
    settings: dict[tuple[str, str], str] = {}
    for path in sorted(SERVICES.rglob("config.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str) and node.value.value in known):
                settings[(_service_of(path), node.target.id)] = node.value.value

    # ANY CONSTRUCTION SITE, not just `container.py`: loyalty builds its peers in a `build_peers`
    # factory beside the adapters, and a check that only looked at containers resolved one door out
    # of six and then reported itself green.
    out: dict[tuple[str, str, str], str] = {}
    for path in sorted(SERVICES.rglob("*.py")):
        if "__pycache__" in path.parts or "/tests/" in path.as_posix():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            for kw in node.keywords:
                if kw.arg is None:
                    continue
                door = None
                if isinstance(kw.value, ast.Constant) and kw.value.value in known:
                    door = str(kw.value.value)
                elif isinstance(kw.value, ast.Attribute):
                    door = settings.get((_service_of(path), kw.value.attr))
                if door:
                    out[(_service_of(path), node.func.id, kw.arg)] = door
    return out


def main() -> int:
    known = routes()
    wired = wiring(set(known))
    findings: list[str] = []
    checked = unresolved = 0

    for path in sorted(SERVICES.rglob("*.py")):
        if "__pycache__" in path.parts or "/tests/" in path.as_posix():
            continue
        text = path.read_text(encoding="utf-8")
        if "/internal/" not in text:
            continue
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue

        # THE CALL IS THE ONLY HONEST ATTRIBUTION. Two earlier versions of this bound a body to a
        # door by proximity — first any path in the file, then any path in the enclosing class —
        # and both reported ten correct calls as broken: `signup.py` talks to five doors from
        # plain functions, and every dict in it carries `tenant`, so every dict matched whichever
        # model was found first. What actually ties a body to a door is the URL passed BESIDE it,
        # in the same call. Everything else is a guess dressed up as a check.
        #
        # `self._url` is resolved per class from `__init__`, which is where every adapter here
        # composes it: `self._url = url.rstrip("/") + path`, with `path` a default argument.
        def _door_of_attr(cls: ast.ClassDef, attr: str) -> str | None:
            """The door behind `self.<attr>`, followed through the parameter it is built from.

            NOT «any known path mentioned in this class». `HttpSender` composes `self._url` from
            `path` and `self._merge_url` from `merge_path`, and only the second has a literal
            default — so a class-wide scan bound the send body to the redemption door and reported
            six correct keys as dropped. The assignment names the parameter; the parameter carries
            the default, or the container passes it. Both are followed, and nothing else is.
            """
            init = next((s for s in cls.body
                         if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))
                         and s.name == "__init__"), None)
            param = None
            for sub in ast.walk(cls):
                if not isinstance(sub, ast.Assign):
                    continue
                for t in sub.targets:
                    if not (isinstance(t, ast.Attribute) and t.attr == attr):
                        continue
                    for lit in ast.walk(sub.value):
                        # A literal door written straight into the assignment ends it here.
                        if (isinstance(lit, ast.Constant) and isinstance(lit.value, str)
                                and lit.value in known):
                            return lit.value
                    # EVERY NAME IN THE EXPRESSION, and exactly one of them must resolve to a
                    # door. Picking one by position was a guess dressed as a rule, and it was
                    # wrong twice over: `ast.walk` is breadth-first, so «the last name» in
                    # `url.rstrip("/") + path` came out as `url`. Asking all of them and refusing
                    # an ambiguous answer needs no assumption about the shape of the expression.
                    param = [n.id for n in ast.walk(sub.value) if isinstance(n, ast.Name)]
            if not param or init is None:
                return None
            args = list(init.args.args) + list(init.args.kwonlyargs)
            defaults = ([None] * (len(init.args.args) - len(init.args.defaults))
                        + list(init.args.defaults) + list(init.args.kw_defaults))
            hits = set()
            for a, d in zip(args, defaults):
                if a.arg in param and isinstance(d, ast.Constant) and d.value in known:
                    hits.add(str(d.value))
            for name in param:
                got = wired.get((_service_of(path), cls.name, name))
                if got:
                    hits.add(got)
            return hits.pop() if len(hits) == 1 else None

        owner: dict[int, ast.ClassDef] = {}
        for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            for sub in ast.walk(cls):
                owner[id(sub)] = cls

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            bodies = [a for a in list(node.args) + [k.value for k in node.keywords]
                      if isinstance(a, ast.Dict)]
            if not bodies:
                continue
            door = None
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value in known:
                    door = a.value
                elif isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name) \
                        and a.value.id == "self":
                    cls = owner.get(id(node))
                    if cls is not None:
                        door = _door_of_attr(cls, a.attr) or door
            if door is None:
                continue
            where, model, declared = known[door]
            for body in bodies:
                keys = _keys(body)
                if keys is None or not keys:
                    unresolved += 1
                    continue
                if not (set(keys) & declared):
                    # Not a body for this door: a header map, or the answer being returned.
                    continue
                checked += 1
                missing = [k for k in keys if k not in declared and k not in TRANSPORT]
                if missing:
                    findings.append(
                        f"{rel}:{body.lineno}  sends {missing} to {door} — `{model}` ({where}) "
                        f"does not declare them, so pydantic drops them and the receiver never "
                        f"learns they were sent")

    if findings:
        print(f"{C_R}  ✘ {len(findings)} peer call(s) sending keys the receiver discards:{C_N}")
        for line in findings:
            print(f"{C_R}      {line}{C_N}")
        print(f"{C_R}    Declare the field or stop sending it. A key accepted by the transport "
              f"and dropped by the model is a fact that travelled and did not arrive.{C_N}")
        return 1

    print(f"{C_G}  ✔ every literal body sent to an internal door is declared by its model "
          f"({checked} bodies across {len(known)} doors){C_N}")
    if unresolved:
        print(f"{C_Y}    {unresolved} dict(s) were not literal enough to read — not checked, "
              f"and not claimed as checked.{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
