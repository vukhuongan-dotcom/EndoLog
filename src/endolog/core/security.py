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


class SessionRevokedError(Exception):
    """Raised when a syntactically valid JWT has been revoked by server state (G01)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


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
    auth_ver: int = 1,
    store_epoch: int = 1,
) -> tuple[str, int]:
    now = dt.datetime.now(dt.timezone.utc)
    exp = now + dt.timedelta(seconds=settings.session_timeout_seconds)
    payload = {
        "sub": username,
        "role": role,
        "display_name": display_name,
        "department": department,
        "auth_ver": max(1, int(auth_ver)),
        "store_epoch": max(1, int(store_epoch)),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": secrets.token_hex(12),
    }
    encoded = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return encoded, settings.session_timeout_seconds


def decode_access_token(settings: EndoLogSettings, token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def prune_expired_revoked_jtis(
    revoked_jtis: Mapping[str, Any] | None,
    *,
    now_ts: int | None = None,
) -> dict[str, int]:
    effective_now = int(dt.datetime.now(dt.timezone.utc).timestamp()) if now_ts is None else int(now_ts)
    if not revoked_jtis:
        return {}
    pruned: dict[str, int] = {}
    for jti_key, exp_val in revoked_jtis.items():
        try:
            exp_int = int(exp_val)
        except (TypeError, ValueError):
            continue
        if exp_int >= effective_now:
            pruned[str(jti_key)] = exp_int
    return pruned


def validate_live_session_claims(
    claims: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    """Server-authoritative JWT check against store_epoch, revoked_jtis, active user, and auth_version (G01)."""
    live_epoch = int(snapshot.get("store_epoch", 1) or 1)
    token_epoch = int(claims.get("store_epoch", 0) or 0)
    if token_epoch != live_epoch:
        raise SessionRevokedError(
            "TOKEN_STORE_EPOCH_REVOKED",
            "Phiên làm việc đã bị thu hồi do kho dữ liệu chuyển sang thế hệ mới.",
        )

    jti = str(claims.get("jti") or "").strip()
    revoked_map = snapshot.get("revoked_jtis") or {}
    if not jti or jti in revoked_map:
        raise SessionRevokedError(
            "TOKEN_LOGGED_OUT",
            "Phiên làm việc đã đăng xuất và bị thu hồi trên máy chủ.",
        )

    sub = str(claims.get("sub") or "").strip()
    users_map = snapshot.get("users") or {}
    live_user = users_map.get(sub)
    if not isinstance(live_user, Mapping) or live_user.get("active") is not True:
        raise SessionRevokedError(
            "USER_INACTIVE_OR_REMOVED",
            "Tài khoản không tồn tại hoặc đã ngừng kích hoạt.",
        )

    live_auth_ver = int(live_user.get("auth_version", 1) or 1)
    token_auth_ver = int(claims.get("auth_ver", 0) or 0)
    if token_auth_ver != live_auth_ver:
        raise SessionRevokedError(
            "TOKEN_AUTH_VERSION_REVOKED",
            "Phiên làm việc đã bị thu hồi do thay đổi hoặc đặt lại mật khẩu.",
        )

    return {
        **dict(claims),
        "sub": str(live_user["username"]),
        "role": str(live_user["role"]),
        "display_name": str(live_user["display_name"]),
        "department": str(live_user["department"]),
        "auth_ver": live_auth_ver,
        "store_epoch": live_epoch,
    }


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
