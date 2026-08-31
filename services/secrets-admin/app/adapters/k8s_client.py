"""The Kubernetes API server, spoken to directly — two PATCHes and nothing else.

NO `kubernetes` PACKAGE, AND NO SHELLING OUT TO kubectl.

The official client is a large dependency with its own transport, its own config loading and its
own release cadence, imported to make two merge-patch calls whose bodies fit on a screen. Shelling
out to kubectl is worse: it needs a binary in the image, it authenticates by a different path than
the one the pod was given, and its failures arrive as text on a stream rather than as a status code
anything can branch on. So this is stdlib urllib, exactly like the audit sink and every other
internal client here.

WHAT MAKES IT TESTABLE WITHOUT A CLUSTER. `Transport` is the seam. `K8sClient` composes the URL,
the headers and the JSON body and hands them over; `UrllibTransport` is the only thing that touches
a socket. There is no cluster to point at from a laptop, so the tests assert the exact method, path,
content-type and body this WOULD send — which is the part that can be wrong. What they cannot
prove is that a real API server accepts it; that is verified once, by hand, against the cluster
(see the values file for the exact command), and this docstring says so rather than letting a green
suite imply it.

THE TOKEN IS READ AT CALL TIME, NEVER CACHED. A projected ServiceAccount token expires — kubelet
rewrites the file roughly hourly — so a client that read it once at boot works perfectly for an
hour and then 401s forever, which is exactly the kind of failure that survives every test and
appears three weeks into production.

THE FAILURE MODE IS A NAMED EXCEPTION, NOT `None`. A caller cannot tell "the secret has no such
key" from "the apiserver refused us" out of a falsy return, and those two need different sentences
in front of the person waiting.
"""
from __future__ import annotations

import base64
import json
import ssl
import urllib.error
import urllib.request
from typing import Any, Protocol


class K8sError(RuntimeError):
    """The API server refused, or could not be reached. Carries the status when there was one."""

    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


class Transport(Protocol):
    """One HTTP request. The whole seam between this adapter and a socket."""

    def request(self, method: str, url: str, *, headers: dict[str, str],
                body: bytes | None) -> tuple[int, bytes]:
        ...


class UrllibTransport:
    """stdlib HTTPS, verifying against the cluster's own CA bundle.

    THE CA IS THE POD'S, NOT THE SYSTEM'S. The API server presents a certificate signed by the
    cluster CA, which no public trust store knows — so verification against the default context
    fails, and the tempting fix (`ssl._create_unverified_context`) would turn every patch into an
    unauthenticated write to whoever answered first on that address. The CA is mounted beside the
    token for precisely this reason.
    """

    def __init__(self, ca_file: str, timeout: int = 10) -> None:
        self._ca_file = ca_file
        self._timeout = timeout
        self._ctx: ssl.SSLContext | None = None

    def _context(self) -> ssl.SSLContext:
        if self._ctx is None:
            # Built once and reused: loading a CA bundle per request is measurable, and the file
            # does not change under a running pod (unlike the token beside it, which does).
            self._ctx = ssl.create_default_context(cafile=self._ca_file)
        return self._ctx

    def request(self, method: str, url: str, *, headers: dict[str, str],
                body: bytes | None) -> tuple[int, bytes]:
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout,  # nosec B310 - https, config-only host
                                        context=self._context()) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            # NOT AN EXCEPTION AT THIS LAYER. A 404 and a 403 are ANSWERS, and the client above
            # turns each into its own sentence; raising here would collapse them into "unreachable".
            return exc.code, exc.read()
        except (urllib.error.URLError, OSError, ssl.SSLError) as exc:
            raise K8sError(f"the cluster API server is unreachable: {exc}") from exc


