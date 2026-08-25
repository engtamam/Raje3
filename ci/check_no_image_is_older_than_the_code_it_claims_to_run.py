"""Every pinned image must record the commit it was built from, and that commit must be current.

WHAT THIS WAS WRITTEN AFTER, AND IT IS THE QUIETEST FAILURE THIS REPOSITORY HAS PRODUCED. The
console was opened and found none of the work: no branch switcher, none of the rewritten sentences,
nothing. And every tool we own said green. `verify-fleet.sh` compares the repository against the
cluster and reported them IDENTICAL — which was true. Both were weeks behind `apps/console`.

A shipment had built the console, pushed it, and been interrupted before the roll. Reading that as
«it did not happen», the pin was restored to the older digest. From then on the two things we
compare agreed with each other perfectly, and neither was compared to the source. There is no
drift to detect when both sides are equally stale.

SO THE THIRD SIDE OF THE TRIANGLE IS CHECKED HERE: repository ↔ cluster is `verify-fleet.sh`;
declaration ↔ image is the digest; and SOURCE ↔ IMAGE is this gate. A service whose code changed
after its image was built is shipping something nobody wrote today, and it will pass every other
check we have.

THE RECORD IS THE COMMIT BESIDE THE DIGEST. `publish-images.sh` writes `# <sha>, published by
publish-images.sh` next to every digest it pins, so the build is self-describing. This gate reads
that sha and asks git one question: has anything under the service's own source tree changed since?

AND A PIN WITHOUT A RECORDED COMMIT FAILS. `deploy/edge/console.yaml` had none — the one place
where this defect actually bit, and the one place that could not have been caught, because a
missing record is indistinguishable from a fresh build to a reader who accepts silence. It is
written down now, and its absence is a failure rather than a shrug.

    python ci/check_no_image_is_older_than_the_code_it_claims_to_run.py
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: declaration file -> the source tree whose changes make its image stale.
WATCHED = {
    "deploy/services/operations.values.yaml": "services/operations",
    "deploy/services/reminders.values.yaml": "services/reminders",
    "deploy/services/campaigns.values.yaml": "services/campaigns",
    "deploy/services/insights.values.yaml": "services/insights",
    "deploy/services/loyalty.values.yaml": "services/loyalty",
    "deploy/services/portal.values.yaml": "services/portal",
    "deploy/edge/console.yaml": "apps/console",
}

#: What `publish-images.sh` writes beside every digest it pins.
BUILT_AT = re.compile(r'#\s*([0-9a-f]{7,40}),\s*published by publish-images\.sh')


def git(*args: str) -> str:
    done = subprocess.run(("git", *args), cwd=ROOT, capture_output=True, text=True)
    return done.stdout.strip()


def main() -> int:
    if not (ROOT / ".git").exists():
        print("FAIL: no git history here — this gate cannot ask when anything was built")
        return 1

    unrecorded, stale, checked = [], [], 0
    for declaration, source in sorted(WATCHED.items()):
        path = ROOT / declaration
        if not path.is_file():
            print(f"FAIL: {declaration} is missing — this gate is pointed at a file that moved")
            return 1
        match = BUILT_AT.search(path.read_text(encoding="utf-8"))
        if not match:
            unrecorded.append((declaration, source))
            continue
        built = match.group(1)
        # An unknown sha is not «current»: a record we cannot resolve proves nothing at all.
        if not git("cat-file", "-t", built):
            unrecorded.append((declaration, f"{source} (records {built}, which is not in history)"))
            continue
        since = [line for line in git("log", "--oneline", f"{built}..HEAD", "--", source).splitlines()
                 if line.strip()]
        checked += 1
        if since:
            stale.append((source, built, since))

    if not checked and not unrecorded:
        print("FAIL: nothing was compared — this gate read no declaration at all")
        return 1

    for declaration, source in unrecorded:
        print(f"FAIL: {declaration} pins an image with no build commit recorded — nothing can tell "
              f"whether it carries today's {source} or last month's")
    for source, built, since in stale:
        print(f"FAIL: {source} has changed {len(since)} time(s) since its image was built at {built}")
        for line in since[:3]:
            print(f"       {line}")
        if len(since) > 3:
            print(f"       … and {len(since) - 3} more")
    if unrecorded or stale:
        print("\nRebuild and ship the service, or explain in its own file why the source moved "
              "without the image needing to — do not exempt it here.")
        return 1

    print(f"{checked} pinned image(s): every one built from the source as it stands")
    return 0


if __name__ == "__main__":
    sys.exit(main())
