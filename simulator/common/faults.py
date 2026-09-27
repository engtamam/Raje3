"""Stage 6 of the simulator's own build plan (see ../README.md): faults — a deliberately broken
dependency, on top of an action that has zero idea it is being tested against one (same
separation principle as stage 3's execution modes: the ACTION never changes, only what it talks
to does).

ONLY THE TRULY GENERIC FAULT LIVES HERE. "A dependency is unreachable" needs no domain knowledge
at all — any service, talking to any peer, can be pointed at a URL nothing is listening on. "A
dependency is slow" or "a dependency returns garbage" needs a real, differently-behaved REAL
service standing in for the real peer — and what shape that peer's own API is (which endpoints, what
a well-formed response looks like) is domain knowledge, so those faults live in
`apps/<name>/faults.py` instead (see `apps/operations/faults.py`'s own fake-referrals-peer).
"""
from __future__ import annotations

import socket


def unreachable_url() -> str:
    """A URL guaranteed to refuse a real TCP connection outright — grab a real, currently-free
    port, then close the socket immediately without anything ever listening on it again. By the
    time a caller connects, nothing is there: a genuine ECONNREFUSED over a real socket, not a
    mock standing in for one."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{s.getsockname()[1]}"
