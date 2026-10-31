"""FastAPI application entrypoint for EndoLog with strict CSP, Zero-PHI HTTP headers, RBAC, and Superadmin governance."""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from endolog import __version__
from endolog.api.service import (
    ConcurrencyConflictError,
    DomainConflictError,
    DomainValidationError,
    DuplicateOutpatientConfirmationRequired,
    EndoLogService,
    InvalidPasswordError,
)
from endolog.clinical.cusum import build_cusum_series_from_cases
from endolog.clinical.export_profiles import (
    MAX_VAULT_BLOB_BYTES,
    VaultDecryptError,
    VaultPayloadTooLargeError,
    VaultSchemaValidationError,
    export_profile_a_encrypted_vault,
    export_profile_b_rows,
    export_profile_c_summary,
    rows_to_csv_bytes,
    rows_to_xlsx_bytes,
)
from endolog.clinical.quality_metrics import compute_kpi_snapshot
from endolog.core.audit import (
    build_audit_entry,
    verify_audit_chain,
    verify_audit_lineage_bridges,
)
from endolog.core.config import EndoLogSettings, load_settings
from endolog.core.dlp import DlpViolationError
from endolog.core.persistence import AtomicJsonStore
from endolog.core.security import (
    COOKIE_NAME,
    SessionRevokedError,
    create_access_token,
    decode_access_token,
    evaluate_local_bypass_gate,
    prune_expired_revoked_jtis,
    validate_live_session_claims,
    verify_password,
)
from endolog.core.seed_od05 import build_od05_synthetic_vignettes
from endolog.schemas.clinical import (
    AdminPasswordResetRequest,
    CaseCreateRequest,
    CasePhasePatchRequest,
    EpisodeReconcileRequest,
    PasswordChangeRequest,
    PatientMergeRequest,
    ProfileARestoreRequest,
)

# Allow small JSON framing overhead around a 10 MiB .endolog.enc blob while still cutting off HTTP stream early
MAX_RESTORE_HTTP_BODY_BYTES = MAX_VAULT_BLOB_BYTES + 262_144


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class LocalBypassRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_username: str = "nguyenbinhan"


class SettingsPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    colo_guideline_mode: str | None = None
    adr_min_age: int | None = None
    cusum_preset: str | None = None
    kpi_min_sample_size: int | None = Field(default=None, ge=1, le=500)


class ProfileABackupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passphrase: str = Field(..., min_length=12, max_length=128)


STATIC_DIR = Path(__file__).resolve().parent / "static"


def _extract_request_token(request: Request) -> str | None:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        tok = auth_header.split(" ", 1)[1].strip()
        if tok:
            return tok
    cookie_tok = request.cookies.get(COOKIE_NAME)
    return cookie_tok.strip() if cookie_tok else None


