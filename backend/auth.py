"""Supabase JWT verification dependency."""
import os
import httpx
from fastapi import Header, HTTPException

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://bncjthibzexlzdryxjdk.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "sb_publishable_yR-U8N_HS25ILJEMwaIHAg_IDIOtlLa")
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "true").lower() == "true"
SUPER_ADMIN_EMAILS = {e.strip().lower() for e in os.getenv("SUPER_ADMIN_EMAILS", "").split(",") if e.strip()}


async def get_current_user(authorization: str = Header(default=None)) -> dict:
    """
    Verify the Supabase JWT in the Authorization header.
    Returns the Supabase user dict on success.
    Raises 401 if auth is required and the token is missing or invalid.
    """
    if not REQUIRE_AUTH:
        return {"id": "local", "email": "local@dev"}

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.split(" ", 1)[1]

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": SUPABASE_ANON_KEY,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    user = resp.json()
    user["is_super_admin"] = user.get("email", "").lower() in SUPER_ADMIN_EMAILS
    return user
