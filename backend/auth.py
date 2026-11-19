
import os
import re
import time
import sqlite3

from collections import deque
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from threading import Lock

import jwt

from argon2 import PasswordHasher
from argon2.exceptions import (
    VerifyMismatchError,
    VerificationError,
    InvalidHashError
)

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response
)

from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer
)

from pydantic import BaseModel, Field

from config import DB_PATH


# ==========================================
# CONFIGURATION
# ==========================================

JWT_SECRET = os.environ.get("JWT_SECRET")

JWT_ALGORITHM = "HS256"

TOKEN_EXPIRE_MINUTES = 30

if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise RuntimeError(
        "JWT_SECRET must be at least 32 characters"
    )


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)

password_hasher = PasswordHasher()

security = HTTPBearer(auto_error=False)

# Reduce login timing differences between
# existing and nonexistent accounts.
DUMMY_PASSWORD_HASH = password_hasher.hash(
    os.urandom(32).hex()
)


# ==========================================
# DATABASE CONNECTION
# ==========================================

@contextmanager
def auth_database():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=10
    )

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        yield conn
        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ==========================================
# RATE LIMITING
# ==========================================

LOGIN_MAX_ATTEMPTS = 10
LOGIN_WINDOW_SECONDS = 300

SIGNUP_MAX_ATTEMPTS = 5
SIGNUP_WINDOW_SECONDS = 600

MAX_RATE_LIMIT_KEYS = 10000

rate_limit_store = {}
rate_limit_lock = Lock()


def get_client_ip(request: Request):
    if request.client:
        return request.client.host

    return "unknown"


def check_rate_limit(
    key,
    max_attempts,
    window_seconds
):
    now = time.monotonic()

    with rate_limit_lock:

        expired_keys = []

        for existing_key, entry in rate_limit_store.items():
            timestamps, window = entry

            while (
                timestamps
                and now - timestamps[0] >= window
            ):
                timestamps.popleft()

            if not timestamps:
                expired_keys.append(existing_key)

        for expired_key in expired_keys:
            del rate_limit_store[expired_key]

        if (
            key not in rate_limit_store
            and len(rate_limit_store) >= MAX_RATE_LIMIT_KEYS
        ):
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Try again later.",
                headers={"Retry-After": "60"}
            )

        if key not in rate_limit_store:
            rate_limit_store[key] = (
                deque(),
                window_seconds
            )

        attempts, _ = rate_limit_store[key]

        if len(attempts) >= max_attempts:
            retry_after = max(
                1,
                int(
                    window_seconds
                    - (now - attempts[0])
                ) + 1
            )

            raise HTTPException(
                status_code=429,
                detail=(
                    "Too many attempts. "
                    "Please try again later."
                ),
                headers={
                    "Retry-After": str(retry_after)
                }
            )

        attempts.append(now)


# ==========================================
# EMAIL VALIDATION
# ==========================================

def validate_email(email: str):
    email = email.strip().lower()

    if len(email) > 254:
        raise HTTPException(
            status_code=422,
            detail="Invalid email address"
        )

    pattern = (
        r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+"
        r"@"
        r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
        r"[a-z]{2,63}"
    )

    if not re.fullmatch(pattern, email):
        raise HTTPException(
            status_code=422,
            detail="Invalid email address"
        )

    local_part = email.split("@", 1)[0]

    if (
        len(local_part) > 64
        or local_part.startswith(".")
        or local_part.endswith(".")
        or ".." in local_part
    ):
        raise HTTPException(
            status_code=422,
            detail="Invalid email address"
        )

    return email


# ==========================================
# PASSWORD SECURITY
# ==========================================

def hash_password(password: str):
    return password_hasher.hash(password)


def verify_password(
    password: str,
    stored_hash: str
):
    try:
        return password_hasher.verify(
            stored_hash,
            password
        )

    except (
        VerifyMismatchError,
        VerificationError,
        InvalidHashError
    ):
        return False


# ==========================================
# REQUEST MODELS
# ==========================================

class SignupInput(BaseModel):
    email: str = Field(
        min_length=5,
        max_length=254
    )

    password: str = Field(
        min_length=12,
        max_length=128
    )