class K8sClient:
    """Patch a Secret, and roll the Deployment that reads it."""

    #: The content type for a strategic-free, additive patch. `application/json-patch+json` would
    #: need the exact index/path to already exist, and a plain PUT would REPLACE the object —
    #: dropping every other key in the Secret and every annotation somebody else wrote on it.
    MERGE_PATCH = "application/merge-patch+json"

    def __init__(self, transport: Transport, *, host: str, port: str, token_file: str) -> None:
        self._transport = transport
        self._host = host
        self._port = port
        self._token_file = token_file

    # ── the wire ──────────────────────────────────────────────────────────────────────────────
    def _token(self) -> str:
        try:
            with open(self._token_file, encoding="utf-8") as fh:
                return fh.read().strip()
        except OSError as exc:
            raise K8sError(
                f"no ServiceAccount token at {self._token_file} — the pod was not given one, so "
                f"every write would be refused 401") from exc

    def _base(self) -> str:
        if not self._host:
            raise K8sError("no KUBERNETES_SERVICE_HOST — this is not running inside a cluster")
        return f"https://{self._host}:{self._port}"

    def _patch(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        raw = json.dumps(body).encode()
        status, payload = self._transport.request(
            "PATCH", f"{self._base()}{path}",
            headers={"Authorization": f"Bearer {self._token()}",
                     "Content-Type": self.MERGE_PATCH,
                     "Accept": "application/json"},
            body=raw)
        if status == 403:
            raise K8sError(
                "the cluster refused this write — the ServiceAccount's Role does not cover this "
                "object", status)
        if status == 404:
            raise K8sError("the cluster has no such object", status)
        if not 200 <= status < 300:
            raise K8sError(f"the cluster API server answered HTTP {status}", status)
        try:
            return json.loads(payload or b"{}")
        except ValueError as exc:
            # A 200 with a body we cannot read proves nothing about what was written.
            raise K8sError(f"HTTP {status} with an unreadable body", status) from exc

    # ── what this service actually does ───────────────────────────────────────────────────────
    def patch_secret(self, namespace: str, name: str, *, data: dict[str, str],
                     annotations: dict[str, str]) -> dict[str, Any]:
        """Write one key's value AND its three annotations, in ONE request.

        ONE REQUEST BECAUSE TWO CAN HALF-FAIL. Writing the value and then the annotations means a
        window — and, if the second call fails, a permanent state — where the live secret is the
        new one and the screen still shows the old `last4` and the previous person's name. The
        screen would then be lying about a credential, which is the single thing this service must
        never do.

        VALUES ARE BASE64, WHICH IS THE `data` FIELD'S CONTRACT (`stringData` exists and is
        write-only sugar the API server converts; using `data` keeps what we send identical to what
        is stored, so the test can assert one thing rather than two).
        """
        encoded = {k: base64.b64encode(v.encode()).decode() for k, v in data.items()}
        return self._patch(f"/api/v1/namespaces/{namespace}/secrets/{name}",
                           {"data": encoded, "metadata": {"annotations": annotations}})

    def restart_deployment(self, namespace: str, name: str, *, at: str) -> dict[str, Any]:
        """Roll the pods, the way `kubectl rollout restart` does — by touching the pod template.

        THERE IS NO "RESTART" VERB IN THE KUBERNETES API. What kubectl does is write a timestamp
        annotation into `spec.template.metadata.annotations`, which changes the pod template hash,
        which makes the Deployment controller perform an ordinary rolling update. We write the same
        annotation under the same name, so a person reading `kubectl describe` sees the field they
        expect rather than a private one of ours they have to go and look up.
        """
        return self._patch(
            f"/apis/apps/v1/namespaces/{namespace}/deployments/{name}",
            {"spec": {"template": {"metadata": {"annotations": {
                "kubectl.kubernetes.io/restartedAt": at}}}}})

    def read_secret_annotations(self, namespace: str, name: str) -> dict[str, str]:
        """The annotations, and NOTHING ELSE — the `data` field is never even looked at.

        THIS IS THE WHOLE READ PATH OF THIS SERVICE, and it is shaped so that returning a real
        secret value is not a bug that could be introduced later — it is not reachable from here.
        The GET route calls this; there is no method on this client that returns a decoded value,
        and adding one would be a visible, reviewable change rather than a typo in a dict
        comprehension.

        `?` A FIELD SELECTOR WOULD BE NICER and the API server does not support one for this. So
        the response does carry `data` over the wire; what matters is that it is discarded here,
        one layer below every caller, rather than trusted to be filtered by each of them.
        """
        status, payload = self._transport.request(
            "GET", f"{self._base()}/api/v1/namespaces/{namespace}/secrets/{name}",
            headers={"Authorization": f"Bearer {self._token()}", "Accept": "application/json"},
            body=None)
        if status == 404:
            # NOT AN ERROR TO THE CALLER. A Secret object that does not exist yet is the honest
            # state of a fresh cluster before anything was ever configured, and the screen's answer
            # for it is «غير مُعدّ» rather than a red banner.
            return {}
        if not 200 <= status < 300:
            raise K8sError(f"the cluster API server answered HTTP {status}", status)
        try:
            obj = json.loads(payload or b"{}")
        except ValueError as exc:
            raise K8sError(f"HTTP {status} with an unreadable body", status) from exc
        meta = obj.get("metadata") or {}
        anns = meta.get("annotations") or {}
        return {str(k): str(v) for k, v in anns.items()}
