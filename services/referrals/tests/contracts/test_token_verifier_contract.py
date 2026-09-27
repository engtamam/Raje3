"""TokenVerifier contract — every driver a deployment may select, held to one behaviour.

WHAT THIS FILE USED TO BE, AND WHY THAT WAS NOT A CONTRACT. It had six tests: three named
`test_hs256_*` and two named `test_rs256_*`, each written against one class. Both drivers were
exercised, so the file looked complete — and it was not, in two ways that matter.

  · THE SETS WERE DIFFERENT. hs256 was checked against a forged signature; rs256 was not. Neither
    was checked against a token issued by somebody else, or minted for another audience. A driver
    that quietly ignored `iss` and `aud` passed this file, and `iss`/`aud` are the whole reason a
    token from one service cannot be replayed at another.
  · `jwks` WAS NOT HERE AT ALL, and `container.py` offers it. A name a deployment can select and
    no test can describe is a promise the product has not read.

So it is one table of behaviours now, and every driver goes through all of them. Adding a driver
to the registry without adding it here is what `ci/check_every_shipped_driver_is_held_to_its_contract.py`
refuses — which is why the parameter ids below are `hs256`, `rs256`, `jwks` and nothing else.

NO INFRASTRUCTURE, INCLUDING FOR `jwks`. The key set is served by a thread on a loopback port for
the length of one test. A driver that reaches the network is not a reason to leave it unheld; it
is a reason to give it something to reach.
"""
from __future__ import annotations

import datetime as dt
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.adapters.token_verifier.hs256 import HS256Verifier
from app.adapters.token_verifier.jwks import JWKSVerifier
from app.adapters.token_verifier.rs256 import RS256Verifier
from app.ports.errors import InvalidToken

HS_SECRET = "s" * 40
OTHER_HS_SECRET = "w" * 40
ISS = "test-issuer"
AUD = "test-aud"
KID = "contract-key"


def _claims(**over):
    now = dt.datetime.now(dt.timezone.utc)
    base = {"sub": "user-1", "iss": ISS, "aud": AUD,
            "exp": now + dt.timedelta(minutes=5), "iat": now}
    base.update(over)
    return base


def _rsa():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(serialization.Encoding.PEM,
                             serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()).decode()
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return key, priv, pub


class _Driver:
    """One driver, plus the two things a test needs of it: a verifier, and a way to mint."""

    def __init__(self, verifier, sign, forge):
        self.verifier = verifier
        self.sign = sign          # a token this verifier should accept the signature of
        self.forge = forge        # a well-formed token signed by somebody else


@pytest.fixture
def hs256():
    return _Driver(
        HS256Verifier(HS_SECRET, ISS, AUD),
        lambda claims: jwt.encode(claims, HS_SECRET, algorithm="HS256"),
        lambda claims: jwt.encode(claims, OTHER_HS_SECRET, algorithm="HS256"),
    )


@pytest.fixture
def rs256():
    _, priv, pub = _rsa()
    _, other_priv, _ = _rsa()
    return _Driver(
        RS256Verifier(pub, ISS, AUD),
        lambda claims: jwt.encode(claims, priv, algorithm="RS256"),
        lambda claims: jwt.encode(claims, other_priv, algorithm="RS256"),
    )


@pytest.fixture
def jwks():
    key, priv, _ = _rsa()
    _, other_priv, _ = _rsa()
    entry = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    entry.update({"kid": KID, "use": "sig", "alg": "RS256"})
    body = json.dumps({"keys": [entry]}).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 — the name http.server requires
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            # A CONTRACT RUN MUST NOT WRITE TO stderr. Otherwise every jwks test prints an access
            # line, and a real warning in the same run is lost in it.
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/jwks.json"
    try:
        yield _Driver(
            JWKSVerifier(url, ISS, AUD),
            lambda claims: jwt.encode(claims, priv, algorithm="RS256",
                                      headers={"kid": KID}),
            lambda claims: jwt.encode(claims, other_priv, algorithm="RS256",
                                      headers={"kid": KID}),
        )
    finally:
        server.shutdown()
        server.server_close()


#: THE NAMES ARE THE REGISTRY'S NAMES. `null` is absent on purpose: it verifies nothing by design
#: and production refuses it at boot.
_PARAMS = [
    pytest.param("hs256", id="hs256"),
    pytest.param("rs256", id="rs256"),
    pytest.param("jwks", id="jwks"),
]


@pytest.fixture
def driver(request):
    return request.getfixturevalue(request.param)


@pytest.mark.parametrize("driver", _PARAMS, indirect=True)
class TestEveryTokenVerifier:
    def test_a_token_it_issued_is_accepted(self, driver):
        claims = driver.verifier.verify(driver.sign(_claims()))
        assert claims["sub"] == "user-1"

    def test_an_expired_token_is_refused(self, driver):
        past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
        with pytest.raises(InvalidToken):
            driver.verifier.verify(driver.sign(_claims(exp=past)))

    def test_a_token_with_no_expiry_is_refused(self, driver):
        # A TOKEN THAT NEVER DIES IS A PASSWORD SOMEBODY WROTE DOWN. Every driver requires `exp`.
        claims = _claims()
        claims.pop("exp")
        with pytest.raises(InvalidToken):
            driver.verifier.verify(driver.sign(claims))

    def test_a_signature_from_somebody_else_is_refused(self, driver):
        with pytest.raises(InvalidToken):
            driver.verifier.verify(driver.forge(_claims()))

    def test_another_issuer_is_refused(self, driver):
        # THE REASON `iss` IS CHECKED AT ALL: a token minted by a different system, with a key it
        # legitimately holds, must not open this door.
        with pytest.raises(InvalidToken):
            driver.verifier.verify(driver.sign(_claims(iss="somebody-else")))

    def test_another_audience_is_refused(self, driver):
        # AND THE REASON `aud` IS: a token this very issuer minted FOR ANOTHER SERVICE is a valid
        # token, correctly signed, that this service must still refuse — otherwise one leaked
        # token is every service at once.
        with pytest.raises(InvalidToken):
            driver.verifier.verify(driver.sign(_claims(aud="another-service")))

    def test_rubbish_is_refused_as_a_token_and_not_as_a_crash(self, driver):
        with pytest.raises(InvalidToken):
            driver.verifier.verify("not-a-token")
