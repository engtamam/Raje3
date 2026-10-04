"""SecretsProvider contract — every driver a deployment may select, held to one behaviour.

WHAT IT USED TO BE. Five tests, two named after `env` and three after `file`, each written against
one class rather than against the port. Two drivers, two different sets of promises, and no single
place saying what a secrets provider IS.

AND THERE WAS A THIRD NAME, `vault`, WHICH IS WHY THIS FILE CHANGED TWICE IN ONE NIGHT. It was
offered by `container.py`, so any deployment could select it with one word — and none ever did:
`SECRETS_DRIVER` defaults to `env`, no values file overrides it, no VAULT_* setting is filled
anywhere, and its `hvac` extra was never installed. It was first given a contract here, with a
loopback server speaking KV-v2. Then the question that work raised got answered — «vault? do we
use it?» — and the honest answer was no.

So it is gone from the registry rather than described here, and this file is now the shape the
repository prefers: a table of behaviours, and every name a deployment can choose goes through all
of them. `ci/check_every_shipped_driver_is_held_to_its_contract.py` is what keeps the two lists
equal — add a driver without adding it here and it refuses.
"""
from __future__ import annotations

import pytest

from app.adapters.secrets.env import EnvSecrets
from app.adapters.secrets.file import FileSecrets
from app.ports.errors import ConfigError

STORED = {"API_KEY": "the-value", "OTHER": "second"}


@pytest.fixture
def env_provider(monkeypatch):
    for name, value in STORED.items():
        monkeypatch.setenv(name, value)
    return EnvSecrets()


@pytest.fixture
def file_provider(tmp_path, monkeypatch):
    for name in STORED:
        monkeypatch.delenv(name, raising=False)
    path = tmp_path / "secrets.env"
    path.write_text("".join(f"{k}={v}\n" for k, v in STORED.items()), encoding="utf-8")
    return FileSecrets(str(path))


#: THE NAMES ARE THE REGISTRY'S NAMES, and there is no third.
_PARAMS = [
    pytest.param("env_provider", id="env"),
    pytest.param("file_provider", id="file"),
]


@pytest.fixture
def provider(request):
    return request.getfixturevalue(request.param)


@pytest.mark.parametrize("provider", _PARAMS, indirect=True)
class TestEverySecretsProvider:
    def test_a_stored_secret_comes_back(self, provider):
        assert provider.get("API_KEY") == "the-value"

    def test_require_returns_the_same_value(self, provider):
        assert provider.require("API_KEY") == "the-value"

    def test_an_absent_name_is_none_rather_than_an_empty_string(self, provider):
        # NONE AND "" ARE DIFFERENT ANSWERS. Callers branch on «is it set», and a driver that
        # returns "" for a name it does not have turns a missing credential into a configured one.
        assert provider.get("NEVER_SET_ANYWHERE") is None

    def test_require_refuses_rather_than_returning_nothing(self, provider):
        with pytest.raises(ConfigError):
            provider.require("NEVER_SET_ANYWHERE")


def test_the_environment_wins_over_a_file(tmp_path, monkeypatch):
    # THE PRECEDENCE IS THE POINT OF HAVING TWO. An operator must be able to override one value on
    # one machine without editing a file every deploy rewrites.
    path = tmp_path / "secrets.env"
    path.write_text("API_KEY=from_file\n", encoding="utf-8")
    monkeypatch.setenv("API_KEY", "from_env")
    assert FileSecrets(str(path)).get("API_KEY") == "from_env"


def test_a_file_that_is_not_there_does_not_stop_the_boot(tmp_path):
    assert FileSecrets(str(tmp_path / "absent.env")).get("ANY") is None


def test_a_file_keeps_comments_out_and_strips_quotes(tmp_path, monkeypatch):
    monkeypatch.delenv("QUOTED", raising=False)
    path = tmp_path / "secrets.env"
    path.write_text('# a note\nQUOTED="q v"\n', encoding="utf-8")
    assert FileSecrets(str(path)).get("QUOTED") == "q v"