def create_app(
    settings: EndoLogSettings | None = None,
    *,
    auto_seed_synthetic: bool = True,
    bootstrap_passwords: dict[str, str] | None = None,
) -> FastAPI:
    cfg = settings or load_settings()
    store = AtomicJsonStore(
        cfg.data_dir,
        cfg.backup_dir,
        bootstrap_passwords=bootstrap_passwords,
        default_kpi_min_sample_size=cfg.kpi_min_sample_size,
    )
    svc = EndoLogService(cfg, store)

    if auto_seed_synthetic and cfg.env_mode == "local_dev_synthetic":
        snap = store.read_snapshot()
        if len(snap.get("cases", {})) == 0:
            for item in build_od05_synthetic_vignettes():
                svc.create_case(
                    CaseCreateRequest.model_validate(item),
                    actor_username="nguyenbinhan",
                    actor_role="endoscopist",
                )

    app = FastAPI(
        title="EndoLog — Hệ thống sổ bộ lâm sàng & đánh giá chất lượng nội soi tiêu hoá",
        version=__version__,
        docs_url=None,
        redoc_url=None,
    )
    app.state.settings = cfg
    app.state.store = store
    app.state.service = svc

    @app.middleware("http")
    async def security_and_zero_phi_headers(request: Request, call_next: Any) -> Response:
        response: Response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "font-src 'self'; img-src 'self' data:; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    def get_current_user(request: Request) -> dict[str, Any]:
        token = _extract_request_token(request)
        if not token:
            raise HTTPException(
                status_code=401,
                detail={"code": "AUTH_REQUIRED", "message": "Phiên làm việc chưa xác thực hoặc đã hết hạn 15 phút."},
            )
        try:
            raw_claims = decode_access_token(cfg, token)
        except Exception as exc:
            raise HTTPException(
                status_code=401,
                detail={"code": "INVALID_OR_EXPIRED_TOKEN", "message": "Phiên xác thực không hợp lệ hoặc đã hết hạn."},
            ) from exc

        snap = store.read_snapshot()
        try:
            return validate_live_session_claims(raw_claims, snap)
        except SessionRevokedError as exc:
            raise HTTPException(
                status_code=401,
                detail={"code": exc.code, "message": exc.message},
            ) from exc

    def require_superadmin(claims: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if claims.get("role") != "superadmin":
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "SUPERADMIN_REQUIRED",
                    "message": "Chức năng này chỉ dành riêng cho tài khoản Superadmin (BSCKII. Vũ Khương An).",
                },
            )
        return claims

    def _set_auth_cookie(response: Response, token: str, ttl: int) -> None:
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            max_age=ttl,
            httponly=True,
            samesite="strict",
            secure=(cfg.env_mode == "production"),
            path="/",
        )

    # 1. GET /api/health
    @app.get("/api/health")
    def healthcheck() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": __version__,
            "env_mode": cfg.env_mode,
            "local_bypass_candidate": cfg.env_mode == "local_dev_synthetic" and cfg.enable_dev_bypass,
        }

    # 2. POST /api/auth/login
    @app.post("/api/auth/login")
    def login(body: LoginRequest, response: Response) -> dict[str, Any]:
        snap = store.read_snapshot()
        user = snap["users"].get(body.username.strip())
        if not user or not user.get("active") or not verify_password(user["password_hash"], body.password):
            raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu không đúng.")
        store_epoch = int(snap.get("store_epoch", 1) or 1)
        auth_ver = int(user.get("auth_version", 1) or 1)
        token, ttl = create_access_token(
            cfg,
            username=user["username"],
            role=user["role"],
            display_name=user["display_name"],
            department=user["department"],
            auth_ver=auth_ver,
            store_epoch=store_epoch,
        )
        now_ts = int(dt.datetime.now(dt.timezone.utc).timestamp())

        def _mut_login(st: dict[str, Any]) -> None:
            st["revoked_jtis"] = prune_expired_revoked_jtis(st.get("revoked_jtis"), now_ts=now_ts)
            st["audit_chain"].append(
                build_audit_entry(
                    st["audit_chain"],
                    actor_username=user["username"],
                    actor_role=user["role"],
                    action="AUTH_LOGIN_SUCCESS",
                    entity_type="SESSION",
                    entity_id=user["username"],
                    detail={"method": "password_argon2id", "store_epoch": store_epoch},
                )
            )

        store.transact(_mut_login)
        _set_auth_cookie(response, token, ttl)
        return {
            "authenticated": True,
            "user": {
                "username": user["username"],
                "display_name": user["display_name"],
                "role": user["role"],
                "department": user["department"],
            },
            "store_epoch": store_epoch,
            "expires_in_seconds": ttl,
            "env_mode": cfg.env_mode,
        }

    # 3. POST /api/auth/local-bypass
    @app.post("/api/auth/local-bypass")
    def local_bypass(
        request: Request,
        response: Response,
        body: LocalBypassRequest | None = None,
    ) -> dict[str, Any]:
        client_ip = request.client.host if request.client else None
        allowed, reason_code = evaluate_local_bypass_gate(
            cfg,
            client_ip=client_ip,
            headers=request.headers,
        )
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail={"code": reason_code, "message": "Local dev bypass bị khóa theo chính sách Fail-Closed."},
            )
        target_user = (body.target_username if body else "nguyenbinhan").strip()
        snap = store.read_snapshot()
        user = snap["users"].get(target_user) or snap["users"]["nguyenbinhan"]
        if not user.get("active"):
            raise HTTPException(status_code=403, detail={"code": "USER_INACTIVE", "message": "Tài khoản không hoạt động."})
        store_epoch = int(snap.get("store_epoch", 1) or 1)
        auth_ver = int(user.get("auth_version", 1) or 1)
        token, ttl = create_access_token(
            cfg,
            username=user["username"],
            role=user["role"],
            display_name=user["display_name"],
            department=user["department"],
            auth_ver=auth_ver,
            store_epoch=store_epoch,
        )
        store.transact(
            lambda st: st["audit_chain"].append(
                build_audit_entry(
                    st["audit_chain"],
                    actor_username=user["username"],
                    actor_role=user["role"],
                    action="AUTH_LOCAL_DEV_BYPASS",
                    entity_type="SESSION",
                    entity_id=user["username"],
                    detail={"env_mode": cfg.env_mode, "gate": reason_code, "store_epoch": store_epoch},
                )
            )
        )
        _set_auth_cookie(response, token, ttl)
        return {
            "authenticated": True,
            "gate_code": reason_code,
            "user": {
                "username": user["username"],
                "display_name": user["display_name"],
                "role": user["role"],
                "department": user["department"],
            },
            "store_epoch": store_epoch,
            "expires_in_seconds": ttl,
            "env_mode": cfg.env_mode,
        }

    # 4. POST /api/auth/logout
    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response) -> dict[str, Any]:
        token = _extract_request_token(request)
        if token:
            try:
                raw_claims = decode_access_token(cfg, token)
                jti = str(raw_claims.get("jti") or "").strip()
                now_ts = int(dt.datetime.now(dt.timezone.utc).timestamp())
                exp_ts = int(raw_claims.get("exp") or (now_ts + cfg.session_timeout_seconds))
                sub = str(raw_claims.get("sub") or "system")
                role = str(raw_claims.get("role") or "endoscopist")
                if jti:
                    def _mut_logout(st: dict[str, Any]) -> None:
                        pruned = prune_expired_revoked_jtis(st.get("revoked_jtis"), now_ts=now_ts)
                        already_revoked = jti in pruned
                        pruned[jti] = exp_ts
                        st["revoked_jtis"] = pruned
                        if not already_revoked:
                            live_u = (st.get("users") or {}).get(sub)
                            eff_role = str(live_u["role"]) if isinstance(live_u, dict) and live_u.get("role") else role
                            st["audit_chain"].append(
                                build_audit_entry(
                                    st["audit_chain"],
                                    actor_username=sub,
                                    actor_role=eff_role,
                                    action="AUTH_LOGOUT",
                                    entity_type="SESSION",
                                    entity_id=sub,
                                    detail={"session_revoked": True},
                                )
                            )

                    store.transact(_mut_logout)
            except Exception:
                pass
        response.delete_cookie(COOKIE_NAME, path="/")
        return {"authenticated": False}

    # 5. GET /api/auth/me
    @app.get("/api/auth/me")
    def auth_me(claims: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        now_ts = int(dt.datetime.now(dt.timezone.utc).timestamp())
        return {
            "authenticated": True,
            "user": {
                "username": claims["sub"],
                "display_name": claims["display_name"],
                "role": claims["role"],
                "department": claims["department"],
            },
            "store_epoch": int(claims["store_epoch"]),
            "remaining_seconds": max(0, int(claims["exp"]) - now_ts),
            "env_mode": cfg.env_mode,
        }

    # 6. POST /api/auth/change-password
    @app.post("/api/auth/change-password")
    def change_password_endpoint(
        body: PasswordChangeRequest,
        response: Response,
        claims: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        try:
            res = svc.change_own_password(actor_username=claims["sub"], req=body)
        except InvalidPasswordError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        except DomainValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản hiện tại.") from exc

        updated_user = res["user"]
        token, ttl = create_access_token(
            cfg,
            username=updated_user["username"],
            role=updated_user["role"],
            display_name=updated_user["display_name"],
            department=updated_user["department"],
            auth_ver=int(updated_user["auth_version"]),
            store_epoch=int(res["store_epoch"]),
        )
        _set_auth_cookie(response, token, ttl)
        return {
            "password_changed": True,
            "user": updated_user,
            "store_epoch": int(res["store_epoch"]),
            "expires_in_seconds": ttl,
        }

    # 7. GET /api/cases
    @app.get("/api/cases")
    def list_cases(
        track: str | None = Query(default=None),
        claims: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        _ = claims
        items = svc.list_enriched_cases(track=track)
        snap = store.read_snapshot()
        return {
            "items": items,
            "total": len(items),
            "store_epoch": int(snap.get("store_epoch", 1) or 1),
            "settings": snap["settings"],
        }

    # 8. POST /api/cases
    @app.post("/api/cases", status_code=201)
    def create_case_endpoint(
        req: CaseCreateRequest,
        response: Response,
        claims: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        try:
            created = svc.create_case(
                req,
                actor_username=claims["sub"],
                actor_role=claims["role"],
            )
        except DlpViolationError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": exc.rule_code, "field": exc.field_path, "message": str(exc)},
            ) from exc
        except DomainValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        except DomainConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": exc.code, "message": exc.message, **exc.extra},
            ) from exc
        except DuplicateOutpatientConfirmationRequired as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "OUTPATIENT_POTENTIAL_DUPLICATE_CONFIRM_REQUIRED",
                    "candidates": exc.candidates,
                },
            ) from exc
        response.headers["ETag"] = created["etag"]
        return created

    def _parse_if_match_header(
        raw_if_match: str,
        *,
        expected_version: int | None = None,
    ) -> tuple[int | None, int | None]:
        cleaned = (raw_if_match or "").strip()
        if not cleaned or cleaned == "*":
            return None, None
        m_new = re.fullmatch(r'(?:W/)?"?e(\d+):v(\d+)"?', cleaned)
        if m_new:
            hdr_epoch = int(m_new.group(1))
            hdr_ver = int(m_new.group(2))
            if expected_version is not None and hdr_ver != int(expected_version):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "OCC_VERSION_CONFLICT",
                        "message": f"Header If-Match ({cleaned}) không khớp với expected_version (v{expected_version}).",
                    },
                )
            return hdr_epoch, hdr_ver
        m_legacy = re.fullmatch(r'(?:W/)?"?v?(\d+)"?', cleaned)
        if not m_legacy:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "OCC_VERSION_CONFLICT",
                    "message": f"Định dạng header If-Match ({cleaned}) không hợp lệ.",
                },
            )
        hdr_ver = int(m_legacy.group(1))
        if expected_version is not None and hdr_ver != int(expected_version):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "OCC_VERSION_CONFLICT",
                    "message": f"Header If-Match ({cleaned}) không khớp với expected_version (v{expected_version}).",
                },
            )
        return 1, hdr_ver

    # 9. PATCH /api/cases/{case_id}
    @app.patch("/api/cases/{case_id}")
    def patch_case_endpoint(
        case_id: str,
        patch: CasePhasePatchRequest,
        request: Request,
        response: Response,
        claims: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        if_match_epoch, _ = _parse_if_match_header(
            request.headers.get("if-match") or "",
            expected_version=int(patch.expected_version),
        )

        try:
            updated = svc.patch_case(
                case_id,
                patch,
                actor_username=claims["sub"],
                actor_role=claims["role"],
                if_match_epoch=if_match_epoch,
            )
        except DlpViolationError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": exc.rule_code, "field": exc.field_path, "message": str(exc)},
            ) from exc
        except DomainValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        except DomainConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": exc.code, "message": exc.message, **exc.extra},
            ) from exc
        except ConcurrencyConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "OCC_VERSION_CONFLICT", "message": str(exc)},
            ) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        response.headers["ETag"] = updated["etag"]
        return updated

    # 10. DELETE /api/cases/{case_id}
    @app.delete("/api/cases/{case_id}")
    def supersede_case_endpoint(
        case_id: str,
        request: Request,
        claims: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        if claims.get("role") != "superadmin":
            raise HTTPException(
                status_code=403,
                detail="Chỉ Superadmin (BSCKII. Vũ Khương An) có thẩm quyền hủy hiệu lực hồ sơ ca soi.",
            )
        if_match_epoch, if_match_version = _parse_if_match_header(
            request.headers.get("if-match") or "",
        )
        try:
            return svc.supersede_case(
                case_id,
                actor_username=claims["sub"],
                actor_role=claims["role"],
                if_match_epoch=if_match_epoch,
                if_match_version=if_match_version,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except DomainConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": exc.code, "message": exc.message, **exc.extra},
            ) from exc
        except ConcurrencyConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "OCC_VERSION_CONFLICT", "message": str(exc)},
            ) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    # 11. GET /api/surveillance
    @app.get("/api/surveillance")
    def get_surveillance_board(
        claims: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        _ = claims
        cases = svc.list_enriched_cases()
        today_iso = dt.date.today().isoformat()
        soon_iso = (dt.date.today() + dt.timedelta(days=30)).isoformat()
        rows = []
        for c in cases:
            surv = c["surveillance"]
            due = surv.get("due_date")
            if surv["category"] == "SURGICAL_MDT_CONSULT_ALERT":
                urgency_tone = "urgent"
                urgency_label = f"Cảnh báo hội chẩn {surv['surgical_consult_target_dept']}"
            elif surv["status"] == "PENDING_GPB":
                urgency_tone = "pending"
                urgency_label = "Chờ GPB"
            elif surv["status"] == "COMPLETED_LINKED":
                urgency_tone = "ned"
                urgency_label = "Không biến cố / hoàn tất"
            elif due and due <= soon_iso:
                urgency_tone = "due"
                urgency_label = "Quá hạn hẹn soi lại" if due < today_iso else "Đến hạn soi lại"
            else:
                urgency_tone = "neutral"
                urgency_label = "Chưa đến hạn"

            rows.append(
                {
                    "case_id": c["case_id"],
                    "case_code": c["case_code"],
                    "track": c["track"],
                    "procedure_date": c["procedure_start_at"][:10],
                    "patient": c["patient"],
                    "indication_detail": c.get("indication_detail") or c.get("indication"),
                    "pathology_completion_status": c.get("pathology_completion_status"),
                    "surveillance": surv,
                    "urgency": {"tone": urgency_tone, "label": urgency_label},
                }
            )
        tone_priority = {"urgent": 0, "due": 1, "pending": 2, "neutral": 3, "ned": 4}
        rows.sort(key=lambda r: (tone_priority.get(r["urgency"]["tone"], 9), r["surveillance"].get("due_date") or "9999"))
        return {"items": rows, "total": len(rows)}

    # 12. GET /api/metrics/kpi
    @app.get("/api/metrics/kpi")
    def get_kpi_metrics(
        min_adr_age: int | None = Query(default=None),
        claims: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        _ = claims
        snap = store.read_snapshot()
        effective_age = int(min_adr_age or snap["settings"].get("adr_min_age", 45))
        if effective_age not in (45, 50):
            raise HTTPException(status_code=422, detail="Ngưỡng tuổi ADR chỉ hỗ trợ 45 hoặc 50.")
        effective_n_min = max(1, int(snap["settings"].get("kpi_min_sample_size", cfg.kpi_min_sample_size)))
        kpi = compute_kpi_snapshot(
            list(snap["cases"].values()),
            patients_by_id=snap["patients"],
            min_adr_age=effective_age,
            n_min=effective_n_min,
        )
        cusum_cir = build_cusum_series_from_cases(
            list(snap["cases"].values()),
            metric="CIR",
            preset=snap["settings"].get("cusum_preset", "DEFAULT_90"),
        )
        cusum_ercp = build_cusum_series_from_cases(
            list(snap["cases"].values()),
            metric="ERCP_NATIVE",
            preset="DEFAULT_90",
        )
        return {
            "kpi": kpi,
            "cusum_cir": cusum_cir,
            "cusum_ercp": cusum_ercp,
            "colo_guideline_mode": snap["settings"].get("colo_guideline_mode", "USMSTF_2020"),
            "kpi_min_sample_size": effective_n_min,
        }

    # 13. GET /api/metrics/cusum
    @app.get("/api/metrics/cusum")
    def get_cusum_endpoint(
        metric: str = Query(default="CIR"),
        preset: str = Query(default="DEFAULT_90"),
        claims: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        _ = claims
        snap = store.read_snapshot()
        return build_cusum_series_from_cases(
            list(snap["cases"].values()),
            metric=metric,
            preset=preset,
        )

    # 14. GET /api/audit/verify
    @app.get("/api/audit/verify")
    def verify_audit_endpoint(
        claims: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        _ = claims
        snap = store.read_snapshot()
        verification = verify_audit_chain(snap["audit_chain"])
        lineage_ver = verify_audit_lineage_bridges(
            snap.get("audit_lineage_bridges", []),
            backup_dir=cfg.backup_dir,
        )
        return {
            "store_epoch": int(snap.get("store_epoch", 1) or 1),
            "verification": verification,
            "audit_lineage_bridges": lineage_ver["items"],
            "lineage_verification": {
                "valid": lineage_ver["valid"],
                "bridge_count": lineage_ver["bridge_count"],
            },
            "recent_entries": list(reversed(snap["audit_chain"][-20:])),
        }

    # 15. GET /api/settings
    @app.get("/api/settings")
    def get_settings_endpoint(
        claims: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        _ = claims
        snap = store.read_snapshot()
        return {
            **snap["settings"],
            "store_epoch": int(snap.get("store_epoch", 1) or 1),
        }

    # 16. PATCH /api/settings
    @app.patch("/api/settings")
    def update_settings_endpoint(
        patch: SettingsPatchRequest,
        claims: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        if claims.get("role") != "superadmin" and (
            patch.kpi_min_sample_size is not None or patch.cusum_preset is not None
        ):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "SUPERADMIN_REQUIRED_FOR_STATISTICAL_SETTINGS",
                    "message": "Chỉ Superadmin (BSCKII. Vũ Khương An) được hiệu chỉnh ngưỡng cỡ mẫu tối thiểu và tham số CUSUM.",
                },
            )

        def _mut(st: dict[str, Any]) -> dict[str, Any]:
            if patch.colo_guideline_mode in ("USMSTF_2020", "ESGE_2020"):
                st["settings"]["colo_guideline_mode"] = patch.colo_guideline_mode
            if patch.adr_min_age in (45, 50):
                st["settings"]["adr_min_age"] = patch.adr_min_age
            if claims.get("role") == "superadmin":
                if patch.cusum_preset in ("DEFAULT_90", "SCREENING_CIR_95"):
                    st["settings"]["cusum_preset"] = patch.cusum_preset
                if patch.kpi_min_sample_size is not None:
                    st["settings"]["kpi_min_sample_size"] = int(patch.kpi_min_sample_size)
            st["audit_chain"].append(
                build_audit_entry(
                    st["audit_chain"],
                    actor_username=claims["sub"],
                    actor_role=claims["role"],
                    action="SETTINGS_UPDATE",
                    entity_type="SETTINGS",
                    entity_id="global",
                    detail=dict(st["settings"]),
                )
            )
            return {
                **st["settings"],
                "store_epoch": int(st.get("store_epoch", 1) or 1),
            }

        return store.transact(_mut)

    # 17. POST /api/exports/profile-a
    @app.post("/api/exports/profile-a")
    def export_profile_a_endpoint(
        body: ProfileABackupRequest,
        claims: dict[str, Any] = Depends(require_superadmin),
    ) -> Response:
        snap = store.read_snapshot()
        ds_epoch = int((snap.get("settings") or {}).get("export_dataset_epoch", 1) or 1)
        crypto_ctx = cfg.build_crypto_context(ds_epoch)
        blob = export_profile_a_encrypted_vault(snap, body.passphrase, crypto_context=crypto_ctx)
        store.transact(
            lambda st: st["audit_chain"].append(
                build_audit_entry(
                    st["audit_chain"],
                    actor_username=claims["sub"],
                    actor_role=claims["role"],
                    action="EXPORT_PROFILE_A_ENCRYPTED",
                    entity_type="EXPORT",
                    entity_id="profile_a",
                    detail={
                        "bytes": len(blob),
                        "store_epoch": int(st.get("store_epoch", 1) or 1),
                        "export_dataset_epoch": ds_epoch,
                    },
                )
            )
        )
        return Response(
            content=blob,
            media_type="application/octet-stream",
            headers={"Content-Disposition": 'attachment; filename="endolog_vault_backup.endolog.enc"'},
        )

    # 18. GET /api/exports/profile-b
    @app.get("/api/exports/profile-b")
    def export_profile_b_endpoint(
        fmt: str = Query(default="csv"),
        track: str | None = Query(default=None),
        scope_id: str = Query(default="endolog_bvbd_v1"),
        claims: dict[str, Any] = Depends(get_current_user),
    ) -> Response:
        snap = store.read_snapshot()
        ds_epoch = int((snap.get("settings") or {}).get("export_dataset_epoch", 1) or 1)
        lineage_seq = int((snap.get("settings") or {}).get("profile_b_lineage_seq", 1) or 1)
        rows = export_profile_b_rows(
            snap,
            master_key=cfg.master_research_key,
            shift_key=cfg.shift_key,
            scope_id=scope_id,
            track_filter=track,
        )
        store.transact(
            lambda st: st["audit_chain"].append(
                build_audit_entry(
                    st["audit_chain"],
                    actor_username=claims["sub"],
                    actor_role=claims["role"],
                    action="EXPORT_PROFILE_B_PSEUDONYMIZED",
                    entity_type="EXPORT",
                    entity_id="profile_b",
                    detail={
                        "fmt": fmt,
                        "row_count": len(rows),
                        "scope_id": scope_id,
                        "export_dataset_epoch": ds_epoch,
                        "profile_b_lineage_seq": lineage_seq,
                    },
                )
            )
        )
        meta_headers = {
            "X-EndoLog-Dataset-Epoch": str(ds_epoch),
            "X-EndoLog-Lineage-Seq": str(lineage_seq),
        }
        if fmt == "xlsx":
            payload = rows_to_xlsx_bytes(rows, sheet_title="EndoLog_Profile_B")
            return Response(
                content=payload,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": 'attachment; filename="endolog_profile_b_longitudinal.xlsx"',
                    **meta_headers,
                },
            )
        payload_csv = rows_to_csv_bytes(rows)
        return Response(
            content=payload_csv,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="endolog_profile_b_longitudinal.csv"',
                **meta_headers,
            },
        )

    # 19. GET /api/exports/profile-c
    @app.get("/api/exports/profile-c")
    def export_profile_c_endpoint(
        suppress_small_cells: bool = Query(default=True),
        claims: dict[str, Any] = Depends(get_current_user),
    ) -> JSONResponse:
        snap = store.read_snapshot()
        summary = export_profile_c_summary(
            snap,
            min_adr_age=int(snap["settings"].get("adr_min_age", 45)),
            suppress_small_cells=suppress_small_cells,
        )
        store.transact(
            lambda st: st["audit_chain"].append(
                build_audit_entry(
                    st["audit_chain"],
                    actor_username=claims["sub"],
                    actor_role=claims["role"],
                    action="EXPORT_PROFILE_C_AGGREGATE",
                    entity_type="EXPORT",
                    entity_id="profile_c",
                    detail={"suppress_small_cells": suppress_small_cells},
                )
            )
        )
        return JSONResponse(content=summary)

    # 20. POST /api/admin/restore-profile-a
    @app.post("/api/admin/restore-profile-a")
    async def restore_profile_a_endpoint(
        request: Request,
        response: Response,
        claims: dict[str, Any] = Depends(require_superadmin),
    ) -> dict[str, Any]:
        cl_header = request.headers.get("content-length")
        if cl_header:
            try:
                if int(cl_header) > MAX_RESTORE_HTTP_BODY_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail={
                            "code": "VAULT_PAYLOAD_TOO_LARGE",
                            "message": "Dữ liệu tải lên vượt ngưỡng cho phép 10 MiB của Hồ sơ A.",
                        },
                    )
            except ValueError:
                pass

        chunks: list[bytes] = []
        total_read = 0
        async for chunk in request.stream():
            total_read += len(chunk)
            if total_read > MAX_RESTORE_HTTP_BODY_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail={
                        "code": "VAULT_PAYLOAD_TOO_LARGE",
                        "message": "Dữ liệu tải lên vượt ngưỡng cho phép 10 MiB của Hồ sơ A.",
                    },
                )
            chunks.append(chunk)
        raw_body = b"".join(chunks)

        try:
            parsed_json = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_RESTORE_REQUEST_JSON", "message": "Nội dung yêu cầu khôi phục không phải JSON hợp lệ."},
            ) from exc

        try:
            restore_req = ProfileARestoreRequest.model_validate(parsed_json)
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_RESTORE_REQUEST_SCHEMA", "message": "Tham số yêu cầu khôi phục không hợp lệ."},
            ) from exc

        try:
            result = svc.restore_profile_a_vault(
                restore_req,
                actor_username=claims["sub"],
                actor_role=claims["role"],
            )
        except VaultPayloadTooLargeError as exc:
            raise HTTPException(
                status_code=413,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        except VaultDecryptError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        except (VaultSchemaValidationError, DomainValidationError) as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        except DomainConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": exc.code, "message": exc.message, **exc.extra},
            ) from exc
        except OSError as exc:
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "PRE_RESTORE_BACKUP_IO_ERROR",
                    "message": "Không thể ghi bản sao lưu dự phòng pre_restore trước khôi phục; đã hủy giao dịch để bảo toàn dữ liệu hiện hành.",
                },
            ) from exc

        if result.get("reauthentication_required") or not result.get("actor_user"):
            response.delete_cookie(COOKIE_NAME, path="/")
        else:
            actor_u = result["actor_user"]
            token, ttl = create_access_token(
                cfg,
                username=actor_u["username"],
                role=actor_u["role"],
                display_name=actor_u["display_name"],
                department=actor_u["department"],
                auth_ver=int(actor_u["auth_version"]),
                store_epoch=int(result["new_store_epoch"]),
            )
            _set_auth_cookie(response, token, ttl)
            result["expires_in_seconds"] = ttl

        return result

    # 21. GET /api/admin/patients
    @app.get("/api/admin/patients")
    def admin_list_patients_endpoint(
        claims: dict[str, Any] = Depends(require_superadmin),
    ) -> dict[str, Any]:
        return svc.list_admin_patients(actor_role=claims["role"])

    # 22. POST /api/admin/patients/merge
    @app.post("/api/admin/patients/merge")
    def admin_merge_patients_endpoint(
        body: PatientMergeRequest,
        claims: dict[str, Any] = Depends(require_superadmin),
    ) -> dict[str, Any]:
        try:
            return svc.merge_patients(
                body,
                actor_username=claims["sub"],
                actor_role=claims["role"],
            )
        except DlpViolationError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": exc.rule_code, "field": exc.field_path, "message": str(exc)},
            ) from exc
        except DomainValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        except DomainConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": exc.code, "message": exc.message, **exc.extra},
            ) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    # 23. POST /api/admin/episodes/reconcile
    @app.post("/api/admin/episodes/reconcile")
    def admin_reconcile_episodes_endpoint(
        body: EpisodeReconcileRequest,
        claims: dict[str, Any] = Depends(require_superadmin),
    ) -> dict[str, Any]:
        try:
            return svc.reconcile_episodes(
                body,
                actor_username=claims["sub"],
                actor_role=claims["role"],
            )
        except DlpViolationError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": exc.rule_code, "field": exc.field_path, "message": str(exc)},
            ) from exc
        except DomainValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        except DomainConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": exc.code, "message": exc.message, **exc.extra},
            ) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    # 24. GET /api/admin/users
    @app.get("/api/admin/users")
    def admin_list_users_endpoint(
        claims: dict[str, Any] = Depends(require_superadmin),
    ) -> dict[str, Any]:
        return svc.list_users_sanitized(actor_role=claims["role"])

    # 25. POST /api/admin/users/{username}/reset-password
    @app.post("/api/admin/users/{username}/reset-password")
    def admin_reset_password_endpoint(
        username: str,
        body: AdminPasswordResetRequest,
        response: Response,
        claims: dict[str, Any] = Depends(require_superadmin),
    ) -> dict[str, Any]:
        try:
            res = svc.admin_reset_user_password(
                username,
                body,
                actor_username=claims["sub"],
                actor_role=claims["role"],
            )
        except DlpViolationError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": exc.rule_code, "field": exc.field_path, "message": str(exc)},
            ) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản cần đặt lại mật khẩu.") from exc

        if res.get("actor_self_reset"):
            target_u = res["target_user"]
            token, ttl = create_access_token(
                cfg,
                username=target_u["username"],
                role=target_u["role"],
                display_name=target_u["display_name"],
                department=target_u["department"],
                auth_ver=int(target_u["auth_version"]),
                store_epoch=int(res["store_epoch"]),
            )
            _set_auth_cookie(response, token, ttl)

        return {
            "password_reset": True,
            "target_user": res["target_user"],
            "store_epoch": int(res["store_epoch"]),
        }

    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    return app


def create_default_app() -> FastAPI:
    return create_app()
