"""A values file that cannot render is a failed deploy discovered on the cluster.

WHAT HAPPENED. `BACKUP_EXEMPT` was written at the ROOT of `backup-service.values.yaml` instead of
under `env:`. The chart's schema is `additionalProperties: false` at every level — deliberately, so
a mistyped key is a render ERROR rather than a silent no-op — so that one line made the release
unrenderable. `install.sh` rolls services in order and stops on the first failure: four of
twenty-four had been upgraded, the other twenty kept their old images, and the cluster was left
half-deployed. The line that explained it appeared after four green successes.

AND THE GUARD ALREADY EXISTED — in `.github/workflows/guards.yml`, which runs `helm template` over
every values file. It did not run. That is the whole finding: the check was written, was correct,
and lived only where nothing was executing it. A guard that runs in one place and not the other is
a guard with a hole the shape of that other place.

So it lives here too, beside the seventy-five gates that run before every commit. `helm` is on the
machine; nothing about this needed a runner.

NOT A DUPLICATE OF THE CI STEP, AND BOTH STAY. CI protects the branch from a pull request; this
protects the SHIPMENT from a working tree — and the shipment is the one that touches a cluster.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
VALUES = ROOT / "deploy" / "services"
CHART = ROOT / "platform" / "deploy" / "chart"


def main() -> int:
    helm = shutil.which("helm")
    if helm is None:
        # A GATE THAT CANNOT RUN MUST SAY SO, LOUDLY. Passing here would report «every values file
        # renders» on a machine that rendered none — which is exactly the shape of the failure
        # this gate exists to prevent.
        print("helm is not on PATH — this gate cannot answer, so it refuses to")
        return 1
    if not CHART.is_dir():
        print(f"no chart at {CHART.relative_to(ROOT).as_posix()} — the submodule is not checked out")
        return 1

    files = sorted(VALUES.glob("*.values.yaml"))
    if not files:
        # SILENCE IS NOT AGREEMENT: rendering nothing is not the same as rendering everything.
        print("no values files found — this gate needs re-pointing")
        return 1

    bad: list[tuple[str, str]] = []
    for f in files:
        name = f.name[: -len(".values.yaml")]
        out = subprocess.run([helm, "template", name, str(CHART), "-f", str(f)],
                             capture_output=True, text=True)
        if out.returncode != 0:
            bad.append((f"deploy/services/{f.name}", (out.stderr or "").strip()[:400]))

    if bad:
        print(f"{len(bad)} values file(s) do not render against the chart:")
        for path, err in bad:
            print(f"  {path}")
            for line in err.splitlines():
                print(f"      {line}")
        print("\nThe installer stops at the first of these, leaving the fleet half-deployed.")
        return 1
    print(f"{len(files)} values files: every one renders against the chart")
    return 0


if __name__ == "__main__":
    sys.exit(main())
