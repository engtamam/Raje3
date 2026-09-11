"""What a file's own FIRST BYTES say it is — never what the uploading client claims in a header.

affiliate-service-010 (QA audit, 2026-09-12): `upload_receipt` trusted `file.content_type` (a
header the client sets, not a fact about the bytes) both to validate against the whitelist AND to
store as `receipt_content_type`, which `download_receipt` later echoes back verbatim as the
response's own `media_type` — an admin could upload bytes that are not really a PDF/image with
`content_type: application/pdf` and have them served back with that same trusted-looking type,
inline, with no `Content-Disposition`.

FOUR CANDIDATES, FOUR FIXED-LENGTH PREFIXES — `AFFILIATE_RECEIPT_CONTENT_TYPES` never grows past
what a bank transfer confirmation actually is (a photo or a PDF), so this is a handful of byte
comparisons against the start of the buffer, not a general-purpose format detector. `bytes.startswith`
is a single C-level memcmp per candidate — checking all four costs nothing next to the network
read that already happened to get the bytes here.
"""
from __future__ import annotations

# Each signature paired with the MIME type this service actually whitelists for it
# (AFFILIATE_RECEIPT_CONTENT_TYPES) — WEBP's is checked separately below, since RIFF containers
# carry a second marker eight bytes in, not a single contiguous prefix.
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"%PDF-", "application/pdf"),
)


def sniff_content_type(data: bytes) -> str | None:
    """The MIME type these bytes actually look like, or `None` if they match none of the four
    types this service ever accepts a receipt as. Pure, no I/O — a handful of prefix comparisons."""
    for signature, mime in _SIGNATURES:
        if data.startswith(signature):
            return mime
    # WEBP: "RIFF" (bytes 0-3), then a 4-byte little-endian chunk size (bytes 4-7, not checked —
    # it varies with file size), then "WEBP" (bytes 8-11).
    if len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None
