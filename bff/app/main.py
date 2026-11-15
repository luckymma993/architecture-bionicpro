"""BFF: единственное место, где живут токены Keycloak.

Браузер получает только cookie сессии (httpOnly). Access и refresh токены лежат в Redis.
Вход идёт по Authorization Code + PKCE (S256), code_verifier создаётся и хранится здесь.
"""
import base64
import hashlib
import json
import os
import secrets
import time
from urllib.parse import urlencode

import httpx
import redis
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

# Адрес Keycloak для браузера и адрес для запросов из контейнера
KC_PUBLIC = os.environ["KEYCLOAK_PUBLIC_URL"]
KC_INTERNAL = os.environ["KEYCLOAK_INTERNAL_URL"]
REALM = os.environ.get("KEYCLOAK_REALM", "reports-realm")
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
BFF_PUBLIC_URL = os.environ["BFF_PUBLIC_URL"]
FRONTEND_URL = os.environ["FRONTEND_URL"]
REPORTS_API_URL = os.environ["REPORTS_API_URL"]

COOKIE = "bff_session"
SESSION_TTL = 60 * 60 * 8
LOGIN_TTL = 300

r = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
http = httpx.Client(timeout=10)

app = FastAPI(title="BionicPRO BFF")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def oidc(kind: str, public: bool = False) -> str:
    base = KC_PUBLIC if public else KC_INTERNAL
    return f"{base}/realms/{REALM}/protocol/openid-connect/{kind}"


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def save_tokens(session_id: str, tok: dict, username: str | None = None) -> None:
    key = f"session:{session_id}"
    old = r.get(key)
    data = json.loads(old) if old else {}
    data.update(
        access_token=tok["access_token"],
        refresh_token=tok["refresh_token"],
        expires_at=time.time() + tok["expires_in"],
    )
    if username:
        data["username"] = username
    r.set(key, json.dumps(data), ex=SESSION_TTL)


def load_session(request: Request) -> tuple[str, dict]:
    session_id = request.cookies.get(COOKIE)
    raw = r.get(f"session:{session_id}") if session_id else None
    if not raw:
        raise HTTPException(status_code=401, detail="Требуется аутентификация")
    return session_id, json.loads(raw)


def fresh_access_token(session_id: str, data: dict) -> str:
    """Если access токен скоро истечёт, обновляем его по refresh токену."""
    if data["expires_at"] - time.time() > 30:
        return data["access_token"]
    resp = http.post(
        oidc("token"),
        data={
            "grant_type": "refresh_token",
            "refresh_token": data["refresh_token"],
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )
    if resp.status_code != 200:
        r.delete(f"session:{session_id}")
        raise HTTPException(status_code=401, detail="Сессия истекла, войдите снова")
    tok = resp.json()
    save_tokens(session_id, tok)
    return tok["access_token"]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/auth/login")
def login():
    state = secrets.token_urlsafe(24)
    verifier = b64(os.urandom(32))
    challenge = b64(hashlib.sha256(verifier.encode()).digest())
    r.set(f"login:{state}", verifier, ex=LOGIN_TTL)
    query = urlencode(
        {
            "client_id": CLIENT_ID,
            "response_type": "code",
            "scope": "openid",
            "redirect_uri": f"{BFF_PUBLIC_URL}/auth/callback",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return RedirectResponse(f"{oidc('auth', public=True)}?{query}")


@app.get("/auth/callback")
def callback(code: str = "", state: str = ""):
    verifier = r.getdel(f"login:{state}") if state else None
    if not code or not verifier:
        return RedirectResponse(f"{FRONTEND_URL}/?error=login")
    resp = http.post(
        oidc("token"),
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": f"{BFF_PUBLIC_URL}/auth/callback",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code_verifier": verifier,
        },
    )
    if resp.status_code != 200:
        return RedirectResponse(f"{FRONTEND_URL}/?error=login")
    tok = resp.json()
    # токен получен напрямую от Keycloak по защищённому каналу, поэтому имя берём из его тела
    payload = tok["access_token"].split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    session_id = secrets.token_urlsafe(32)
    save_tokens(session_id, tok, claims.get("preferred_username"))
    out = RedirectResponse(FRONTEND_URL)
    out.set_cookie(
        COOKIE, session_id, httponly=True, samesite="lax", max_age=SESSION_TTL, path="/"
    )
    return out


@app.get("/auth/me")
def me(request: Request):
    try:
        _, data = load_session(request)
    except HTTPException:
        return {"authenticated": False}
    return {"authenticated": True, "username": data.get("username")}


@app.post("/auth/logout")
def logout(request: Request):
    session_id = request.cookies.get(COOKIE)
    raw = r.getdel(f"session:{session_id}") if session_id else None
    if raw:
        # закрываем сессию и в Keycloak
        http.post(
            oidc("logout"),
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": json.loads(raw)["refresh_token"],
            },
        )
    out = JSONResponse({"authenticated": False})
    out.delete_cookie(COOKIE, path="/")
    return out


@app.get("/reports")
def reports(request: Request):
    session_id, data = load_session(request)
    token = fresh_access_token(session_id, data)
    # параметры периода передаём как есть; пользователя определяет только токен
    params = {k: v for k, v in request.query_params.items() if k in ("date_from", "date_to")}
    resp = http.get(
        f"{REPORTS_API_URL}/reports",
        params=params,
        headers={"Authorization": f"Bearer {token}"},
    )
    return JSONResponse(resp.json(), status_code=resp.status_code)
