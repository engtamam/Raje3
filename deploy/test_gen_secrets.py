#!/usr/bin/env python3
"""Regression test for deploy/gen-secrets.py's own worst bug: a re-run used to
rebuild every existing secret's DATASTORE_DSN from one global PG_DB default, which silently
replaced operations'/campaigns'/bookings'/insights'/loyalty's/reminders' own real databases with
the (separate, near-empty) shared one — on a live cluster, with data already in every one of them.

No pytest dependency, deliberately, matching gen_secrets.py's own zero-dependency stance: this runs
as `python3 deploy/test_gen_secrets.py` and exits non-zero on any failure.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

# `gen-secrets.py` has a hyphen, which is not a valid module name for a plain `import` — loaded by
# path instead, same trick every plugin loader uses for a file it cannot name as a module.
_spec = importlib.util.spec_from_file_location(
    "gen_secrets", Path(__file__).resolve().parent / "gen-secrets.py")
G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(G)


def _b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


def _fake_kubectl_get(existing: dict[str, dict[str, str]]):
    """A `kubectl -n NS get secret -o json` stand-in carrying whatever secrets already exist."""
    items = [{"metadata": {"name": name}, "data": {k: _b64(v) for k, v in data.items()}}
             for name, data in existing.items()]
    return mock.Mock(returncode=0, stdout=json.dumps({"items": items}))


def test_an_existing_dsn_survives_a_rerun_untouched():
    shared = {"INTERNAL_SERVICE_TOKEN": "t" * 40, "PII_SALT": "s" * 32,
              "TOKEN_HS256_SECRET": "h" * 40, "POSTGRES_PASSWORD": "shared-pw",
              "SECRETS_KEK": "k" * 40, "BACKUP_KEK": "b" * 40}
    # THE REAL, ALREADY-CORRECT STATE: operations already has its OWN database, minted long
    # before this script's global PG_DB default ("base_services") existed.
    real_dsn = "postgresql://base_services:shared-pw@postgres:5432/operations"
    existing = {
        "platform-secrets": dict(shared),
        "operations-secrets": {**shared, "DATASTORE_DSN": real_dsn, "CACHE_URL": "redis://x"},
    }

    schema = {"operations-secrets": {"keys": {
        "DATASTORE_DSN": {"t": "dsn", "role": "base_services"},
        "CACHE_URL": {"t": "const"},
        "PII_SALT": {"t": "shared"},
    }}}

    applied: dict[str, dict[str, str]] = {}

    def fake_run(args, **kwargs):
        if args[:4] == ["kubectl", "-n", G.NS, "get"]:
            return _fake_kubectl_get(existing)
        if "create" in args:
            name = args[args.index("secret") + 2]
            data = {}
            for a in args:
                if a.startswith("--from-literal="):
                    k, v = a[len("--from-literal="):].split("=", 1)
                    data[k] = v
            applied[name] = data
            return mock.Mock(returncode=0, stdout="fake-yaml")
        return mock.Mock(returncode=0, stdout="")

    with mock.patch.object(G, "SCHEMA", mock.Mock(read_text=lambda encoding: json.dumps(schema))), \
         mock.patch.object(subprocess, "run", side_effect=fake_run):
        G.generate_and_apply()

    assert "operations-secrets" not in applied, (
        "operations-secrets was re-applied even though every one of its schema keys already "
        "existed — the exact no-op case that must never touch a live secret")


def test_a_missing_key_is_filled_in_without_touching_the_rest():
    shared = {"INTERNAL_SERVICE_TOKEN": "t" * 40, "PII_SALT": "s" * 32,
              "TOKEN_HS256_SECRET": "h" * 40, "POSTGRES_PASSWORD": "shared-pw",
              "SECRETS_KEK": "k" * 40, "BACKUP_KEK": "b" * 40}
    real_dsn = "postgresql://base_services:shared-pw@postgres:5432/operations"
    existing = {
        "platform-secrets": dict(shared),
        # A NEW FIELD (BACKUP_KEK) was added to operations' config.py since this secret was
        # last minted — the one case this script SHOULD still act on.
        "operations-secrets": {**{k: v for k, v in shared.items() if k != "BACKUP_KEK"},
                              "DATASTORE_DSN": real_dsn},
    }
    schema = {"operations-secrets": {"keys": {
        "DATASTORE_DSN": {"t": "dsn", "role": "base_services"},
        "BACKUP_KEK": {"t": "shared"},
    }}}

    applied: dict[str, dict[str, str]] = {}

    def fake_run(args, **kwargs):
        if args[:4] == ["kubectl", "-n", G.NS, "get"]:
            return _fake_kubectl_get(existing)
        if "create" in args:
            name = args[args.index("secret") + 2]
            data = {}
            for a in args:
                if a.startswith("--from-literal="):
                    k, v = a[len("--from-literal="):].split("=", 1)
                    data[k] = v
            applied[name] = data
            return mock.Mock(returncode=0, stdout="fake-yaml")
        return mock.Mock(returncode=0, stdout="")

    with mock.patch.object(G, "SCHEMA", mock.Mock(read_text=lambda encoding: json.dumps(schema))), \
         mock.patch.object(subprocess, "run", side_effect=fake_run):
        G.generate_and_apply()

    assert applied["operations-secrets"]["DATASTORE_DSN"] == real_dsn, (
        "the pre-existing DSN was reconstructed instead of preserved")
    assert applied["operations-secrets"]["BACKUP_KEK"] == shared["BACKUP_KEK"]


if __name__ == "__main__":
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok  {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL  {name}: {exc}")
    sys.exit(1 if failures else 0)
