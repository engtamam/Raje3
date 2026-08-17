"""Every data store this repository deploys is selected by a NetworkPolicy that denies by default.

WHAT WAS MISSING, AND IT WAS MISSING IN THE DIRECTION THAT MATTERS (أ-3). The fleet carries 48
NetworkPolicies covering the 24 services — a default-deny and an allow for each — and every one of
them selects a SERVICE. Read live from the cluster: not one selects `postgres`, `redis` or
`objectstore`. The model restricted where services may GO. It said nothing about who may ARRIVE
at the data.

So `postgres:5432` and `redis:6379` accepted a connection from anything that could get a packet
into the namespace, and the two pods most able to give an attacker that packet — `edge` and
`console`, both Caddy, both facing the internet — were themselves selected by nothing at all.

WHY A REPOSITORY GATE FOR A CLUSTER FACT. Because the cluster is where you find out, and by then
it is running. The manifests are where the intent lives, and a manifest set that deploys a
database and no policy for it is a decision — usually an unnoticed one — made here first. The live
half is `deploy/check-posture.sh` and `verify-fleet.sh`; this is the half that runs on every push.

THE RULE, AND IT HAS NO EXCEPTIONS TABLE: a workload whose manifest names a data-store image must
be selected by at least one NetworkPolicy in the same repository, and that policy must deny by
default — `policyTypes` naming Ingress with no blanket `ingress` rule that admits everybody.

DISCOVERED BY IMAGE, NOT BY A LIST OF NAMES. `postgres`, `redis`, `seaweedfs` and friends are
recognised from the image they run, so a second cache or a new store added next month is in scope
the day its manifest lands — with no list here to remember to extend, which is the failure mode
this repository has already paid for in `KNOWN` sets twice.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy"
#: THE STORES ARE DEPLOYED BY THE PLATFORM, AND THE WALL IS OURS TO BUILD. `postgres`, `redis` and
#: `objectstore` come from `platform/deploy/k3s/` — a read-only submodule we do not edit. A
#: NetworkPolicy is namespace-scoped and needs no change to the workload it protects, so the honest
#: division is: they run the database, we decide who may reach it. This gate therefore LOOKS for
#: stores in both trees and REQUIRES the policy in ours.
PLATFORM = ROOT / "platform" / "deploy"

#: What a data store looks like from its image. Names, not tags — the tag is somebody else's
#: version scheme and changes without the thing changing.
STORE_IMAGES = ("postgres", "redis", "seaweedfs", "minio", "mysql", "mariadb", "mongo",
                "elasticsearch", "opensearch", "clickhouse", "cassandra", "etcd")

#: `app: postgres` / `base-services/role: datastore` — the labels a policy could select it by.
#:
#: `re.M` IS NOT DECORATION HERE. Without it `^` anchors to the start of the whole document rather
#: than each line, so this matched almost nothing and the gate reported three unprotected stores
#: whose policy was sitting right next to it. A pattern that silently matches nothing produces a
#: gate that is confidently wrong — the same shape as the money gate that caught two sites of three.
#: AND A TRAILING COMMENT IS STILL A LABEL. `base-services/role: datastore   # the chart's egress
#: policy selects THIS` is how the platform writes the very label this gate needs, and anchoring
#: hard at `$` skipped it — so the gate reported three unprotected stores while their policy sat
#: next to it. Both of this pattern's bugs were the same kind: it matched nothing and said so
#: confidently.
A_LABEL = re.compile(r"^\s{0,20}([a-zA-Z0-9][\w./-]*):\s*([\w.-]+)\s*(?:#.*)?$", re.M)


def _docs(text: str) -> list[str]:
    return re.split(r"^---\s*$", text, flags=re.M)


def main() -> int:
    if not DEPLOY.is_dir():
        print("no deploy/ directory — this gate cannot answer, so it refuses to")
        return 1

    files = sorted(DEPLOY.rglob("*.yaml")) + sorted(DEPLOY.rglob("*.yml"))
    ours = set(files)
    if PLATFORM.is_dir():
        files += sorted(PLATFORM.rglob("*.yaml")) + sorted(PLATFORM.rglob("*.yml"))
    else:
        # A GATE THAT CANNOT READ HALF ITS SUBJECT MUST SAY SO. Without the submodule the stores
        # are invisible and «no store is unprotected» would be true of nothing.
        print("platform/deploy is missing — the data stores it deploys cannot be seen, so this "
              "gate cannot answer")
        return 1
    if not files:
        # SILENCE IS NOT AGREEMENT.
        print("no manifests under deploy/ — this gate needs re-pointing")
        return 1

    stores: dict[str, str] = {}        # workload name -> the file that deploys it
    selectors: list[tuple[str, str]] = []   # (label key:value selected by a policy, policy name)
    denies: set[str] = set()           # label key:value that some policy denies by default

    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {rel}: {exc} — so it was NOT checked")
            return 1

        for doc in _docs(text):
            if "kind: NetworkPolicy" in doc:
                if path not in ours:
                    continue        # the platform's own policies are not the wall we control
                name = ""
                m = re.search(r"^\s*name:\s*([\w.-]+)", doc, re.M)
                if m:
                    name = m.group(1)
                sel = re.search(r"podSelector:\s*\n((?:\s+.+\n)+?)\s*(?:policyTypes|ingress|egress)",
                                doc)
                if sel:
                    for k, v in A_LABEL.findall(sel.group(1)):
                        if k in ("matchLabels", "matchExpressions"):
                            continue
                        selectors.append((f"{k}:{v}", name))
                        # A DEFAULT-DENY IS A POLICY THAT NAMES Ingress AND ADMITS NOBODY BY
                        # DEFAULT. A policy with an `ingress:` list is an allow; the deny is the
                        # one that has none.
                        if "Ingress" in doc and not re.search(r"^\s*ingress:", doc, re.M):
                            denies.add(f"{k}:{v}")
                continue

            img = re.search(r"^\s*image:\s*[\"']?([^\s\"']+)", doc, re.M)
            if not img:
                continue
            ref = img.group(1)
            if not any(s in ref.split("@")[0].split(":")[0].lower() for s in STORE_IMAGES):
                continue
            nm = re.search(r"^\s*name:\s*([\w.-]+)", doc, re.M)
            labels = dict(A_LABEL.findall(doc))
            key = nm.group(1) if nm else ref
            stores[key] = rel
            # Remember every label this workload carries so a policy can be matched to it.
            stores[key] = rel
            for k, v in labels.items():
                if k in ("name", "image", "kind", "apiVersion", "namespace"):
                    continue
                stores.setdefault(f"@{key}", "")
                selectors_key = f"{k}:{v}"
                stores[f"@{key}"] = (stores[f"@{key}"] + "|" + selectors_key).strip("|")

    if not stores:
        print("no data-store workload found under deploy/ — this gate needs re-pointing")
        return 1

    selected = {s for s, _ in selectors}
    naked: list[str] = []
    open_door: list[str] = []
    for key, rel in sorted(stores.items()):
        if key.startswith("@"):
            continue
        own = set((stores.get(f"@{key}") or "").split("|")) - {""}
        hit = own & selected
        if not hit:
            naked.append(f"{key} ({rel}) — no NetworkPolicy in this repository selects it")
        elif not (own & denies):
            open_door.append(f"{key} ({rel}) — selected by a policy, but none of them denies "
                             f"by default")

    if naked or open_door:
        print(f"{len(naked) + len(open_door)} data store(s) are not behind a default-deny:")
        for line in naked + open_door:
            print("  " + line)
        print("\nEvery service in this fleet has a default-deny and an allow. A store that has")
        print("neither accepts a connection from anything that can put a packet in the namespace —")
        print("and the pods most likely to hand an attacker that packet are the internet-facing")
        print("ones. See deploy/k3s/datastores-netpol.yaml.")
        return 1

    n = len([k for k in stores if not k.startswith("@")])
    print(f"{n} data store(s) under deploy/: every one is selected by a policy that denies by "
          f"default")
    return 0


if __name__ == "__main__":
    sys.exit(main())
