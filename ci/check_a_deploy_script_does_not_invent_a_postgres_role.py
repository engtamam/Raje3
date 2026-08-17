"""A deploy script must read the postgres role, never spell it.

THE SAME DEFECT, FOUND THREE TIMES, FIXED ONCE. `deploy/hooks/pre-deploy.sh` used to provision the
fleet's databases with `psql -U platform`. Postgres has no role called `platform` — it is
`base_services`, minted by gen-secrets and written into every DSN — so every psql and every
createdb failed, `2>/dev/null || true` swallowed all of it, and the next line announced «databases
present». Twenty-four databases that did not exist, reported as provisioned.

That was found and fixed: the hook now READS the role out of the DSN it is going to use. But the
fix landed in the one file where the failure had been noticed, and the same spelling sat untouched
in two other scripts, both of which had been failing silently for exactly as long:

  - `check-posture.sh` asked `-U platform` whether postgres serves TLS. The read returned nothing,
    nothing is not «on», and so the security posture check has reported «postgres does not serve
    TLS» on every run since it was written — including on clusters that do. A permanent red alarm
    is not a check; it is a thing people learn to scroll past.
  - `uninstall.sh` asked `-U postgres` for the number of shops it was about to delete. That role
    does not exist either. The count came back empty, an `-n` test skipped the line, and the one
    number in that prompt meant to make a person stop — «you are about to delete N shops and
    everything they own» — has never once been printed.

WHY THE GATE IS ON THE SPELLING AND NOT THE VALUE. A gate that checked for `platform` specifically
would pass the day somebody writes `postgres` instead, which is the other wrong answer already in
the tree. The defect is not which name was guessed; it is that a name was GUESSED at all when the
DSN in the cluster is the authority and is two `cut`s away. So: a literal after `-U` is the finding,
and a variable is the fix. That is a rule with no exceptions to keep a table of.

SCOPE. `psql` and `createdb` invocations in `deploy/`. Not `platform/` — vendored and read-only.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy"

#: `-U something` on a psql/createdb line. A `$VAR` or `"$VAR"` is the correct form and is not a
#: hit; a bare word is a guess about somebody else's cluster.
CALL = re.compile(r"\b(psql|createdb|dropdb|pg_dump)\b[^\n|;]*?-U\s+(\S+)")
READ = re.compile(r"^[\"']?\$")


def main() -> int:
    if not DEPLOY.is_dir():
        # A GATE THAT CANNOT READ MUST FAIL LOUDLY.
        print("no deploy/ directory — this gate cannot answer, so it refuses to")
        return 1

    files = sorted(DEPLOY.rglob("*.sh"))
    if not files:
        # SILENCE IS NOT AGREEMENT: scanning nothing is not the same as finding nothing.
        print("no deploy scripts found — this gate needs re-pointing")
        return 1

    hits: list[str] = []
    checked = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {f.relative_to(ROOT).as_posix()}: {exc}")
            return 1
        for line_no, line in enumerate(text.splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue
            for tool, role in CALL.findall(line):
                checked += 1
                if READ.match(role):
                    continue
                hits.append(f"{f.relative_to(ROOT).as_posix()}:{line_no}: "
                            f"{tool} -U {role}")

    if hits:
        print(f"{len(hits)} deploy call(s) spell a postgres role instead of reading it:")
        for line in hits:
            print("  " + line)
        print("\nThe role is minted by gen-secrets and lives in every service's DATASTORE_DSN. Read "
              "it the way deploy/hooks/pre-deploy.sh does:")
        print("  PGUSER=$(kubectl -n \"$NS\" get secret tenant-service-secrets \\")
        print("           -o jsonpath='{.data.DATASTORE_DSN}' | base64 -d | cut -d/ -f3 | cut -d: -f1)")
        print("\nA guessed role does not error visibly: the query returns nothing, and nothing "
              "reads as «no TLS», «no shops», «no databases» — never as «I could not ask».")
        return 1
    print(f"{checked} psql/createdb calls in deploy/: every one reads the role rather than "
          f"spelling it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
