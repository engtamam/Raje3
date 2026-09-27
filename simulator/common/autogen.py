"""The answer to "why do WE write the Action — can't the simulator understand the app itself?":
this generates a REAL, runnable Action straight from a route's OWN schema, read live off the
SPAWNED SERVICE ITSELF (its real `/openapi.json`) — the smartest possible link, since it is not
even parsing source code, it is asking the running app what it accepts, the same document its own
generated SDKs/contracts elsewhere in this repo already come from.

WHAT THIS DOES NOT CLAIM TO REPLACE. A schema says a field is a string of length 3-32; it cannot
say that string should look like a Saudi phone number, or that creating a mobile request needs a
branch to exist first. Business-meaningful, multi-step scenarios stay hand-written (the whole
`apps/<name>/actions.py` files this session already built) — this generates the MECHANICAL part a
schema fully determines: a single, schema-valid call to a single route, for the fuzzing/coverage
class of testing a hand-written Action was never meant for (does EVERY declared route accept a
well-formed body without a 500, the same question Schemathesis asks of an OpenAPI spec — see the
README's own taxonomy note on where that precedent came from).
"""
from __future__ import annotations

import random
import string
from dataclasses import dataclass, field
from typing import Any

import httpx

from .action import ActionResult, Context
from .discovery import DeclaredAction

Schemas = dict[str, Any]


