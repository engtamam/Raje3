"""A real test for `check_branch_scope.py`'s own AST matching — not the CI gate itself (which has
no service to boot, no fixtures, and runs as a plain script over the real repo), but the one piece
of it worth pinning down with a unit test: `_calls_any`/`_call_matches` deciding whether a function
REALLY calls a scope resolver, as opposed to merely mentioning its name.

WHY THIS EXISTS. An adversarial security audit of this project's step 3 found that the original
`_calls_any` checked `tok in ast.get_source_segment(text, fn)` — a substring search over the WHOLE
function source, docstring and comments included. A route whose docstring merely NAMED
`branch_scope()`, even to say it deliberately does not call it, passed the gate. The fix replaced
the substring search with a real AST `Call`-node check; this test is the proof that the exact
adversarial example from the audit now fails the gate the way it always should have.
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "ci" / "check_branch_scope.py"


def _load():
    spec = importlib.util.spec_from_file_location("cbs_under_test", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


cbs = _load()


def _parse_one(src: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(src)
    return tree.body[0]  # type: ignore[return-value]


# ── the exact adversarial case the audit reported ────────────────────────────────────────────────
def test_a_docstring_that_only_mentions_the_resolvers_name_does_not_pass():
    """The literal example the audit gave: a docstring saying branch_scope is NOT called here, and
    a body that genuinely never calls it. The substring version of this check read `branch_scope`
    in the docstring and reported this function as scoped — exactly backwards."""
    src = '''
async def list_bookings(tenant):
    """NOTE: does not call branch_scope() here, handled upstream."""
    return await svc.list_all(tenant)
'''
    fn = _parse_one(src)
    assert cbs._calls_any(fn, ("branch_scope",), {}) is False


def test_a_comment_naming_the_resolver_does_not_pass_either():
    src = '''
async def read_something(tenant):
    # branch_scope() is applied by the caller, not here
    return await svc.read(tenant)
'''
    fn = _parse_one(src)
    assert cbs._calls_any(fn, ("branch_scope",), {}) is False


# ── the real shapes this gate must still recognise ───────────────────────────────────────────────
def test_a_bare_name_call_passes():
    src = '''
async def recent_customers(tenant, principal):
    scope = await branch_scope(store, principal)
    return scope
'''
    fn = _parse_one(src)
    assert cbs._calls_any(fn, ("branch_scope",), {}) is True


def test_an_attribute_call_passes():
    src = '''
async def dashboard(tenant):
    scope = await peers.branch_scope(tenant)
    return scope
'''
    fn = _parse_one(src)
    assert cbs._calls_any(fn, ("branch_scope",), {}) is True


def test_the_getattr_by_string_shape_bookings_reminders_and_insights_all_use_passes():
    """`getattr(container, "branch_scope", None)` — not a literal `.branch_scope` attribute
    access, so it would be invisible to a naive AST `Attribute` check. This is the real shape
    `bookings.py::_require_branch`, `owner.py::_branch_scope`, and `insights.py::dashboard` all
    use, confirmed by re-running the gate on the real repo after this fix (still clean)."""
    src = '''
async def _require_branch(container, tenant):
    resolver = getattr(container, "branch_scope", None)
    if resolver is None:
        return
    scope = await resolver.scope(tenant)
    return scope
'''
    fn = _parse_one(src)
    assert cbs._calls_any(fn, ("branch_scope",), {}) is True


def test_a_getattr_naming_something_else_does_not_false_positive():
    src = '''
async def read_settings(container):
    resolver = getattr(container, "something_else", None)
    return resolver
'''
    fn = _parse_one(src)
    assert cbs._calls_any(fn, ("branch_scope",), {}) is False


# ── the same-file helper recursion, unchanged by this fix ───────────────────────────────────────
def test_delegating_to_a_same_file_helper_that_really_calls_it_still_passes():
    """The `field.py::staff_performance` shape this gate was built to stop flagging as a false
    positive — a route delegates to a helper that itself calls the resolver."""
    src_route = '''
async def staff_performance(tenant):
    return await _staff_performance_rows(tenant)
'''
    src_helper = '''
async def _staff_performance_rows(tenant):
    scope = await branch_scope(store, principal)
    return scope
'''
    route_fn = _parse_one(src_route)
    helper_fn = _parse_one(src_helper)
    fn_map = {"_staff_performance_rows": helper_fn}
    assert cbs._calls_any(route_fn, ("branch_scope",), fn_map) is True


def test_delegating_to_a_helper_that_only_mentions_it_in_its_own_docstring_still_fails():
    """The adversarial case one level deeper — a helper whose OWN docstring mentions the resolver
    but whose body never calls it. Delegating to it must not launder an unscoped read into a
    scoped one."""
    src_route = '''
async def list_bookings(tenant):
    return await _unscoped_helper(tenant)
'''
    src_helper = '''
async def _unscoped_helper(tenant):
    """branch_scope() is intentionally not called here."""
    return await svc.list_all(tenant)
'''
    route_fn = _parse_one(src_route)
    helper_fn = _parse_one(src_helper)
    fn_map = {"_unscoped_helper": helper_fn}
    assert cbs._calls_any(route_fn, ("branch_scope",), fn_map) is False


# ── the real repo, end to end ────────────────────────────────────────────────────────────────────
def test_the_gate_is_still_clean_against_the_real_repo_after_the_fix():
    """The tightened check must not regress anything already correct — every route this gate
    actually names in DOMAIN_ROUTES/MOBILE_REQUESTS_ROUTES today calls a real resolver, verified
    fresh rather than assumed."""
    assert cbs.main() == 0
