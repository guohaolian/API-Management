"""Mock 服务层：按 API 定义生成示例响应，支持正式版、历史版本与迭代草稿。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import unquote

from sqlalchemy.orm import Session

from database.models import Api, ApiDraft, Service, ServiceIteration, User
from services.mock_engine import (
    build_default_request_values,
    generate_mock_body,
    match_api_path,
)
from services.utils import organizeReqParams, organizeRespParams


def _check_api_access(
    db: Session,
    api: Api | ApiDraft,
    user_id: int,
    is_latest: bool,
) -> Optional[dict]:
    user = db.get(User, user_id)
    if not user:
        return {"status": -2, "message": "User not found"}

    if user.level.value != 0:
        if is_latest:
            service = api.service
            if service.owner_id != user_id and user not in service.maintainers:
                return {
                    "status": -3,
                    "message": "You are neither the owner nor the maintainer of this service",
                }
        else:
            iteration = api.service_iteration
            service = iteration.service
            if (
                iteration.creator_id != user_id
                and user not in service.maintainers
                and service.owner_id != user_id
            ):
                return {
                    "status": -4,
                    "message": "You are neither the owner nor the maintainer of this service, nor the creator of this service iteration",
                }
    return None


def _resolve_service_context(
    db: Session,
    service_uuid: str,
    version: Optional[str],
    service_iteration_id: Optional[int],
) -> dict:
    service_uuid = unquote(service_uuid).strip()
    curr_service = (
        db.query(Service)
        .filter(Service.service_uuid == service_uuid, ~Service.is_deleted)
        .first()
    )
    if not curr_service:
        return {"status": -1, "message": "Service not found"}

    if service_iteration_id is not None:
        iteration = db.get(ServiceIteration, service_iteration_id)
        if not iteration or iteration.service_id != curr_service.id:
            return {"status": -5, "message": "Service iteration not found"}
        return {
            "status": 200,
            "curr_service": curr_service,
            "entity": iteration,
            "is_latest": False,
            "apis": iteration.api_drafts,
        }

    version = (version or "latest").strip()
    if curr_service.version == version or version == "latest":
        return {
            "status": 200,
            "curr_service": curr_service,
            "entity": curr_service,
            "is_latest": True,
            "apis": curr_service.apis,
        }

    iteration = (
        db.query(ServiceIteration)
        .filter(
            ServiceIteration.service_id == curr_service.id,
            ServiceIteration.version == version,
        )
        .first()
    )
    if not iteration:
        return {"status": -2, "message": "Service version not found"}

    return {
        "status": 200,
        "curr_service": curr_service,
        "entity": iteration,
        "is_latest": False,
        "apis": iteration.api_drafts,
    }


def _check_service_access(
    db: Session,
    curr_service: Service,
    entity: Service | ServiceIteration,
    user_id: int,
    is_latest: bool,
) -> Optional[dict]:
    user = db.get(User, user_id)
    if not user:
        return {"status": -2, "message": "User not found"}

    if user.level.value != 0:
        if curr_service.owner_id != user_id and user not in curr_service.maintainers:
            if is_latest:
                return {
                    "status": -3,
                    "message": "You are neither the owner nor the maintainer of this service",
                }
            if entity.creator_id != user_id:
                return {
                    "status": -4,
                    "message": "You are not the creator of this service iteration",
                }
    return None


def _pick_status_code(
    response_params_by_status_code: Dict[str, List[Dict]],
    status_code: Optional[int],
) -> int:
    codes = sorted(int(k) for k in response_params_by_status_code.keys())
    if not codes:
        return status_code or 200
    if status_code is not None and status_code in codes:
        return status_code
    if 200 in codes:
        return 200
    return codes[0]


def mockExecuteApi(
    db: Session,
    api_id: int,
    user_id: int,
    is_latest: bool = True,
    status_code: Optional[int] = None,
    request_input: Optional[Dict[str, Any]] = None,
) -> dict:
    """对单个 API 执行 Mock，返回按定义生成的响应体。"""
    api = db.get(Api, api_id) if is_latest else db.get(ApiDraft, api_id)
    if not api:
        return {"status": -1, "message": "Api not found"}

    access_error = _check_api_access(db, api, user_id, is_latest)
    if access_error:
        return access_error

    if not api.is_enabled:
        return {"status": -6, "message": "Api is disabled"}

    request_params_by_location = organizeReqParams(api.request_params)
    response_params_by_status_code = organizeRespParams(api.response_params)
    chosen_status = _pick_status_code(response_params_by_status_code, status_code)
    response_params = response_params_by_status_code.get(str(chosen_status), [])
    body = generate_mock_body(response_params)
    default_request = build_default_request_values(request_params_by_location)

    return {
        "status": 200,
        "message": "Mock executed successfully",
        "mock_result": {
            "api_id": api.id,
            "method": api.method.value if hasattr(api.method, "value") else str(api.method),
            "path": api.path,
            "status_code": chosen_status,
            "headers": {"Content-Type": "application/json"},
            "body": body,
            "request_echo": request_input or default_request,
            "default_request": default_request,
        },
    }


def mockProxyRequest(
    db: Session,
    service_uuid: str,
    user_id: int,
    method: str,
    mock_path: str,
    version: Optional[str] = None,
    service_iteration_id: Optional[int] = None,
    request_input: Optional[Dict[str, Any]] = None,
) -> dict:
    """按 service_uuid + 版本/迭代匹配 API 并返回 Mock 响应（供前端联调代理）。"""
    ctx = _resolve_service_context(
        db, service_uuid, version, service_iteration_id
    )
    if ctx.get("status") != 200:
        return ctx

    curr_service = ctx["curr_service"]
    entity = ctx["entity"]
    is_latest = ctx["is_latest"]
    access_error = _check_service_access(db, curr_service, entity, user_id, is_latest)
    if access_error:
        return access_error

    method_upper = method.upper()
    mock_path = unquote(mock_path).strip()
    if not mock_path.startswith("/"):
        mock_path = "/" + mock_path

    matched = None
    for api in ctx["apis"]:
        if not api.is_enabled:
            continue
        api_method = api.method.value if hasattr(api.method, "value") else str(api.method)
        if api_method != method_upper:
            continue
        if match_api_path(api.path, mock_path):
            matched = api
            break

    if not matched:
        return {
            "status": -7,
            "message": f"No matching API found for {method_upper} {mock_path}",
        }

    response_params_by_status_code = organizeRespParams(matched.response_params)
    request_params_by_location = organizeReqParams(matched.request_params)
    chosen_status = _pick_status_code(response_params_by_status_code, None)
    body = generate_mock_body(response_params_by_status_code.get(str(chosen_status), []))

    return {
        "status": 200,
        "message": "Mock proxy executed successfully",
        "mock_result": {
            "api_id": matched.id,
            "api_name": matched.name,
            "method": method_upper,
            "path": matched.path,
            "matched_path": mock_path,
            "status_code": chosen_status,
            "headers": {"Content-Type": "application/json"},
            "body": body,
            "request_echo": request_input or build_default_request_values(
                request_params_by_location
            ),
        },
    }


def mockGetDefaultRequest(
    db: Session,
    api_id: int,
    user_id: int,
    is_latest: bool = True,
) -> dict:
    """获取调试台预填的请求参数（example / default 生成）。"""
    api = db.get(Api, api_id) if is_latest else db.get(ApiDraft, api_id)
    if not api:
        return {"status": -1, "message": "Api not found"}

    access_error = _check_api_access(db, api, user_id, is_latest)
    if access_error:
        return access_error

    request_params_by_location = organizeReqParams(api.request_params)
    response_params_by_status_code = organizeRespParams(api.response_params)
    status_codes = sorted(int(k) for k in response_params_by_status_code.keys())

    return {
        "status": 200,
        "message": "Get mock defaults success",
        "default_request": build_default_request_values(request_params_by_location),
        "status_codes": status_codes or [200],
    }
