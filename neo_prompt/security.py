"""Loopback-only origin and short-lived session/CSRF protection for local UI.

Not intended as a multi-user network authentication system.
"""
from __future__ import annotations

import secrets
import time
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse

SESSIONS: dict[str, tuple[str, float]] = {}
TTL_SECONDS = 6 * 3600
COOKIE = "neo_prompt_local_session"


def bootstrap_session(request: Request, response) -> str:
    now = time.monotonic()
    for session, (_, created) in list(SESSIONS.items()):
        if now - created > TTL_SECONDS:
            SESSIONS.pop(session, None)
    cookie = request.cookies.get(COOKIE)
    if cookie and cookie in SESSIONS:
        return SESSIONS[cookie][0]
    if len(SESSIONS) >= 256:
        SESSIONS.pop(next(iter(SESSIONS)))
    session = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    SESSIONS[session] = (csrf, now)
    response.set_cookie(COOKIE, session, httponly=True, samesite="strict", secure=False, max_age=TTL_SECONDS, path="/")
    return csrf


def valid_host(host: str) -> bool:
    try:
        parts = urlsplit("http://" + host)
        return parts.hostname in ("127.0.0.1", "localhost", "::1") and not parts.username
    except ValueError:
        return False


async def local_guard(request: Request, call_next):
    if not valid_host(request.headers.get("host", "")):
        return JSONResponse({"detail": "Neo Prompt serves loopback only"}, status_code=403)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin:
            try:
                parts = urlsplit(origin)
                approved = parts.scheme == "http" and parts.netloc == request.headers.get("host") and not parts.path and not parts.query and not parts.fragment
            except ValueError:
                approved = False
            if not approved:
                return JSONResponse({"detail": "Cross-origin request denied"}, status_code=403)
        current = SESSIONS.get(request.cookies.get(COOKIE, ""))
        if not current or time.monotonic() - current[1] > TTL_SECONDS or not secrets.compare_digest(request.headers.get("x-neo-csrf", ""), current[0]):
            return JSONResponse({"detail": "Refresh the page to establish a local session"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    return response
