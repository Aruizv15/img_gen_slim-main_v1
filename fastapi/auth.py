import os
import time
import hmac
import hashlib
import base64
import json as _json
import asyncio
import smtplib
from email.mime.text import MIMEText
from typing import Optional

import bcrypt
import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

APP_USERNAME = os.getenv("APP_USERNAME", "admin")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
SESSION_SECRET = os.getenv("SESSION_SECRET") or os.getenv("RESTART_TOKEN", "change-me")
ADMIN_SECRET = os.getenv("ADMIN_SECRET") or os.getenv("RESTART_TOKEN", "change-me")
DATABASE_URL = os.getenv("DATABASE_URL")
SESSION_TTL_SECONDS = 60 * 60 * 12
RESET_TTL_SECONDS = 60 * 60

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.office365.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM") or SMTP_USERNAME

# Microsoft Graph API (metodo preferido: no depende de SMTP ni de las
# politicas de "Security Defaults" del tenant). Si estas variables estan
# configuradas, send_email() las usa en vez de SMTP.
GRAPH_TENANT_ID = os.getenv("AZURE_TENANT_ID")
GRAPH_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
GRAPH_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
GRAPH_SENDER_EMAIL = os.getenv("AZURE_SENDER_EMAIL") or SMTP_FROM

security = HTTPBearer()
auth_router = APIRouter()

_pool: Optional[asyncpg.Pool] = None


async def _get_pool() -> Optional[asyncpg.Pool]:
    global _pool
    if _pool is not None:
        return _pool
    if not DATABASE_URL:
        return None
    try:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
        async with _pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS batchapp_users (
                    id            SERIAL PRIMARY KEY,
                    username      TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    email         TEXT,
                    role          TEXT NOT NULL DEFAULT 'user',
                    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            await conn.execute("ALTER TABLE batchapp_users ADD COLUMN IF NOT EXISTS email TEXT")
            await conn.execute("ALTER TABLE batchapp_users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user'")
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS image_ownership (
                    vrepro_id  TEXT NOT NULL,
                    filename   TEXT NOT NULL,
                    username   TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (vrepro_id, filename)
                )
                """
            )
        return _pool
    except Exception as e:
        print(f"[AUTH] Error de conexion a la base de datos: {e}")
        _pool = None
        return None


async def _verify_db_user(username: str, password: str) -> Optional[str]:
    """Devuelve el rol ('admin'/'user') si las credenciales son validas, o None si no."""
    pool = await _get_pool()
    if pool is None:
        return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT password_hash, role FROM batchapp_users WHERE username = $1", username
        )
    if row is None:
        return None
    if bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
        return row["role"] or "user"
    return None


async def _get_user_email(username: str) -> Optional[str]:
    pool = await _get_pool()
    if pool is None:
        return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT email FROM batchapp_users WHERE username = $1", username)
    return row["email"] if row and row["email"] else None


async def record_image_ownership(vrepro_id: str, filenames: list, username: str) -> None:
    """Se llama desde main.py justo despues de confirmar que las imagenes
    de un job se subieron a B2 -- registra que ESTE usuario las genero."""
    pool = await _get_pool()
    if pool is None or not filenames:
        return
    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO image_ownership (vrepro_id, filename, username)
            VALUES ($1, $2, $3)
            ON CONFLICT (vrepro_id, filename) DO NOTHING
            """,
            [(vrepro_id, f, username) for f in filenames],
        )


async def get_image_owner(vrepro_id: str, filename: str) -> Optional[str]:
    """Devuelve el username dueño de esta imagen especifica, o None si
    no tiene dueño registrado (imagen de antes de este sistema)."""
    pool = await _get_pool()
    if pool is None:
        return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT username FROM image_ownership WHERE vrepro_id = $1 AND filename = $2",
            vrepro_id, filename,
        )
    return row["username"] if row else None


async def get_all_owned_files() -> set:
    """Devuelve el set de TODAS las (vrepro_id, filename) que tienen
    algun dueño registrado, sin importar cual. Sirve para distinguir
    'imagen sin dueño (legacy)' de 'imagen de otro usuario'."""
    pool = await _get_pool()
    if pool is None:
        return set()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT vrepro_id, filename FROM image_ownership")
    return {(r["vrepro_id"], r["filename"]) for r in rows}


async def get_owned_files_for_user(username: str) -> set:
    """Devuelve el set de (vrepro_id, filename) que generó este usuario."""
    pool = await _get_pool()
    if pool is None:
        return set()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT vrepro_id, filename FROM image_ownership WHERE username = $1", username
        )
    return {(r["vrepro_id"], r["filename"]) for r in rows}


