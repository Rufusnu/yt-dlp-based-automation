from fastapi import HTTPException, Request


def need(request: Request):
    """Login + CSRF check; call first in every /api handler."""
    if not request.session.get("ok"):
        raise HTTPException(401, "login required")
    if request.method != "GET" and request.headers.get("x-requested-with") != "ytw":
        raise HTTPException(403, "bad request")
