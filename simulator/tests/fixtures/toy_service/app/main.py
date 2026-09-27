"""A minimal, real FastAPI app — used ONLY by stage 4's own tests to prove `run_service` genuinely
spawns a real process, waits for real health, and tears it down, WITHOUT depending on any of this
project's real services (which need a full env of secrets/config to boot). Stage 5 is where a
real project service (services/referrals or services/operations) gets wired in for real.
"""
from __future__ import annotations

import os

from fastapi import FastAPI

app = FastAPI()


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/echo")
async def echo() -> dict:
    return {"pid": os.getpid()}


@app.post("/tenants/{tenant}/widgets")
async def create_widget(tenant: str) -> dict:
    """Just enough of a real endpoint for stage 4's BlastRadius tests to name a real tenant
    against a real HTTP response, without inventing a whole fake domain."""
    return {"tenant": tenant, "created": True}