async def _get_graph_token() -> str:
    url = f"https://login.microsoftonline.com/{GRAPH_TENANT_ID}/oauth2/v2.0/token"
    data = {
        "client_id": GRAPH_CLIENT_ID,
        "client_secret": GRAPH_CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(url, data=data, timeout=15)
        if r.status_code >= 300:
            raise RuntimeError(f"Error obteniendo token de Graph: {r.status_code} {r.text}")
        return r.json()["access_token"]


async def _send_via_graph(to_email: str, subject: str, body: str) -> None:
    token = await _get_graph_token()
    url = f"https://graph.microsoft.com/v1.0/users/{GRAPH_SENDER_EMAIL}/sendMail"
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": to_email}}],
        },
        # Con esto el correo SI queda registrado en la carpeta de
        # Enviados de GRAPH_SENDER_EMAIL -- algo que SMTP nunca podia
        # garantizar cuando se enviaba autenticado con otra cuenta.
        "saveToSentItems": True,
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=15,
        )
        if r.status_code >= 300:
            raise RuntimeError(f"Error enviando por Graph: {r.status_code} {r.text}")


def _send_email_sync(to_email: str, subject: str, body: str) -> None:
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email

    # Puerto 465 = SSL implicito desde el inicio de la conexion (SMTPS,
    # comun en servidores propios tipo cPanel). Cualquier otro puerto
    # (587, 25) = STARTTLS, la conexion arranca sin cifrar y se cifra
    # despues (comun en Outlook, Gmail, Resend).
    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [to_email], msg.as_string())
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [to_email], msg.as_string())


async def send_email(to_email: str, subject: str, body: str) -> None:
    if GRAPH_TENANT_ID and GRAPH_CLIENT_ID and GRAPH_CLIENT_SECRET:
        await _send_via_graph(to_email, subject, body)
        return
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        raise RuntimeError("Ni Microsoft Graph ni SMTP estan configurados")
    await asyncio.to_thread(_send_email_sync, to_email, subject, body)


def _sign(payload: str) -> str:
    return hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def _make_token(username: str, ttl: int, typ: str, role: str = "user") -> str:
    payload = _json.dumps({"u": username, "exp": int(time.time()) + ttl, "typ": typ, "role": role})
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode()
    return f"{payload_b64}.{_sign(payload_b64)}"


def _verify_token(token: str, expected_typ: str, invalid_msg: str, status_code: int) -> dict:
    try:
        payload_b64, signature = token.split(".", 1)
        if not hmac.compare_digest(signature, _sign(payload_b64)):
            raise ValueError
        payload = _json.loads(base64.urlsafe_b64decode(payload_b64.encode()).decode())
        if payload.get("typ") != expected_typ:
            raise ValueError
    except Exception:
        raise HTTPException(status_code=status_code, detail=invalid_msg)

    if int(time.time()) > payload.get("exp", 0):
        raise HTTPException(status_code=status_code, detail="Expiró, solicita uno nuevo")
    return payload


def create_session_token(username: str, role: str = "user") -> str:
    return _make_token(username, SESSION_TTL_SECONDS, "session", role)


def verify_session_token(token: str) -> dict:
    return _verify_token(token, "session", "Token de sesión inválido", 401)


def create_reset_token(username: str) -> str:
    return _make_token(username, RESET_TTL_SECONDS, "reset")


def verify_reset_token(token: str) -> dict:
    return _verify_token(token, "reset", "Link de recuperación inválido", 400)


def require_login(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    return verify_session_token(credentials.credentials)


def require_login_flexible(request: Request, token: Optional[str] = None) -> dict:
    if token:
        return verify_session_token(token)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return verify_session_token(auth_header[7:])
    raise HTTPException(status_code=401, detail="No autenticado")


def require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = credentials.credentials
    if hmac.compare_digest(token, ADMIN_SECRET):
        return token
    try:
        payload = verify_session_token(token)
        if payload.get("role") == "admin":
            return token
    except HTTPException:
        pass
    raise HTTPException(status_code=403, detail="No autorizado")


@auth_router.post("/login")
async def login(request: Request):
    body = await request.json()
    username = body.get("username", "")
    password = body.get("password", "")

    if not username or not password:
        raise HTTPException(status_code=400, detail="Usuario y contraseña son requeridos")

    role = await _verify_db_user(username, password)

    if role is None and APP_PASSWORD:
        if hmac.compare_digest(username, APP_USERNAME) and hmac.compare_digest(password, APP_PASSWORD):
            role = "admin"

    if role is None:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    token = create_session_token(username, role)
    return {"token": token, "username": username, "role": role, "expires_in": SESSION_TTL_SECONDS}


@auth_router.get("/session_check")
async def session_check(session: dict = Depends(require_login)):
    return {"valid": True, "username": session.get("u"), "role": session.get("role", "user")}


@auth_router.post("/register")
async def register(request: Request):
    body = await request.json()
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    email = (body.get("email") or "").strip() or None

    if not username or not password:
        raise HTTPException(status_code=400, detail="username y password son requeridos")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")

    pool = await _get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Base de datos no disponible")

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO batchapp_users (username, password_hash, email, role) VALUES ($1, $2, $3, 'user')",
                username, password_hash, email,
            )
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail=f"El usuario '{username}' ya existe")

    token = create_session_token(username, "user")
    return {"token": token, "username": username, "role": "user", "expires_in": SESSION_TTL_SECONDS}


