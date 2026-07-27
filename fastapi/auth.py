"""
Modulo de autenticacion, separado a proposito del resto del backend
(main.py) para que los cambios en login/sesiones no afecten ni se
mezclen con la logica de generacion de imagenes, Backblaze, etc.

Uso desde main.py:
    from auth import auth_router, require_login, require_login_flexible

    app.include_router(auth_router)

    @app.get("/algun_endpoint_protegido")
    async def algo(session: dict = Depends(require_login)):
        ...
"""
import os
import time
import hmac
import hashlib
import base64
import json as _json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# ---- Configuracion (variables de entorno) ----
APP_USERNAME = os.getenv("APP_USERNAME", "admin")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
SESSION_SECRET = os.getenv("SESSION_SECRET") or os.getenv("RESTART_TOKEN", "change-me")
SESSION_TTL_SECONDS = 60 * 60 * 12  # 12 horas

security = HTTPBearer()
auth_router = APIRouter()


# ---- Firmado y verificacion de tokens ----
def _sign(payload: str) -> str:
    return hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_session_token(username: str) -> str:
    expires_at = int(time.time()) + SESSION_TTL_SECONDS
    payload = _json.dumps({"u": username, "exp": expires_at})
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode()
    signature = _sign(payload_b64)
    return f"{payload_b64}.{signature}"


def verify_session_token(token: str) -> dict:
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError:
        raise HTTPException(status_code=401, detail="Token de sesion invalido")

    expected_sig = _sign(payload_b64)
    if not hmac.compare_digest(signature, expected_sig):
        raise HTTPException(status_code=401, detail="Token de sesion invalido")

    try:
        payload = _json.loads(base64.urlsafe_b64decode(payload_b64.encode()).decode())
    except Exception:
        raise HTTPException(status_code=401, detail="Token de sesion invalido")

    if int(time.time()) > payload.get("exp", 0):
        raise HTTPException(status_code=401, detail="Sesion expirada, inicia sesion de nuevo")

    return payload


# ---- Dependencias para proteger endpoints ----
def require_login(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Uso normal: exige la cabecera 'Authorization: Bearer <token>'."""
    return verify_session_token(credentials.credentials)


def require_login_flexible(request: Request, token: Optional[str] = None) -> dict:
    """
    Igual que require_login, pero tambien acepta el token como query
    parametro (?token=...). Necesario para endpoints usados como src de
    <img>, ya que las etiquetas <img> no pueden enviar la cabecera
    Authorization -- el navegador solo hace un GET simple.
    """
    if token:
        return verify_session_token(token)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return verify_session_token(auth_header[7:])
    raise HTTPException(status_code=401, detail="No autenticado")


# ---- Endpoints propios del modulo de auth ----
@auth_router.post("/login")
async def login(request: Request):
    """
    Recibe {"username": ..., "password": ...} y devuelve un token de
    sesion valido por 12 horas si las credenciales son correctas.
    """
    body = await request.json()
    username = body.get("username", "")
    password = body.get("password", "")

    if not APP_PASSWORD:
        raise HTTPException(status_code=500, detail="APP_PASSWORD no esta configurado en el servidor")

    valid = hmac.compare_digest(username, APP_USERNAME) and hmac.compare_digest(password, APP_PASSWORD)
    if not valid:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    token = create_session_token(username)
    return {"token": token, "username": username, "expires_in": SESSION_TTL_SECONDS}


@auth_router.get("/session_check")
async def session_check(session: dict = Depends(require_login)):
    """Permite al frontend confirmar si el token guardado sigue siendo valido."""
    return {"valid": True, "username": session.get("u")}
