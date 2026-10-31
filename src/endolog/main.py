"""FastAPI application entrypoint for EndoLog with strict CSP, Zero-PHI HTTP headers, and 5-latch local bypass."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from endolog import __version__
from endolog.api.service import (
    ConcurrencyConflictError,
    DuplicateOutpatientConfirmationRequired,
    EndoLogService,
)
from endolog.clinical.cusum import build_cusum_series_from_cases
from endolog.clinical.export_profiles import (
    export_profile_a_encrypted_vault,
    export_profile_b_rows,
    export_profile_c_summary,
    rows_to_csv_bytes,
    rows_to_xlsx_bytes,
)
from endolog.clinical.quality_metrics import compute_kpi_snapshot
from endolog.core.audit import build_audit_entry, verify_audit_chain
from endolog.core.config import EndoLogSettings, load_settings
from endolog.core.dlp import DlpViolationError
from endolog.core.persistence import AtomicJsonStore
from endolog.core.security import (
    COOKIE_NAME,
    create_access_token,
    decode_access_token,
    evaluate_local_bypass_gate,
    verify_password,
)
from endolog.core.seed_od05 import build_od05_synthetic_vignettes
from endolog.schemas.clinical import CaseCreateRequest, CasePhasePatchRequest


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class LocalBypassRequest(BaseModel):
    target_username: str = "nguyenbinhan"


class SettingsPatchRequest(BaseModel):
    colo_guideline_mode: str | None = None
    adr_min_age: int | None = None
    cusum_preset: str | None = None
    kpi_min_sample_size: int | None = Field(default=None, ge=1, le=500)


class ProfileABackupRequest(BaseModel):
    passphrase: str = Field(..., min_length=12, max_length=128)


STATIC_DIR = Path(__file__).resolve().parent / "static"


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
        token = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
        if not token:
            token = request.cookies.get(COOKIE_NAME)
        if not token:
            raise HTTPException(status_code=401, detail="Phiên làm việc chưa xác thực hoặc đã hết hạn 15 phút.")
        try:
            claims = decode_access_token(cfg, token)
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Phiên xác thực không hợp lệ hoặc đã hết hạn.") from exc
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

    @app.get("/api/health")
    def healthcheck() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": __version__,
            "env_mode": cfg.env_mode,
            "local_bypass_candidate": cfg.env_mode == "local_dev_synthetic" and cfg.enable_dev_bypass,
        }

    @app.post("/api/auth/login")
    def login(body: LoginRequest, response: Response) -> dict[str, Any]:
        snap = store.read_snapshot()
        user = snap["users"].get(body.username.strip())
        if not user or not user.get("active") or not verify_password(user["password_hash"], body.password):
            raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu không đúng.")
        token, ttl = create_access_token(
            cfg,
            username=user["username"],
            role=user["role"],
            display_name=user["display_name"],
            department=user["department"],
        )
        store.transact(
            lambda st: st["audit_chain"].append(
                build_audit_entry(
                    st["audit_chain"],
                    actor_username=user["username"],
                    actor_role=user["role"],
                    action="AUTH_LOGIN_SUCCESS",
                    entity_type="SESSION",
                    entity_id=user["username"],
                    detail={"method": "password_argon2id"},
                )
            )
        )
        _set_auth_cookie(response, token, ttl)
        return {
            "authenticated": True,
            "user": {
                "username": user["username"],
                "display_name": user["display_name"],
                "role": user["role"],
                "department": user["department"],
            },
            "expires_in_seconds": ttl,
            "env_mode": cfg.env_mode,
        }

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
        token, ttl = create_access_token(
            cfg,
            username=user["username"],
            role=user["role"],
            display_name=user["display_name"],
            department=user["department"],
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
                    detail={"env_mode": cfg.env_mode, "gate": reason_code},
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
            "expires_in_seconds": ttl,
            "env_mode": cfg.env_mode,
        }

    @app.post("/api/auth/logout")
    def logout(response: Response) -> dict[str, Any]:
        response.delete_cookie(COOKIE_NAME, path="/")
        return {"authenticated": False}

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
            "remaining_seconds": max(0, int(claims["exp"]) - now_ts),
            "env_mode": cfg.env_mode,
        }

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
            "settings": snap["settings"],
        }

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

    @app.patch("/api/cases/{case_id}")
    def patch_case_endpoint(
        case_id: str,
        patch: CasePhasePatchRequest,
        request: Request,
        response: Response,
        claims: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        if_match = (request.headers.get("if-match") or "").strip()
        if if_match and if_match != "*":
            m = re.search(r"v?(\d+)", if_match)
            if not m or int(m.group(1)) != int(patch.expected_version):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "OCC_VERSION_CONFLICT",
                        "message": f"Header If-Match ({if_match}) không khớp với expected_version (v{patch.expected_version}).",
                    },
                )
        try:
            updated = svc.patch_case(
                case_id,
                patch,
                actor_username=claims["sub"],
                actor_role=claims["role"],
            )
        except DlpViolationError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": exc.rule_code, "field": exc.field_path, "message": str(exc)},
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

    @app.delete("/api/cases/{case_id}")
    def supersede_case_endpoint(
        case_id: str,
        claims: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        try:
            return svc.supersede_case(
                case_id,
                actor_username=claims["sub"],
                actor_role=claims["role"],
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

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

    @app.get("/api/audit/verify")
    def verify_audit_endpoint(
        claims: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        _ = claims
        snap = store.read_snapshot()
        verification = verify_audit_chain(snap["audit_chain"])
        return {
            "verification": verification,
            "recent_entries": list(reversed(snap["audit_chain"][-20:])),
        }

    @app.get("/api/settings")
    def get_settings_endpoint(
        claims: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        _ = claims
        return store.read_snapshot()["settings"]

    @app.patch("/api/settings")
    def update_settings_endpoint(
        patch: SettingsPatchRequest,
        claims: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        def _mut(st: dict[str, Any]) -> dict[str, Any]:
            if patch.colo_guideline_mode in ("USMSTF_2020", "ESGE_2020"):
                st["settings"]["colo_guideline_mode"] = patch.colo_guideline_mode
            if patch.adr_min_age in (45, 50):
                st["settings"]["adr_min_age"] = patch.adr_min_age
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
                    detail=st["settings"],
                )
            )
            return st["settings"]

        return store.transact(_mut)

    @app.post("/api/exports/profile-a")
    def export_profile_a_endpoint(
        body: ProfileABackupRequest,
        claims: dict[str, Any] = Depends(get_current_user),
    ) -> Response:
        if claims["role"] != "superadmin":
            raise HTTPException(
                status_code=403,
                detail="Profile A (Sao lưu mã hóa chứa PHI gốc) chỉ dành riêng cho Superadmin (BSCKII. Vũ Khương An).",
            )
        snap = store.read_snapshot()
        blob = export_profile_a_encrypted_vault(snap, body.passphrase)
        store.transact(
            lambda st: st["audit_chain"].append(
                build_audit_entry(
                    st["audit_chain"],
                    actor_username=claims["sub"],
                    actor_role=claims["role"],
                    action="EXPORT_PROFILE_A_ENCRYPTED",
                    entity_type="EXPORT",
                    entity_id="profile_a",
                    detail={"bytes": len(blob)},
                )
            )
        )
        return Response(
            content=blob,
            media_type="application/octet-stream",
            headers={"Content-Disposition": 'attachment; filename="endolog_vault_backup.endolog.enc"'},
        )

    @app.get("/api/exports/profile-b")
    def export_profile_b_endpoint(
        fmt: str = Query(default="csv"),
        track: str | None = Query(default=None),
        scope_id: str = Query(default="endolog_bvbd_v1"),
        claims: dict[str, Any] = Depends(get_current_user),
    ) -> Response:
        snap = store.read_snapshot()
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
                    detail={"fmt": fmt, "row_count": len(rows), "scope_id": scope_id},
                )
            )
        )
        if fmt == "xlsx":
            payload = rows_to_xlsx_bytes(rows, sheet_title="EndoLog_Profile_B")
            return Response(
                content=payload,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": 'attachment; filename="endolog_profile_b_longitudinal.xlsx"'},
            )
        payload_csv = rows_to_csv_bytes(rows)
        return Response(
            content=payload_csv,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="endolog_profile_b_longitudinal.csv"'},
        )

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

    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    return app


def create_default_app() -> FastAPI:
    return create_app()