@auth_router.post("/admin/create_user")
async def admin_create_user(request: Request, _: str = Depends(require_admin)):
    body = await request.json()
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    email = (body.get("email") or "").strip() or None
    role = (body.get("role") or "user").strip()
    if role not in ("user", "admin"):
        role = "user"

    if not username or not password:
        raise HTTPException(status_code=400, detail="username y password son requeridos")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")

    pool = await _get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Base de datos no disponible")

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO batchapp_users (username, password_hash, email, role) VALUES ($1, $2, $3, $4)",
                username, password_hash, email, role,
            )
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail=f"El usuario '{username}' ya existe")

    return {"status": "success", "message": f"Usuario '{username}' creado ({role})"}


@auth_router.post("/admin/reset_password")
async def admin_reset_password(request: Request, _: str = Depends(require_admin)):
    body = await request.json()
    username = (body.get("username") or "").strip()
    new_password = body.get("new_password") or ""

    if not username or not new_password:
        raise HTTPException(status_code=400, detail="username y new_password son requeridos")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")

    pool = await _get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Base de datos no disponible")

    password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE batchapp_users SET password_hash = $1 WHERE username = $2",
            password_hash, username,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail=f"El usuario '{username}' no existe")

    return {"status": "success", "message": f"Contraseña de '{username}' actualizada"}


@auth_router.post("/admin/delete_user")
async def admin_delete_user(request: Request, _: str = Depends(require_admin)):
    body = await request.json()
    username = (body.get("username") or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="username es requerido")

    pool = await _get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Base de datos no disponible")

    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM batchapp_users WHERE username = $1", username)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail=f"El usuario '{username}' no existe")

    return {"status": "success", "message": f"Usuario '{username}' eliminado"}


@auth_router.get("/admin/list_users")
async def admin_list_users(_: str = Depends(require_admin)):
    pool = await _get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Base de datos no disponible")
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT username, email, role, created_at FROM batchapp_users ORDER BY created_at")
    return {"users": [
        {"username": r["username"], "email": r["email"], "role": r["role"], "created_at": r["created_at"].isoformat()}
        for r in rows
    ]}


@auth_router.post("/forgot_password")
async def forgot_password(request: Request):
    body = await request.json()
    username = (body.get("username") or "").strip()
    generic_msg = {"status": "success", "message": "Si el usuario existe y tiene correo registrado, se envió un link de recuperación."}

    if not username:
        raise HTTPException(status_code=400, detail="username es requerido")

    email = await _get_user_email(username)
    if not email:
        return generic_msg

    token = create_reset_token(username)
    reset_link = f"{str(request.base_url).rstrip('/')}/static/reset-password.html?token={token}"
    subject = "BatchApp — Recuperación de contraseña"
    body_text = (
        f"Hola {username},\n\n"
        f"Solicitaste restablecer tu contraseña de GenrImage.\n"
        f"Este link es válido por 1 hora:\n\n{reset_link}\n\n"
        f"Si no fuiste tú, ignora este correo."
    )

    try:
        await send_email(email, subject, body_text)
    except Exception as e:
        print(f"[AUTH] Error enviando correo: {e}")

    return generic_msg


@auth_router.post("/reset_password_with_token")
async def reset_password_with_token(request: Request):
    body = await request.json()
    token = body.get("token") or ""
    new_password = body.get("new_password") or ""

    if not token or not new_password:
        raise HTTPException(status_code=400, detail="token y new_password son requeridos")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")

    payload = verify_reset_token(token)
    username = payload["u"]

    pool = await _get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Base de datos no disponible")

    password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE batchapp_users SET password_hash = $1 WHERE username = $2",
            password_hash, username,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return {"status": "success", "message": "Contraseña actualizada. Ya puedes iniciar sesión."}
