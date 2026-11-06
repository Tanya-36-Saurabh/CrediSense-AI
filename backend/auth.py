
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field


# Configuration
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "credisense.db"

load_dotenv(BASE_DIR / ".env")

JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 30

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)

password_hasher = PasswordHasher()
security = HTTPBearer()


# Password Security
def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return password_hasher.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False


# Request Models
class SignupInput(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=128)


class LoginInput(BaseModel):
    email: str
    password: str


# JWT Functions
def create_access_token(user_id: int) -> str:
    if not JWT_SECRET or len(JWT_SECRET) < 32:
        raise RuntimeError(
            "JWT_SECRET must be at least 32 characters"
        )

    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=TOKEN_EXPIRE_MINUTES),
        "type": "access"
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM
    )


def decode_access_token(token: str) -> int:
    if not JWT_SECRET or len(JWT_SECRET) < 32:
        raise RuntimeError(
            "JWT_SECRET is not configured securely"
        )

    payload = jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        options={
            "require": ["sub", "iat", "exp", "type"]
        }
    )

    if payload["type"] != "access":
        raise jwt.InvalidTokenError("Invalid token type")

    user_id = int(payload["sub"])

    if user_id <= 0:
        raise jwt.InvalidTokenError("Invalid user ID")

    return user_id


# Signup API
@router.post("/signup", status_code=201)
def signup(data: SignupInput):
    email = data.email.strip().lower()

    if "@" not in email or email.startswith("@"):
        raise HTTPException(
            status_code=422,
            detail="Invalid email address"
        )

    try:
        password_hash = hash_password(data.password)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (email, password_hash)
                VALUES (?, ?)
                """,
                (email, password_hash)
            )

            user_id = cursor.lastrowid

        return {
            "message": "User registered successfully",
            "user_id": user_id
        }

    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to register user"
        ) from exc


# Login API
@router.post("/login")
def login(data: LoginInput):
    email = data.email.strip().lower()

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        user = conn.execute(
            """
            SELECT id, email, password_hash, is_active
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not verify_password(
        data.password,
        user["password_hash"]
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=403,
            detail="Account is disabled"
        )

    access_token = create_access_token(user["id"])

    return {
        "message": "Login successful",
        "user_id": user["id"],
        "email": user["email"],
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 1800
    }


# Current User Authentication
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    try:
        user_id = decode_access_token(
            credentials.credentials
        )

    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        user = conn.execute(
            """
            SELECT id, email, is_active
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

    if user is None or not user["is_active"]:
        raise HTTPException(
            status_code=401,
            detail="User not found or inactive"
        )

    return {
        "user_id": user["id"],
        "email": user["email"]
    }


# Profile API
@router.get("/me")
def get_my_profile(
    current_user=Depends(get_current_user)
):
    return current_user