async def fetch_openapi(base_url: str) -> dict[str, Any]:
    """The service's own live schema — `ENV=test` (every spawned service in this simulator boots
    this way, see `shared/service_env.py`) is precisely what keeps `/openapi.json` switched on;
    `main.py` disables it only in production."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{base_url}/openapi.json", timeout=10.0)
    r.raise_for_status()
    return r.json()


def _resolve(schema: Schemas, root: Schemas) -> Schemas:
    """Follow one `$ref` against `components.schemas` — this repo's own generated OpenAPI never
    nests refs more than one level for a request body, so one hop is enough; a schema this cannot
    resolve is treated as "no constraints", never a crash (`generate_value`'s own fallback)."""
    ref = schema.get("$ref")
    if not ref:
        return schema
    name = ref.rsplit("/", 1)[-1]
    return root.get("components", {}).get("schemas", {}).get(name, {})


def _random_string(min_length: int = 0, max_length: int = 20) -> str:
    length = max(min_length, min(max_length, max(min_length, 6)))
    return "".join(random.choices(string.ascii_lowercase, k=length))


def generate_value(schema: Schemas, root: Schemas) -> Any:
    """One value that satisfies `schema` — deliberately simple, boundary-aware generation (nearest
    to a schema's own minimum/lower bound, since a scenario proving "every declared route accepts
    A well-formed body" only needs ONE valid instance, not a full property-based search — that is
    Schemathesis' own job on a spec, and duplicating its search strategy here would be reinventing
    a tool this project already cites rather than composing with it)."""
    schema = _resolve(schema, root)
    if "default" in schema:
        return schema["default"]
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    if "anyOf" in schema:
        return generate_value(schema["anyOf"][0], root)
    schema_type = schema.get("type")

    if schema_type == "string":
        min_len = int(schema.get("minLength", 0) or 0)
        max_len = int(schema.get("maxLength", 20) or 20)
        if schema.get("format") == "date-time":
            return "2026-01-01T00:00:00Z"
        return _random_string(min_len, max_len)
    if schema_type == "integer":
        low = schema.get("minimum", schema.get("exclusiveMinimum", 0))
        low = int(low) + (1 if "exclusiveMinimum" in schema else 0)
        high = schema.get("maximum")
        return low if high is None else min(int(high), max(low, low))
    if schema_type == "number":
        low = schema.get("minimum", 0)
        return float(low)
    if schema_type == "boolean":
        return False
    if schema_type == "array":
        min_items = int(schema.get("minItems", 0) or 0)
        item_schema = schema.get("items", {})
        count = max(min_items, 1 if min_items else 0)
        return [generate_value(item_schema, root) for _ in range(count)]
    if schema_type == "object" or "properties" in schema:
        return generate_object(schema, root)
    # Unconstrained/unknown type — "" is a valid, harmless instance for the overwhelmingly common
    # case here (an untyped free-form field), never a crash for a shape this cannot recognise.
    return ""


def generate_object(schema: Schemas, root: Schemas) -> dict[str, Any]:
    schema = _resolve(schema, root)
    required = set(schema.get("required", []))
    props: Schemas = schema.get("properties", {})
    out: dict[str, Any] = {}
    for prop_name, prop_schema in props.items():
        # ONLY REQUIRED FIELDS ARE FILLED, on purpose — the route's own defaults for everything
        # optional are exactly what a real, honest caller who has nothing to say about a field
        # would send (omit it), and filling every field regardless would exercise this generator's
        # own guesses far more than the route's real optional-field handling.
        if prop_name in required:
            out[prop_name] = generate_value(prop_schema, root)
    return out


def find_operation(openapi: Schemas, method: str, path: str) -> Schemas | None:
    """OpenAPI keys a path exactly as FastAPI declared it (`{request_id}`, not a filled-in value) —
    `DeclaredAction.path` already carries the SAME real route string `user_actions.py` declares
    (see that file's own docstring: it is what makes the undeclared-route CI gate meaningful at
    all), so this is a direct dict lookup, never a fuzzy match."""
    item = openapi.get("paths", {}).get(path)
    if item is None:
        return None
    return item.get(method.lower())


@dataclass
class AutoAction:
    """A single, schema-valid HTTP call to one declared route — generated, not hand-written. Real
    HTTP against a real spawned service, the same as every hand-written Action in `apps/`; the only
    difference is where the request BODY came from.

    `path_params` is the one thing a schema cannot supply on its own (an id from an EARLIER call in
    the same scenario) — left for the caller to fill; a route this simulator has not been told
    values for and that still needs one is out of scope for auto-generation, same limitation this
    module's own docstring names up front."""

    base_url: str
    tenant: str
    declared: DeclaredAction
    openapi: Schemas
    path_params: dict[str, str] = field(default_factory=dict)
    caller_subject: str = "owner"
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"auto:{self.declared.id}"

    def _filled_path(self) -> str:
        path = self.declared.path
        for key, value in self.path_params.items():
            path = path.replace(f"{{{key}}}", value)
        return path

    async def run(self, ctx: Context) -> ActionResult:
        from simulator.shared.auth import auth_header

        operation = find_operation(self.openapi, self.declared.method, self.declared.path)
        body: dict[str, Any] | None = None
        if operation is not None:
            body_schema = (operation.get("requestBody", {}).get("content", {})
                          .get("application/json", {}).get("schema"))
            if body_schema:
                body = generate_object(body_schema, self.openapi)

        headers = auth_header(tenant=self.tenant, caps=(self.declared.capability,),
                              subject=self.caller_subject)
        url = f"{self.base_url}{self._filled_path()}"
        async with httpx.AsyncClient() as client:
            r = await client.request(self.declared.method, url, json=body, headers=headers,
                                     timeout=10.0)
        # THE ONLY THING AN AUTO-GENERATED CALL CAN HONESTLY ASSERT: the route did not CRASH. A
        # well-formed-but-meaningless body (a random phone, a made-up service id) is very often
        # refused by a real business rule this generator knows nothing about — a 4xx REFUSAL is
        # success for this Action's own purpose. 503 IS ALSO NOT A CRASH HERE, and excluding it is
        # deliberate, not a loophole: this codebase's own documented posture, repeated across
        # several real routes this simulator already drives (till.py's licence check, field.py's
        # PDF export, subscription's own checkout) is "an unreachable PEER refuses cleanly (503)
        # rather than guesses" — and this generator spawns ONLY the one service under test, no
        # billing/pdf-conversion/payment peer behind it, so a 503 here is that exact, correct,
        # by-design refusal, not evidence of a bug. Only 500 (an actually unhandled exception) is
        # `ok=False`.
        ok = r.status_code != 500
        return ActionResult(ok=ok, detail=f"{self.declared.method} {self.declared.path} -> "
                                          f"{r.status_code}",
                            data={"status": r.status_code, "body": body})


async def autogen_actions(base_url: str, declared: list[DeclaredAction], *,
                          tenant: str) -> list[AutoAction]:
    """One `AutoAction` per declared route that carries no unfilled path parameter — the mechanical
    subset a schema fully determines on its own, with zero hand-written code per route."""
    openapi = await fetch_openapi(base_url)
    out: list[AutoAction] = []
    for d in declared:
        if "{" in d.path:
            # Needs an id from elsewhere — out of scope for a fully-automatic call, see this
            # module's own docstring on `AutoAction.path_params`.
            continue
        out.append(AutoAction(base_url=base_url, tenant=tenant, declared=d, openapi=openapi))
    return out
