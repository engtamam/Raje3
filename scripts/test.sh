#!/usr/bin/env bash
# Run a service's tests in an environment that looks like the one it ships in.
#
#   ./scripts/test.sh                 every service
#   ./scripts/test.sh reminders       one
#   ./scripts/test.sh reminders -q    extra pytest arguments pass through
#
# WHY THIS EXISTS, AND IT IS NOT CONVENIENCE.
#
# ci/check_licenses.py — which every service ships and which the security suite runs — enumerates
# the packages installed in the INTERPRETER THAT RUNS IT. That is the correct thing for it to do:
# in the image, that set is exactly the service's dependencies.
#
# Run from a developer machine's system Python it enumerates the developer's machine. Ours reported
# six forbidden licences from PyMuPDF, kobo-scan, formulas and docutils — none of them a dependency
# of anything here. One failure, in every service, every run.
#
# A failing test nobody can act on is worse than no test: it teaches the person running it to read
# "1 failed" as normal, and the day it means something they will not notice. So the fix is not to
# weaken the gate, exempt the packages, or skip the test — all of which were available and all of
# which would have removed a real control to fix a fake symptom.
#
# The fix is to stop lying to the scanner about what is installed.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
VENV="$ROOT/.venv-test"

# The dependency set every service in this repo declares, from their pyproject files. httpx is
# added because starlette's TestClient needs it and nothing declares it — a test-only dependency
# of the platform's own template.
DEPS=(fastapi uvicorn pydantic pydantic-settings prometheus-client "pyjwt[crypto]" pytest httpx)

PY="$VENV/Scripts/python.exe"
[ -x "$PY" ] || PY="$VENV/bin/python"

if [ ! -x "$PY" ]; then
  echo "creating $VENV (once)"
  python -m venv "$VENV" || { echo "could not create the venv"; exit 1; }
  PY="$VENV/Scripts/python.exe"; [ -x "$PY" ] || PY="$VENV/bin/python"
  "$PY" -m pip install -q --disable-pip-version-check "${DEPS[@]}" || exit 1
fi

SERVICES=("$@")
EXTRA=()
if [ ${#SERVICES[@]} -eq 0 ]; then
  mapfile -t SERVICES < <(cd "$ROOT/services" && ls -d */ | tr -d /)
else
  # Anything after the first argument that starts with `-` is for pytest, not a service name.
  keep=(); for a in "${SERVICES[@]}"; do
    case "$a" in -*) EXTRA+=("$a") ;; *) keep+=("$a") ;; esac
  done
  SERVICES=("${keep[@]}")
fi

fail=0
for svc in "${SERVICES[@]}"; do
  [ -d "$ROOT/services/$svc" ] || { echo "  ✗ no services/$svc"; fail=1; continue; }
  printf '%-12s ' "$svc"
  (cd "$ROOT/services/$svc" && "$PY" -m pytest -q "${EXTRA[@]}" 2>&1 | tail -1)
  # THE PIPE HIDES THE EXIT CODE, so it is read from PIPESTATUS rather than from the tail.
  [ "${PIPESTATUS[0]:-0}" -eq 0 ] || fail=1
done

exit $fail
