"""What a file's own bytes say it is — see file_sniff.py's own module docstring
(affiliate-service-010, QA audit 2026-09-12)."""
from __future__ import annotations

from app.core.file_sniff import sniff_content_type


def test_a_jpeg_signature_is_recognised():
    assert sniff_content_type(b"\xff\xd8\xff\xe0rest-of-a-jpeg") == "image/jpeg"


def test_a_png_signature_is_recognised():
    assert sniff_content_type(b"\x89PNG\r\n\x1a\nrest") == "image/png"


def test_a_pdf_signature_is_recognised():
    assert sniff_content_type(b"%PDF-1.7\n...") == "application/pdf"


def test_a_webp_signature_is_recognised():
    assert sniff_content_type(b"RIFF\x00\x00\x00\x00WEBPVP8 ...") == "image/webp"


def test_plain_text_matches_nothing():
    assert sniff_content_type(b"hello, this is not a real file") is None


def test_an_empty_buffer_matches_nothing():
    assert sniff_content_type(b"") is None


def test_a_riff_container_that_is_not_webp_matches_nothing():
    """RIFF alone is not enough — AVI and WAV are RIFF containers too, and neither is a receipt
    format this service accepts."""
    assert sniff_content_type(b"RIFF\x00\x00\x00\x00AVI LIST...") is None


def test_a_truncated_riff_header_does_not_crash():
    assert sniff_content_type(b"RIFF") is None
