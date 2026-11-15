import os

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

ISSUER = os.environ["KEYCLOAK_ISSUER"]
JWKS_URL = os.environ["KEYCLOAK_JWKS_URL"]
REQUIRED_ROLE = os.environ.get("REQUIRED_ROLE", "prothetic_user")
ALLOWED_CLIENTS = os.environ.get("ALLOWED_CLIENTS", "reports-bff,reports-frontend").split(",")

bearer = HTTPBearer(auto_error=False)
jwks_client = jwt.PyJWKClient(JWKS_URL, cache_keys=True)


def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Требуется аутентификация")
    try:
        key = jwks_client.get_signing_key_from_jwt(credentials.credentials)
        claims = jwt.decode(
            credentials.credentials,
            key.key,
            algorithms=["RS256"],
            issuer=ISSUER,
            options={"verify_aud": False, "require": ["exp", "iss", "sub"]},
        )
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Недействительный токен")
    if claims.get("azp") not in ALLOWED_CLIENTS:
        raise HTTPException(status_code=401, detail="Токен выдан другому клиенту")
    roles = claims.get("realm_access", {}).get("roles", [])
    if REQUIRED_ROLE not in roles:
        raise HTTPException(status_code=403, detail="Нет доступа к отчётам")
    username = claims.get("preferred_username")
    if not username:
        raise HTTPException(status_code=401, detail="В токене нет имени пользователя")
    return {"username": username}
