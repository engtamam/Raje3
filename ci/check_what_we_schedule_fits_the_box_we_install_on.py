"""Everything this deployment schedules must fit the smallest node we install on — with a roll.

WHAT THIS WAS WRITTEN AFTER. A read of the live cluster found sixteen pods in a terminal state and
a node whose 4 vCPU were 5180m spoken for. `console`, `edge`, `campaigns` and `identity-service`
had all died with `OutOfcpu`: the scheduler could not place the new pod, so the OLD one kept
serving. Every deploy reported success, the release moved, and the screen did not change — which is
the hardest failure to read, because nothing is broken anywhere except arithmetic.

NOTHING IN THE REPOSITORY SAID HOW BIG THE BOX IS. Twenty-one values files each name a modest
request, no file names the total, and no file names the machine. So the sum could grow past the
node one service at a time with every individual change looking reasonable.

AND THE ROLL IS THE PEAK, NOT THE STEADY STATE. A rolling update runs the new pod BESIDE the old
one, so the moment that matters is `total + the largest single service`, not `total`. A fleet that
fits exactly cannot deploy at all: it is full precisely when it needs one more slot.

WHAT THIS CANNOT SEE, said plainly: pods the cluster is holding that this repository never
declared — terminal pods whose reservations the scheduler still counts, finished jobs, anything
installed by hand. Only `deploy/verify-fleet.sh` against the live node can answer that, and it is
what found this in the first place. This gate answers the half that IS ours: what we ask for.

    python ci/check_what_we_schedule_fits_the_box_we_install_on.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: THE SMALLEST NODE WE INSTALL ON, in millicores. This is a fact about the machine Tamam buys, so
#: it is written here once rather than inferred — and raising it is a decision about hardware, not
#: a way to make this check pass. The pilot box is 4 vCPU.
NODE_MILLICORES = 4000

#: k3s itself, containerd, the kubelet and coredns are not in any of our files and are not free.
#: Measured on the pilot node rather than guessed.
SYSTEM_RESERVE = 500

WHERE = (
    ("deploy/services/*.values.yaml", "our services"),
    ("deploy/edge/*.yaml", "the console and the edge"),
    ("platform/deploy/k3s/**/*.yaml", "the platform's datastores"),
)

REPLICAS = re.compile(r'^\s*replicas:\s*(\d+)', re.M)
INLINE = re.compile(r'^(\s*)requests:\s*(\{.*\})?\s*$')
FLOW_CPU = re.compile(r'cpu:\s*([^,}\s]+)')
BLOCK_CPU = re.compile(r'\s*cpu:\s*([^\s#]+)')


def cpu_requests(text: str) -> list[str]:
    """Every cpu request in a manifest, read the way YAML reads it — over comments.

    A REGEX THAT LOOKED FOR `requests:` FOLLOWED BY `cpu:` MISSED THREE FILES, and they were not
    unusual ones: `operations`, `campaigns` and `reminders` each explain their number in a comment
    between the two lines, which is exactly what a values file SHOULD do. 450m went uncounted, and
    the gate reported headroom it had not measured — the same defect it exists to catch, in the
    gate itself. So the block is walked by indentation and comments are skipped, because that is
    what the parser the cluster uses does.
    """
    found: list[str] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        head = INLINE.match(line)
        if not head:
            continue
        if head.group(2):                                   # requests: { cpu: 100m, memory: … }
            flow = FLOW_CPU.search(head.group(2))
            if flow:
                found.append(flow.group(1))
            continue
        indent = len(head.group(1))
        for following in lines[index + 1:]:
            if not following.strip():
                continue
            if len(following) - len(following.lstrip()) <= indent:
                break                                        # the block ended without a cpu
            if following.lstrip().startswith("#"):
                continue
            block = BLOCK_CPU.match(following)
            if block:
                found.append(block.group(1))
                break
    return found


def millicores(raw: str) -> int:
    value = raw.strip().strip('",')
    return int(value[:-1]) if value.endswith("m") else int(float(value) * 1000)


def weigh(pattern: str) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    for path in sorted(ROOT.glob(pattern)):
        text = path.read_text(encoding="utf-8", errors="ignore")
        replicas = REPLICAS.search(text)
        count = int(replicas.group(1)) if replicas else 1
        asked = sum(millicores(raw) for raw in cpu_requests(text))
        if asked:
            found.append((path.stem, asked * count))
    return found


def main() -> int:
    total, largest, largest_name, groups = 0, 0, "", []
    for pattern, label in WHERE:
        weighed = weigh(pattern)
        subtotal = sum(w for _, w in weighed)
        groups.append((label, len(weighed), subtotal))
        total += subtotal
        for name, weight in weighed:
            if weight > largest:
                largest, largest_name = weight, name

    if not total:
        print("FAIL: no cpu request found anywhere — this gate read nothing, "
              "and silence is not agreement")
        return 1

    peak = total + largest          # a rolling update runs the new pod beside the old
    budget = NODE_MILLICORES - SYSTEM_RESERVE
    for label, count, subtotal in groups:
        print(f"  {label:28} {count:3} workload(s)  {subtotal:5}m")
    print(f"  {'steady state':28} {'':3}               {total:5}m")
    print(f"  {'peak during a roll':28} {'':3}               {peak:5}m "
          f"(+{largest}m for {largest_name}, which runs twice)")
    print(f"  {'the box, less the system':28} {'':3}               {budget:5}m")

    if peak > budget:
        print(f"\nFAIL: a roll needs {peak}m and the node has {budget}m to give. The new pod cannot "
              f"be placed, so the OLD one keeps serving and the deploy reports success anyway.")
        print("Cut a request, or install on a bigger node and raise NODE_MILLICORES here — "
              "do not exempt a service.")
        return 1
    print(f"\nOK: a roll fits with {budget - peak}m to spare")
    return 0


if __name__ == "__main__":
    sys.exit(main())