class LoginInput(BaseModel):
    email: str = Field(
        min_length=5,
        max_length=254
    )

    password: str = Field(
        min_length=1,
        max_length=128
    )


# ==========================================
# JWT TOKEN CREATION
# ==========================================

def create_access_token(user_id: int):
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(
            minutes=TOKEN_EXPIRE_MINUTES
        ),
        "type": "access"
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM
    )


# ==========================================
# JWT TOKEN VALIDATION
# ==========================================

def decode_access_token(token: str):
    if not token or len(token) > 4096:
        raise jwt.InvalidTokenError(
            "Invalid token"
        )

    payload = jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        options={
            "require": [
                "sub",
                "iat",
                "exp",
                "type"
            ],
            "verify_signature": True,
            "verify_exp": True,
            "verify_iat": True
        }
    )

    if payload["type"] != "access":
        raise jwt.InvalidTokenError(
            "Invalid token type"
        )

    subject = payload["sub"]

    if not isinstance(subject, str):
        raise jwt.InvalidTokenError(
            "Invalid user ID"
        )

    user_id = int(subject)

    if (
        user_id <= 0
        or user_id > 9223372036854775807
    ):
        raise jwt.InvalidTokenError(
            "Invalid user ID"
        )

    return user_id


# ==========================================
# SIGNUP API
# ==========================================

@router.post("/signup", status_code=201)
def signup(
    data: SignupInput,
    request: Request,
    response: Response
):
    response.headers["Cache-Control"] = "no-store"

    client_ip = get_client_ip(request)

    check_rate_limit(
        key=("signup", client_ip),
        max_attempts=SIGNUP_MAX_ATTEMPTS,
        window_seconds=SIGNUP_WINDOW_SECONDS
    )

    email = validate_email(data.email)

    try:
        password_hash = hash_password(
            data.password
        )

        with auth_database() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (
                    email,
                    password_hash
                )
                VALUES (?, ?)
                """,
                (
                    email,
                    password_hash
                )
            )

            user_id = cursor.lastrowid

        return {
            "message": "User registered successfully",
            "user_id": user_id
        }

    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        ) from exc

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to register user"
        ) from exc


# ==========================================
# LOGIN API
# ==========================================

@router.post("/login")
def login(
    data: LoginInput,
    request: Request,
    response: Response
):
    response.headers["Cache-Control"] = "no-store"

    client_ip = get_client_ip(request)

    check_rate_limit(
        key=("login", client_ip),
        max_attempts=LOGIN_MAX_ATTEMPTS,
        window_seconds=LOGIN_WINDOW_SECONDS
    )

    email = validate_email(data.email)

    try:
        with auth_database() as conn:
            user = conn.execute(
                """
                SELECT
                    id,
                    email,
                    password_hash,
                    is_active
                FROM users
                WHERE email = ?
                """,
                (email,)
            ).fetchone()

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to login"
        ) from exc

    stored_hash = (
        user["password_hash"]
        if user is not None
        else DUMMY_PASSWORD_HASH
    )

    password_valid = verify_password(
        data.password,
        stored_hash
    )

    if user is None or not password_valid:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=403,
            detail="Account is disabled"
        )

    access_token = create_access_token(
        user["id"]
    )

    return {
        "message": "Login successful",
        "user_id": user["id"],
        "email": user["email"],
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": TOKEN_EXPIRE_MINUTES * 60
    }


# ==========================================
# CURRENT USER AUTHENTICATION
# ==========================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    )
):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    try:
        user_id = decode_access_token(
            credentials.credentials
        )

    except (
        jwt.InvalidTokenError,
        ValueError,
        TypeError,
        OverflowError
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    try:
        with auth_database() as conn:
            user = conn.execute(
                """
                SELECT
                    id,
                    email,
                    is_active
                FROM users
                WHERE id = ?
                """,
                (user_id,)
            ).fetchone()

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to validate user"
        ) from exc

    if user is None or not user["is_active"]:
        raise HTTPException(
            status_code=401,
            detail="User not found or inactive",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    return {
        "user_id": user["id"],
        "email": user["email"]
    }


# ==========================================
# PROFILE API
# ==========================================

@router.get("/me")
def get_my_profile(
    response: Response,
    current_user=Depends(get_current_user)
):
    response.headers["Cache-Control"] = "no-store"

    return current_user
