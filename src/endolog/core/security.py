"""Authentication (Argon2id + JWT HS256), RBAC, and 5-latch fail-closed Local Bypass Gate."""

from __future__ import annotations

import datetime as dt
import secrets
from typing import Any, Mapping
from urllib.parse import urlparse

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from endolog.core.config import EndoLogSettings

COOKIE_NAME = "endolog_session"

# RFC 9106 Argon2id parameters
_HASHER = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
)

PROXY_HEADERS = ("x-forwarded-for", "forwarded", "x-real-ip")
LOOPBACK_IPS = {"127.0.0.1", "::1"}
TRUSTED_LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]"}


def hash_password(plain_password: str) -> str:
    return _HASHER.hash(plain_password)


def verify_password(password_hash: str, plain_password: str) -> bool:
    try:
        return _HASHER.verify(password_hash, plain_password)
    except (VerifyMismatchError, Exception):
        return False


def create_access_token(
    settings: EndoLogSettings,
    *,
    username: str,
    role: str,
    display_name: str,
    department: str,
) -> tuple[str, int]:
    now = dt.datetime.now(dt.timezone.utc)
    exp = now + dt.timedelta(seconds=settings.session_timeout_seconds)
    payload = {
        "sub": username,
        "role": role,
        "display_name": display_name,
        "department": department,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": secrets.token_hex(12),
    }
    encoded = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return encoded, settings.session_timeout_seconds


def decode_access_token(settings: EndoLogSettings, token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def _extract_host_without_port(raw_host: str) -> str:
    raw = raw_host.strip().lower()
    if not raw:
        return ""
    if raw.startswith("["):
        end_idx = raw.find("]")
        return raw[: end_idx + 1] if end_idx != -1 else raw
    return raw.split(":")[0]


def evaluate_local_bypass_gate(
    settings: EndoLogSettings,
    *,
    client_ip: str | None,
    headers: Mapping[str, str],
) -> tuple[bool, str]:
    """5-latch fail-closed predicate for /api/auth/local-bypass (Rule v2:R41 + F06)."""
    if settings.env_mode != "local_dev_synthetic":
        return False, "403_ENV_NOT_SYNTHETIC_DEV"
    if not settings.enable_dev_bypass:
        return False, "403_OPT_IN_DISABLED"
    if settings.has_phi_vault_marker or settings.data_dir.name != "data_synthetic_dev":
        return False, "403_DATA_DIR_NOT_ISOLATED_SYNTHETIC"
    if settings.bind_host not in LOOPBACK_IPS:
        return False, "403_NON_LOOPBACK_BIND"
    if (client_ip or "") not in LOOPBACK_IPS:
        return False, "403_NON_LOOPBACK_CLIENT"

    lowered = {k.lower(): v for k, v in headers.items()}
    for h_name in PROXY_HEADERS:
        if (lowered.get(h_name) or "").strip():
            return False, "403_PROXY_HEADER_PRESENT"

    host_only = _extract_host_without_port(lowered.get("host", ""))
    if host_only not in TRUSTED_LOCAL_HOSTS:
        return False, "403_UNTRUSTED_HOST_HEADER"

    origin_raw = (lowered.get("origin") or "").strip()
    if origin_raw:
        parsed = urlparse(origin_raw)
        origin_host = f"[{parsed.hostname}]" if parsed.hostname == "::1" else (parsed.hostname or "").lower()
        if origin_host not in TRUSTED_LOCAL_HOSTS:
            return False, "403_UNTRUSTED_ORIGIN_HEADER"

    return True, "200_SYNTHETIC_DEV_BYPASS_OK"
