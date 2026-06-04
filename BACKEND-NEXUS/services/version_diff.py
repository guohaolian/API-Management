"""Service/API/参数树 版本差异对比。

对比两个已发布版本（或 latest）的快照，按 method+path 匹配 API，
按路径键匹配嵌套参数，返回结构化 diff 供前端展示。
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from database.models import (
    Api,
    ApiCategory,
    ApiDraft,
    Service,
    ServiceIteration,
    User,
)
from services.utils import organizeReqParams, organizeRespParams

# API 顶层字段对比（不含 id / 时间戳）
API_COMPARE_FIELDS = (
    "name",
    "method",
    "path",
    "description",
    "level",
    "is_enabled",
    "category_id",
)

# 参数节点对比字段
PARAM_COMPARE_FIELDS = (
    "name",
    "type",
    "required",
    "default_value",
    "description",
    "example",
    "array_child_type",
)


def _enum_value(val: Any) -> Any:
    return getattr(val, "value", val)


def _normalize_api_fields(api_dict: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for field in API_COMPARE_FIELDS:
        val = api_dict.get(field)
        if field in ("method", "level"):
            val = _enum_value(val)
        out[field] = val
    return out


def _normalize_param_fields(param: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for field in PARAM_COMPARE_FIELDS:
        val = param.get(field)
        if field in ("type", "array_child_type", "location"):
            val = _enum_value(val)
        out[field] = val
    if "location" in param:
        out["location"] = _enum_value(param.get("location"))
    return out


def _api_key(method: Any, path: str) -> str:
    return f"{_enum_value(method)}:{path}"


def _field_changes(
    old: Dict[str, Any], new: Dict[str, Any], fields: Tuple[str, ...]
) -> List[Dict[str, Any]]:
    changes = []
    for field in fields:
        old_v, new_v = old.get(field), new.get(field)
        if old_v != new_v:
            changes.append({"field": field, "old": old_v, "new": new_v})
    return changes


def _flatten_request_params(
    params_by_location: Dict[str, List[Dict]],
) -> Dict[str, Dict[str, Any]]:
    """将按 location 分组的请求参数树压平为 path -> 字段字典。"""
    flat: Dict[str, Dict[str, Any]] = {}

    def walk(nodes: List[Dict], loc: str, parent_path: str) -> None:
        for node in nodes:
            name = node.get("name", "")
            path = f"{parent_path}.{name}" if parent_path else name
            full_key = f"{loc}.{path}"
            entry = _normalize_param_fields(node)
            entry["location"] = loc
            flat[full_key] = entry
            for child in node.get("children_params") or []:
                walk([child], loc, path)

    for loc, roots in (params_by_location or {}).items():
        walk(roots, loc, "")
    return flat


def _flatten_response_params(
    params_by_status: Dict[str, List[Dict]],
) -> Dict[str, Dict[str, Any]]:
    flat: Dict[str, Dict[str, Any]] = {}

    def walk(nodes: List[Dict], status: str, parent_path: str) -> None:
        for node in nodes:
            name = node.get("name", "")
            path = f"{parent_path}.{name}" if parent_path else name
            full_key = f"{status}.{path}"
            flat[full_key] = _normalize_param_fields(node)
            for child in node.get("children_params") or []:
                walk([child], status, path)

    for status, roots in (params_by_status or {}).items():
        walk(roots, str(status), "")
    return flat


def _diff_flat_maps(
    base_map: Dict[str, Dict[str, Any]],
    compare_map: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    added: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []
    modified: List[Dict[str, Any]] = []

    for key in sorted(compare_map.keys()):
        if key not in base_map:
            added.append({"path": key, "param": compare_map[key]})

    for key in sorted(base_map.keys()):
        if key not in compare_map:
            removed.append({"path": key, "param": base_map[key]})

    for key in sorted(base_map.keys() & compare_map.keys()):
        changes = _field_changes(base_map[key], compare_map[key], PARAM_COMPARE_FIELDS)
        loc_change = base_map[key].get("location") != compare_map[key].get("location")
        if loc_change:
            changes.append(
                {
                    "field": "location",
                    "old": base_map[key].get("location"),
                    "new": compare_map[key].get("location"),
                }
            )
        if changes:
            modified.append(
                {
                    "path": key,
                    "field_changes": changes,
                    "base": base_map[key],
                    "compare": compare_map[key],
                }
            )

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "has_changes": bool(added or removed or modified),
    }


def _build_api_snapshot(api: Api | ApiDraft) -> Dict[str, Any]:
    req_by_loc = organizeReqParams(api.request_params)
    resp_by_status = organizeRespParams(api.response_params)
    info = {
        "name": api.name,
        "method": api.method,
        "path": api.path,
        "description": api.description,
        "level": api.level,
        "is_enabled": api.is_enabled,
        "category_id": api.category_id,
        "request_params_by_location": req_by_loc,
        "response_params_by_status_code": resp_by_status,
    }
    normalized = _normalize_api_fields(info)
    normalized["key"] = _api_key(api.method, api.path)
    normalized["request_params_by_location"] = req_by_loc
    normalized["response_params_by_status_code"] = resp_by_status
    return normalized


def _diff_apis(
    base_apis: List[Dict[str, Any]], compare_apis: List[Dict[str, Any]]
) -> Dict[str, Any]:
    base_index = {a["key"]: a for a in base_apis}
    compare_index = {a["key"]: a for a in compare_apis}

    added: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []
    modified: List[Dict[str, Any]] = []

    for key in sorted(compare_index.keys()):
        if key not in base_index:
            added.append(compare_index[key])

    for key in sorted(base_index.keys()):
        if key not in compare_index:
            removed.append(base_index[key])

    for key in sorted(base_index.keys() & compare_index.keys()):
        base_api = base_index[key]
        compare_api = compare_index[key]
        field_changes = _field_changes(
            {k: base_api[k] for k in API_COMPARE_FIELDS if k in base_api},
            {k: compare_api[k] for k in API_COMPARE_FIELDS if k in compare_api},
            API_COMPARE_FIELDS,
        )
        request_diff = _diff_flat_maps(
            _flatten_request_params(base_api.get("request_params_by_location")),
            _flatten_request_params(compare_api.get("request_params_by_location")),
        )
        response_diff = _diff_flat_maps(
            _flatten_response_params(
                base_api.get("response_params_by_status_code")
            ),
            _flatten_response_params(
                compare_api.get("response_params_by_status_code")
            ),
        )
        if field_changes or request_diff["has_changes"] or response_diff["has_changes"]:
            modified.append(
                {
                    "key": key,
                    "method": compare_api.get("method"),
                    "path": compare_api.get("path"),
                    "name": compare_api.get("name"),
                    "field_changes": field_changes,
                    "request_params": request_diff,
                    "response_params": response_diff,
                }
            )

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
    }


def _resolve_version_entity(
    db: Session,
    curr_service: Service,
    version: str,
    user: User,
    user_id: int,
) -> Tuple[Any | None, bool | None, dict | None]:
    """解析版本实体。返回 (entity, is_latest, error_dict)。"""
    if curr_service.version == version or version == "latest":  # type: ignore
        is_latest = True
        entity = curr_service
    else:
        is_latest = False
        entity = (
            db.query(ServiceIteration)
            .filter(
                ServiceIteration.service_id == curr_service.id,
                ServiceIteration.version == version,
                ServiceIteration.is_committed == True,  # noqa: E712
            )
            .first()
        )
        if not entity:
            return None, None, {"status": -2, "message": "Service version not found"}

    if (
        curr_service.owner_id != user_id
        and user not in curr_service.maintainers
        and user.level.value != 0  # type: ignore
    ):
        if is_latest:
            return None, None, {
                "status": -3,
                "message": "You are neither the owner nor the maintainer of this service",
            }
        if entity.creator_id != user_id:  # type: ignore
            return None, None, {
                "status": -4,
                "message": "You are not the creator of this service iteration",
            }

    return entity, is_latest, None


def _load_version_snapshot(
    db: Session, curr_service: Service, entity: Any, is_latest: bool
) -> Dict[str, Any]:
    if is_latest:
        apis = (
            db.query(Api)
            .filter(Api.service_id == curr_service.id)
            .order_by(Api.id)
            .all()
        )
        description = entity.description
        version = entity.version
    else:
        apis = list(entity.api_drafts)
        description = entity.description
        version = entity.version

    categories = (
        db.query(ApiCategory)
        .filter(ApiCategory.service_id == curr_service.id)
        .order_by(ApiCategory.id)
        .all()
    )

    return {
        "version": version,
        "description": description or "",
        "categories": [
            {"id": c.id, "name": c.name, "description": c.description or ""}
            for c in categories
        ],
        "apis": [_build_api_snapshot(api) for api in apis],
    }


def _diff_categories(
    base_cats: List[Dict], compare_cats: List[Dict]
) -> Dict[str, Any]:
    base_by_id = {c["id"]: c for c in base_cats}
    compare_by_id = {c["id"]: c for c in compare_cats}
    added = [compare_by_id[i] for i in sorted(compare_by_id) if i not in base_by_id]
    removed = [base_by_id[i] for i in sorted(base_by_id) if i not in compare_by_id]
    modified = []
    for cid in sorted(base_by_id.keys() & compare_by_id.keys()):
        changes = _field_changes(base_by_id[cid], compare_by_id[cid], ("name", "description"))
        if changes:
            modified.append(
                {
                    "id": cid,
                    "field_changes": changes,
                    "base": base_by_id[cid],
                    "compare": compare_by_id[cid],
                }
            )
    return {"added": added, "removed": removed, "modified": modified}


def compare_service_versions(
    db: Session,
    service_uuid: str,
    base_version: str,
    compare_version: str,
    user_id: int,
) -> dict:
    from urllib.parse import unquote

    service_uuid = unquote(service_uuid).strip()
    if base_version == compare_version:
        return {"status": -5, "message": "Base version and compare version must differ"}

    curr_service = (
        db.query(Service)
        .filter(Service.service_uuid == service_uuid, ~Service.is_deleted)
        .first()
    )
    if not curr_service:
        return {"status": -1, "message": "Service not found"}

    user = db.get(User, user_id)
    if not user:
        return {"status": -6, "message": "User not found"}

    base_entity, base_is_latest, base_err = _resolve_version_entity(
        db, curr_service, base_version, user, user_id
    )
    if base_err:
        return base_err

    compare_entity, compare_is_latest, compare_err = _resolve_version_entity(
        db, curr_service, compare_version, user, user_id
    )
    if compare_err:
        return compare_err

    base_snapshot = _load_version_snapshot(
        db, curr_service, base_entity, base_is_latest  # type: ignore
    )
    compare_snapshot = _load_version_snapshot(
        db, curr_service, compare_entity, compare_is_latest  # type: ignore
    )

    service_field_changes = []
    if base_snapshot["description"] != compare_snapshot["description"]:
        service_field_changes.append(
            {
                "field": "description",
                "old": base_snapshot["description"],
                "new": compare_snapshot["description"],
            }
        )

    categories_diff = _diff_categories(
        base_snapshot["categories"], compare_snapshot["categories"]
    )
    apis_diff = _diff_apis(base_snapshot["apis"], compare_snapshot["apis"])

    summary = {
        "service_changed": bool(service_field_changes),
        "categories_added": len(categories_diff["added"]),
        "categories_removed": len(categories_diff["removed"]),
        "categories_modified": len(categories_diff["modified"]),
        "apis_added": len(apis_diff["added"]),
        "apis_removed": len(apis_diff["removed"]),
        "apis_modified": len(apis_diff["modified"]),
    }

    return {
        "status": 200,
        "message": "Compare service versions success",
        "base_version": base_snapshot["version"],
        "compare_version": compare_snapshot["version"],
        "service_diff": {
            "field_changes": service_field_changes,
            "base_description": base_snapshot["description"],
            "compare_description": compare_snapshot["description"],
        },
        "categories_diff": categories_diff,
        "apis_diff": apis_diff,
        "summary": summary,
    }


def _load_base_snapshot_for_iteration(
    db: Session, curr_service: Service, base_version: str
) -> Dict[str, Any] | None:
    """加载迭代基线版本快照；找不到时返回 None。"""
    if curr_service.version == base_version:
        return _load_version_snapshot(db, curr_service, curr_service, True)

    entity = (
        db.query(ServiceIteration)
        .filter(
            ServiceIteration.service_id == curr_service.id,
            ServiceIteration.version == base_version,
            ServiceIteration.is_committed == True,  # noqa: E712
        )
        .first()
    )
    if not entity:
        return None
    return _load_version_snapshot(db, curr_service, entity, False)


def _load_draft_snapshot(
    db: Session, curr_service: Service, iteration: ServiceIteration
) -> Dict[str, Any]:
    return {
        "version": iteration.proposed_version or "(draft)",
        "description": iteration.description or "",
        "categories": [
            {"id": c.id, "name": c.name, "description": c.description or ""}
            for c in db.query(ApiCategory)
            .filter(ApiCategory.service_id == curr_service.id)
            .order_by(ApiCategory.id)
            .all()
        ],
        "apis": [_build_api_snapshot(api) for api in list(iteration.api_drafts)],
    }


def compare_iteration_change_preview(
    db: Session, iteration: ServiceIteration
) -> dict:
    """对比迭代基线版本与当前草稿（用于审批预览）。"""
    curr_service = iteration.service
    base_version = iteration.base_version or curr_service.version
    base_snapshot = _load_base_snapshot_for_iteration(db, curr_service, base_version)
    if not base_snapshot:
        return {"status": -2, "message": "Base version snapshot not found"}

    compare_snapshot = _load_draft_snapshot(db, curr_service, iteration)

    service_field_changes = []
    if base_snapshot["description"] != compare_snapshot["description"]:
        service_field_changes.append(
            {
                "field": "description",
                "old": base_snapshot["description"],
                "new": compare_snapshot["description"],
            }
        )

    categories_diff = _diff_categories(
        base_snapshot["categories"], compare_snapshot["categories"]
    )
    apis_diff = _diff_apis(base_snapshot["apis"], compare_snapshot["apis"])

    summary = {
        "service_changed": bool(service_field_changes),
        "categories_added": len(categories_diff["added"]),
        "categories_removed": len(categories_diff["removed"]),
        "categories_modified": len(categories_diff["modified"]),
        "apis_added": len(apis_diff["added"]),
        "apis_removed": len(apis_diff["removed"]),
        "apis_modified": len(apis_diff["modified"]),
    }

    return {
        "status": 200,
        "message": "Get iteration change preview success",
        "base_version": base_snapshot["version"],
        "compare_version": compare_snapshot["version"],
        "service_diff": {
            "field_changes": service_field_changes,
            "base_description": base_snapshot["description"],
            "compare_description": compare_snapshot["description"],
        },
        "categories_diff": categories_diff,
        "apis_diff": apis_diff,
        "summary": summary,
    }
