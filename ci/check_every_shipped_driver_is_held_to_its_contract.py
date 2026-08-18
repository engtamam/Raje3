"""A driver a deployment can choose must be held to its kind's contract.

WHAT THE CONTRACT SUITES ACTUALLY COVER TODAY, AND IT IS NOT WHAT THEIR NAME SUGGESTS.

`app/container.py` declares, per kind, exactly which drivers a deployment may select — one
registry per kind, keyed by the value of its `*_DRIVER` setting. `tests/contracts/` exists to hold
every one of them to the same behaviour, so that switching a driver in a values file is a
configuration change and not a rewrite of what the product does.

Two kinds do that. The rest test the in-memory driver and stop:

    cache        memory ✔  redis ✘        the fleet runs redis
    event_bus    memory ✔  redis ✘        the fleet runs redis
    queue        memory ✔  redis ✘        the fleet runs redis — and it carries the send queue
    rate_limiter memory ✔  redis ✘        the fleet runs redis

AND THE QUEUE CONTRACT KNOWS. Its own docstring names a defect the redis adapter had — «the Redis
adapter was LPOP, so a worker killed mid-job took the job with it: no retry» — and then
parametrises `MemoryQueue` alone. The thing that lost jobs is the thing no test holds.

THIS IS NOT THE SAME GAP AS THE SKIPPED CONTRACTS. Those declared a real driver and skipped it for
want of a server, and said so on every run. These declare nothing: there is no skip to notice, no
line in any summary, and the suite reads as though the contract were satisfied.

THE RULE. Every key in a container registry must appear in that kind's contract test. `null`
drivers are excluded and only those: a driver that deliberately does nothing has no behaviour to
hold to a contract, and the boot guard already refuses it in production.

    python ci/check_every_shipped_driver_is_held_to_its_contract.py
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"

#: A registry in `container.py`: `_CACHE: dict[str, Builder] = { "memory": …, "redis": … }`.
REGISTRY = re.compile(r"^_([A-Z][A-Z0-9_]*)\s*:\s*dict\[str,\s*Builder\]", re.M)

#: THE SUBJECT: the ports that stand between the product and a running server. Each is a thing a
#: deployment points at infrastructure — a database, a cache, a queue, a bus, a limiter, a bucket —
#: and each already has a contract file whose whole purpose is that switching the pointer is
#: configuration rather than a change in what the product does.
#:
#: `token_verifier` JOINED THEM, AND WHAT IT COST WAS A THREAD. Its three drivers looked covered
#: — there were tests named after two of them — but the sets were different and `jwks` had none at
#: all. It is now one table of behaviours with a loopback key server for the length of a test, so
#: «it needs a network» turned out to be a reason to give it one rather than to leave it unheld.
#:
#: WHAT THIS GATE STILL DOES NOT COVER, SAID OUT LOUD SO ITS GREEN IS NOT READ FOR MORE THAN IT
#: IS: `secrets` (vault) and the peer-shaped adapters — audit sink, consent gate, telemetry. Those
#: are the same rule and each needs a server or a stub; they are recorded as work, not waved
#: through here. A narrower rule fully enforced beats a broad one with a list of exceptions
#: underneath it — but only while the narrowing is written down.
CONTRACT_OF = {
    "DATASTORE": "test_datastore_contract.py",
    "CACHE": "test_cache_contract.py",
    "EVENTBUS": "test_event_bus_contract.py",
    "QUEUE": "test_queue_contract.py",
    "OBJECTSTORE": "test_object_store_contract.py",
    "RATELIMITER": "test_rate_limiter_contract.py",
    "TOKEN": "test_token_verifier_contract.py",
}

#: DOES NOTHING, ON PURPOSE. A null driver has no behaviour to agree with, and production refuses
#: it at boot. Every other name here is a real implementation somebody can switch on.
DOES_NOTHING = {"null"}


def _named_in_parameters(source: str) -> set[str]:
    """Every driver name the file NAMES as a parameter — nothing weaker counts.

    THREE THINGS SATISFIED EARLIER VERSIONS OF THIS GATE AND NONE OF THEM RAN A TEST: the word in
    a comment explaining how to start a server, the word in a docstring about a defect, and the
    import of the class. Each was proved by sabotage: deleting the line that adds the parameter
    left the gate green, twice.

    WHAT A PARAMETRISATION ACTUALLY LOOKS LIKE, IN BOTH SHAPES THIS REPOSITORY USES:

        pytest.param(lambda: RedisQueue(url), id="redis")
        @pytest.fixture(params=["memory", "local", "s3"])

    Both NAME the driver in a string that pytest prints beside the test. So the evidence is the
    file's string literals — minus its docstrings, which are prose and were the first false green.
    """
    tree = ast.parse(source)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))
    return {n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docstrings}


def _registries(source: str) -> dict[str, list[str]]:
    """Every kind and the driver names a deployment may select for it."""
    tree = ast.parse(source)
    out: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
            continue
        name = node.target.id
        if not name.startswith("_") or not name[1:].isupper():
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        keys = [k.value for k in node.value.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)]
        if keys:
            out[name[1:]] = keys
    return out


def main() -> int:
    if not SERVICES.is_dir():
        print("services/ is missing — this gate cannot answer, and that is not a pass")
        return 1

    bad: list[str] = []
    checked = 0
    for service in sorted(p for p in SERVICES.iterdir() if p.is_dir()):
        container = service / "app" / "container.py"
        contracts = service / "tests" / "contracts"
        if not container.is_file() or not contracts.is_dir():
            continue
        for kind, drivers in sorted(_registries(container.read_text(encoding="utf-8")).items()):
            filename = CONTRACT_OF.get(kind)
            if filename is None:
                # OUTSIDE THE SUBJECT — see CONTRACT_OF. Not «exempt»: the rule above says which
                # ports this gate is about, and a kind it does not name is not one of them.
                continue
            path = contracts / filename
            if not path.is_file():
                bad.append(f"{service.name}: {filename} is missing — _{kind} is held to nothing")
                continue
            named = _named_in_parameters(path.read_text(encoding="utf-8"))
            for driver in drivers:
                if driver in DOES_NOTHING:
                    continue
                checked += 1
                if driver not in named:
                    bad.append(f"{service.name}: {kind.lower()} driver «{driver}» is selectable "
                               f"and absent from {filename}")

    if bad:
        print("  \033[31m✘ drivers a deployment can switch on that no contract holds:\033[0m")
        for line in bad:
            print(f"      \033[31m{line}\033[0m")
        print("\n    Add the driver to its contract's parameters — skipping when its server is "
              "absent, which is\n    honest and visible — or take it out of the registry. A "
              "driver nothing tests is a rewrite of\n    the product's behaviour wearing the "
              "word «configuration». Do not exempt it here.")
        return 1

    print(f"  \033[32m✔ every selectable driver is held to its contract ({checked})\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
