"""A path is not a link. A customer reading WhatsApp cannot tap `/p/abc123`.

WHAT THIS FOUND. The customer's page is built, served and reachable at `/p/{ref}`. The consent
module states the legal requirement in its own words — «WITHDRAWAL IS AS EASY AS GRANTING… It is
already one tap at `/p/{ref}/stop`» — and every screen, route and renderer behind that sentence
exists.

Nothing anywhere composes the URL. Not one line in any of the six services turns `/p/{ref}` into
`https://<host>/p/{ref}`; there was no setting naming our public address, and no fill source a
template could use to carry one. So the page a shop's whole retention story depends on could only
be reached by a customer who already knew the address — and the withdrawal tap that PDPL requires
be as easy as granting was, in practice, unreachable.

That is the shape this gate is named after: a relative path is correct inside the service that
serves it and meaningless the moment it leaves the building. The two look identical in code.

THE RULE, WITH NO EXCEPTIONS TABLE. Outside the portal — which serves these paths and whose own
forms are correctly relative — a `/p/…` literal may appear only in `core/links.py`, the one place
that turns it into an absolute URL. Anywhere else it is a path being handed to somebody who cannot
use it.

WHAT IT CANNOT SEE, said plainly:
  · a link built by string concatenation with no `/p/` literal (`"/" + "p" + "/"`), which nothing
    has a reason to write;
  · a WRONG absolute link — a base URL pointing at the wrong host is a configuration error, and
    `links.py` refusing an empty one is what stands there instead;
  · a customer-facing path other than `/p/`. This gate knows one prefix, and says so.

    python ci/check_a_link_a_customer_taps_is_absolute.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# `/p/` as a literal inside a string, however the string is quoted or f-formatted.
CUSTOMER_PATH = re.compile(r"""['"][^'"]*?/p/""")

# The portal SERVES these paths; its own forms must post relative, and its manifest and action
# catalogue must declare the paths it owns. Scoped by directory, never by a list of allowed lines.
SERVES_THEM = "services/portal/"
# The one composer. It holds the literal because holding it is its job.
THE_COMPOSER = "core/links.py"


def _without_comments(path: pathlib.Path, lines: list[str]) -> list[str]:
    """The same lines with every `#` comment blanked, keeping line numbers exact.

    Tokenized rather than regexed, because a `#` inside a string literal is not a comment and a
    naive split at the first one would blank half of `"/p/{ref}#top"` — hiding the very thing this
    gate is looking for. If the file cannot be tokenized it is returned untouched: a parse failure
    must make this gate stricter, never quieter.
    """
    import io
    import tokenize

    out = list(lines)
    try:
        for tok in tokenize.generate_tokens(io.StringIO("\n".join(lines) + "\n").readline):
            if tok.type != tokenize.COMMENT:
                continue
            row, col = tok.start[0] - 1, tok.start[1]
            if 0 <= row < len(out):
                out[row] = out[row][:col]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return list(lines)
    return out


def main() -> int:
    bad: list[str] = []
    composers = 0

    for path in sorted(ROOT.glob("services/*/app/**/*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(SERVES_THEM):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            bad.append(f"{rel}: cannot read it — {exc}")
            continue
        # STRINGS, NOT PROSE. The rule is about a path that TRAVELS — into a message, a response, a
        # template. A comment describing the shape of a URL reaches nobody's phone, and failing on
        # one would teach the next reader to stop explaining what the code does. So comments are
        # tokenized away rather than matched: the SCOPE narrows to code, the PATTERN does not
        # narrow at all.
        code = _without_comments(path, lines)
        for i, line in enumerate(code):
            if not CUSTOMER_PATH.search(line):
                continue
            if rel.endswith(THE_COMPOSER):
                composers += 1
                continue
            bad.append(f"{rel}:{i + 1}: a bare /p/ path outside {THE_COMPOSER} — a customer "
                       f"reading this in WhatsApp has nothing to tap")

    # SILENCE IS NOT AGREEMENT. If links.py were deleted or renamed, every service would be clean
    # by virtue of composing no link at all — which is the exact state this gate was written about.
    if composers == 0:
        print(f"FAIL: no {THE_COMPOSER} holds the customer path — either it was removed, or the "
              f"link is being built somewhere this gate cannot see. Both are the defect.")
        return 1

    if bad:
        print(f"FAIL: {len(bad)} customer path(s) that are not links")
        for line in bad:
            print("  " + line)
        return 1
    print(f"OK: every customer-facing /p/ path is composed in {THE_COMPOSER}, which makes it "
          f"absolute or refuses")
    return 0


if __name__ == "__main__":
    sys.exit(main())
