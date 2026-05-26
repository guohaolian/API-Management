import json
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from database.enums import HttpMethod, ParamLocation, ParamType
from database.models import (
    ApiCategory,
    ApiDraft,
    RequestParamDraft,
    ResponseParamDraft,
    Service,
    ServiceIteration,
    User,
)
from services.utils import checkServiceIterationPermission


_MAX_DEPTH = 24
_MAX_TEXT_LEN = 256


def _safe_long_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        text = value
    elif isinstance(value, (int, float, bool)):
        text = str(value)
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            text = str(value)
    text = text.strip()
    if not text:
        return None
    return text


def _safe_short_text(value: Any) -> Optional[str]:
    text = _safe_long_text(value)
    if text is None:
        return None
    if len(text) > _MAX_TEXT_LEN:
        return text[:_MAX_TEXT_LEN]
    return text


def _normalize_path(path: str) -> str:
    if not path:
        return "/"
    if not path.startswith("/"):
        return "/" + path
    return path


def _slugify(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^a-zA-Z0-9]+", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_")


def _derive_api_name(method: str, path: str) -> str:
    parts = [method.lower()]
    for seg in path.strip("/").split("/"):
        if not seg:
            continue
        if seg.startswith("{") and seg.endswith("}"):
            parts.append("by")
            parts.append(seg[1:-1])
        else:
            parts.append(seg)
    raw = "_".join(parts) or method.lower()
    return _slugify(raw)[:128] or method.lower()


def _pick_content_schema(content: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(content, dict) or not content:
        return None
    for ctype in ("application/json", "application/*+json", "*/*"):
        if ctype in content and isinstance(content[ctype], dict):
            schema = content[ctype].get("schema")
            if isinstance(schema, dict):
                return schema
    for v in content.values():
        if isinstance(v, dict):
            schema = v.get("schema")
            if isinstance(schema, dict):
                return schema
    return None


def _resolve_ref(doc: Dict[str, Any], ref: str) -> Optional[Dict[str, Any]]:
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return None
    node: Any = doc
    for part in ref[2:].split("/"):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    if isinstance(node, dict):
        return node
    return None


def _deref_schema(
    doc: Dict[str, Any],
    schema: Dict[str, Any],
    depth: int,
    seen_refs: Set[str],
) -> Dict[str, Any]:
    if depth > _MAX_DEPTH:
        return {}
    if not isinstance(schema, dict):
        return {}

    if "$ref" in schema:
        ref = schema.get("$ref")
        if isinstance(ref, str):
            if ref in seen_refs:
                return {}
            seen_refs.add(ref)
            target = _resolve_ref(doc, ref) or {}
            merged = dict(_deref_schema(doc, target, depth + 1, seen_refs))
            for k, v in schema.items():
                if k != "$ref":
                    merged[k] = v
            return merged

    for comb_key in ("oneOf", "anyOf", "allOf"):
        items = schema.get(comb_key)
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                merged = dict(_deref_schema(doc, first, depth + 1, seen_refs))
                for k, v in schema.items():
                    if k not in (comb_key,):
                        merged[k] = v
                return merged

    return schema


def _map_schema_type(schema: Dict[str, Any]) -> Tuple[ParamType, Optional[ParamType]]:
    t = schema.get("type")
    fmt = schema.get("format")

    if t is None and isinstance(schema.get("properties"), dict):
        return (ParamType.OBJECT, None)

    if t == "object":
        return (ParamType.OBJECT, None)
    if t == "array":
        items = schema.get("items")
        if isinstance(items, dict):
            item_t, _ = _map_schema_type(items)
            return (ParamType.ARRAY, item_t)
        return (ParamType.ARRAY, ParamType.STRING)
    if t == "integer":
        return (ParamType.INT, None)
    if t == "number":
        return (ParamType.DOUBLE, None)
    if t == "boolean":
        return (ParamType.BOOLEAN, None)
    if t == "string":
        if fmt == "binary":
            return (ParamType.BINARY, None)
        return (ParamType.STRING, None)

    return (ParamType.STRING, None)


def _iter_object_properties(schema: Dict[str, Any]) -> Iterable[Tuple[str, Dict[str, Any], bool]]:
    props = schema.get("properties")
    if not isinstance(props, dict):
        return []
    required_list = schema.get("required")
    required_set = set(required_list) if isinstance(required_list, list) else set()

    out: List[Tuple[str, Dict[str, Any], bool]] = []
    for name, child in props.items():
        if not isinstance(name, str) or not isinstance(child, dict):
            continue
        out.append((name, child, name in required_set))
    return out


def _create_request_param_from_schema(
    db: Session,
    doc: Dict[str, Any],
    api_draft_id: int,
    location: ParamLocation,
    name: str,
    schema: Dict[str, Any],
    required: bool,
    parent_param_id: Optional[int],
    description: Optional[str] = None,
    example: Any = None,
) -> RequestParamDraft:
    resolved = _deref_schema(doc, schema, depth=0, seen_refs=set())
    param_type, array_child_type = _map_schema_type(resolved)

    param = RequestParamDraft(
        api_draft_id=api_draft_id,
        name=name,
        location=location,
        type=param_type,
        required=required,
        default_value=_safe_short_text(resolved.get("default")),
        description=_safe_long_text(description)
        or _safe_long_text(resolved.get("description")),
        example=_safe_short_text(example) or _safe_short_text(resolved.get("example")),
        array_child_type=array_child_type if param_type == ParamType.ARRAY else None,
        parent_param_id=parent_param_id,
    )
    db.add(param)
    db.flush()

    if param_type == ParamType.OBJECT:
        for child_name, child_schema, child_required in _iter_object_properties(resolved):
            _create_request_param_from_schema(
                db=db,
                doc=doc,
                api_draft_id=api_draft_id,
                location=location,
                name=child_name,
                schema=child_schema,
                required=child_required,
                parent_param_id=param.id,
            )

    if param_type == ParamType.ARRAY and array_child_type == ParamType.OBJECT:
        items = resolved.get("items")
        items_schema = items if isinstance(items, dict) else {}
        items_resolved = _deref_schema(doc, items_schema, depth=0, seen_refs=set())
        for child_name, child_schema, child_required in _iter_object_properties(items_resolved):
            _create_request_param_from_schema(
                db=db,
                doc=doc,
                api_draft_id=api_draft_id,
                location=location,
                name=child_name,
                schema=child_schema,
                required=child_required,
                parent_param_id=param.id,
            )

    return param


def _create_response_param_from_schema(
    db: Session,
    doc: Dict[str, Any],
    api_draft_id: int,
    status_code: int,
    name: str,
    schema: Dict[str, Any],
    required: bool,
    parent_param_id: Optional[int],
    description: Optional[str] = None,
    example: Any = None,
) -> ResponseParamDraft:
    resolved = _deref_schema(doc, schema, depth=0, seen_refs=set())
    param_type, array_child_type = _map_schema_type(resolved)

    param = ResponseParamDraft(
        api_draft_id=api_draft_id,
        status_code=status_code,
        name=name,
        type=param_type,
        required=required,
        description=_safe_long_text(description)
        or _safe_long_text(resolved.get("description")),
        example=_safe_short_text(example) or _safe_short_text(resolved.get("example")),
        array_child_type=array_child_type if param_type == ParamType.ARRAY else None,
        parent_param_id=parent_param_id,
    )
    db.add(param)
    db.flush()

    if param_type == ParamType.OBJECT:
        for child_name, child_schema, child_required in _iter_object_properties(resolved):
            _create_response_param_from_schema(
                db=db,
                doc=doc,
                api_draft_id=api_draft_id,
                status_code=status_code,
                name=child_name,
                schema=child_schema,
                required=child_required,
                parent_param_id=param.id,
            )

    if param_type == ParamType.ARRAY and array_child_type == ParamType.OBJECT:
        items = resolved.get("items")
        items_schema = items if isinstance(items, dict) else {}
        items_resolved = _deref_schema(doc, items_schema, depth=0, seen_refs=set())
        for child_name, child_schema, child_required in _iter_object_properties(items_resolved):
            _create_response_param_from_schema(
                db=db,
                doc=doc,
                api_draft_id=api_draft_id,
                status_code=status_code,
                name=child_name,
                schema=child_schema,
                required=child_required,
                parent_param_id=param.id,
            )

    return param


def _replace_iteration_drafts(db: Session, service_iteration_id: int) -> None:
    api_draft_ids = [
        r[0]
        for r in db.query(ApiDraft.id)
        .filter(ApiDraft.service_iteration_id == service_iteration_id)
        .all()
    ]
    if api_draft_ids:
        db.query(RequestParamDraft).filter(
            RequestParamDraft.api_draft_id.in_(api_draft_ids)
        ).delete(synchronize_session=False)
        db.query(ResponseParamDraft).filter(
            ResponseParamDraft.api_draft_id.in_(api_draft_ids)
        ).delete(synchronize_session=False)
    db.query(ApiDraft).filter(
        ApiDraft.service_iteration_id == service_iteration_id
    ).delete(synchronize_session=False)


def _fill_iteration_from_openapi(
    db: Session,
    service_id: int,
    service_iteration_id: int,
    openapi_object: Dict[str, Any],
    user_id: int,
) -> Dict[str, Any]:
    tag_to_category_id: Dict[str, int] = {}

    def _get_or_create_category_id(tag_name: str) -> Optional[int]:
        tag_name = (tag_name or "").strip()
        if not tag_name:
            return None
        if tag_name in tag_to_category_id:
            return tag_to_category_id[tag_name]
        existing_cat = (
            db.query(ApiCategory)
            .filter(ApiCategory.service_id == service_id, ApiCategory.name == tag_name)
            .first()
        )
        if existing_cat:
            tag_to_category_id[tag_name] = existing_cat.id
            return existing_cat.id
        new_cat = ApiCategory(service_id=service_id, name=tag_name, description=None)
        db.add(new_cat)
        db.flush()
        tag_to_category_id[tag_name] = new_cat.id
        return new_cat.id

    imported_api_count = 0
    imported_req_param_count = 0
    imported_resp_param_count = 0
    warnings: List[str] = []

    used_names: Set[str] = set()
    paths: Dict[str, Any] = openapi_object.get("paths", {})

    for raw_path, path_item in paths.items():
        if not isinstance(raw_path, str) or not isinstance(path_item, dict):
            continue
        path = _normalize_path(raw_path)

        common_parameters = (
            path_item.get("parameters")
            if isinstance(path_item.get("parameters"), list)
            else []
        )

        for method in ("get", "post", "put", "delete", "patch"):
            op = path_item.get(method)
            if not isinstance(op, dict):
                continue

            try:
                method_enum = HttpMethod[method.upper()]
            except KeyError:
                warnings.append(f"Unsupported http method: {method}")
                continue

            operation_id = op.get("operationId")
            summary = op.get("summary")
            name_candidate = (
                operation_id
                if isinstance(operation_id, str) and operation_id.strip()
                else summary
            )
            if not isinstance(name_candidate, str) or not name_candidate.strip():
                name_candidate = _derive_api_name(method, path)
            name = _slugify(name_candidate)[:128] or _derive_api_name(method, path)

            base_name = name
            idx = 2
            while name in used_names:
                suffix = f"_{idx}"
                name = (
                    (base_name[: (128 - len(suffix))] + suffix)
                    if len(base_name) + len(suffix) > 128
                    else base_name + suffix
                )
                idx += 1
            used_names.add(name)

            tags = op.get("tags") if isinstance(op.get("tags"), list) else []
            first_tag = tags[0] if tags and isinstance(tags[0], str) else ""
            category_id = _get_or_create_category_id(first_tag)

            api_draft = ApiDraft(
                service_iteration_id=service_iteration_id,
                owner_id=user_id,
                category_id=category_id,
                name=name,
                method=method_enum,
                path=path,
                description=_safe_long_text(op.get("description"))
                or _safe_long_text(op.get("summary")),
                is_enabled=True,
            )
            db.add(api_draft)
            db.flush()
            imported_api_count += 1

            all_parameters: List[Any] = []
            if isinstance(common_parameters, list):
                all_parameters.extend(common_parameters)
            op_parameters = (
                op.get("parameters") if isinstance(op.get("parameters"), list) else []
            )
            if isinstance(op_parameters, list):
                all_parameters.extend(op_parameters)

            seen_param_keys: Set[Tuple[str, str]] = set()
            for p in all_parameters:
                if not isinstance(p, dict):
                    continue
                p_resolved = _deref_schema(openapi_object, p, depth=0, seen_refs=set())
                pname = p_resolved.get("name")
                pin = p_resolved.get("in")
                if not isinstance(pname, str) or not isinstance(pin, str):
                    continue
                key = (pname, pin)
                if key in seen_param_keys:
                    continue
                seen_param_keys.add(key)

                try:
                    location_enum = ParamLocation(pin)
                except Exception:
                    warnings.append(f"Unsupported param location: {pin}")
                    continue

                schema = (
                    p_resolved.get("schema")
                    if isinstance(p_resolved.get("schema"), dict)
                    else {}
                )
                required = bool(p_resolved.get("required")) or (
                    location_enum == ParamLocation.PATH
                )
                _create_request_param_from_schema(
                    db=db,
                    doc=openapi_object,
                    api_draft_id=api_draft.id,
                    location=location_enum,
                    name=pname,
                    schema=schema,
                    required=required,
                    parent_param_id=None,
                    description=_safe_long_text(p_resolved.get("description")),
                    example=p_resolved.get("example"),
                )
                imported_req_param_count += 1

            request_body = op.get("requestBody")
            if isinstance(request_body, dict):
                rb_resolved = _deref_schema(openapi_object, request_body, depth=0, seen_refs=set())
                schema = None
                content = rb_resolved.get("content")
                if isinstance(content, dict):
                    schema = _pick_content_schema(content)
                if isinstance(schema, dict):
                    schema_resolved = _deref_schema(openapi_object, schema, depth=0, seen_refs=set())
                    if (
                        isinstance(schema_resolved.get("properties"), dict)
                        or schema_resolved.get("type") == "object"
                    ):
                        for child_name, child_schema, child_required in _iter_object_properties(schema_resolved):
                            _create_request_param_from_schema(
                                db=db,
                                doc=openapi_object,
                                api_draft_id=api_draft.id,
                                location=ParamLocation.BODY,
                                name=child_name,
                                schema=child_schema,
                                required=child_required,
                                parent_param_id=None,
                            )
                            imported_req_param_count += 1
                    else:
                        _create_request_param_from_schema(
                            db=db,
                            doc=openapi_object,
                            api_draft_id=api_draft.id,
                            location=ParamLocation.BODY,
                            name="body",
                            schema=schema_resolved,
                            required=bool(rb_resolved.get("required")),
                            parent_param_id=None,
                        )
                        imported_req_param_count += 1

            responses = op.get("responses")
            if isinstance(responses, dict):
                for scode_raw, resp in responses.items():
                    if scode_raw == "default":
                        continue
                    try:
                        status_code = int(scode_raw)
                    except Exception:
                        continue
                    if not isinstance(resp, dict):
                        continue
                    resp_resolved = _deref_schema(openapi_object, resp, depth=0, seen_refs=set())
                    schema = None
                    content = resp_resolved.get("content")
                    if isinstance(content, dict):
                        schema = _pick_content_schema(content)
                    if not isinstance(schema, dict):
                        continue

                    schema_resolved = _deref_schema(openapi_object, schema, depth=0, seen_refs=set())
                    if (
                        isinstance(schema_resolved.get("properties"), dict)
                        or schema_resolved.get("type") == "object"
                    ):
                        for child_name, child_schema, child_required in _iter_object_properties(schema_resolved):
                            _create_response_param_from_schema(
                                db=db,
                                doc=openapi_object,
                                api_draft_id=api_draft.id,
                                status_code=status_code,
                                name=child_name,
                                schema=child_schema,
                                required=child_required,
                                parent_param_id=None,
                            )
                            imported_resp_param_count += 1
                    else:
                        _create_response_param_from_schema(
                            db=db,
                            doc=openapi_object,
                            api_draft_id=api_draft.id,
                            status_code=status_code,
                            name="data",
                            schema=schema_resolved,
                            required=False,
                            parent_param_id=None,
                        )
                        imported_resp_param_count += 1

    return {
        "apis": imported_api_count,
        "request_params": imported_req_param_count,
        "response_params": imported_resp_param_count,
        "categories": len(tag_to_category_id),
        "warnings": warnings,
    }


def import_openapi_to_new_iteration(
    db: Session,
    service_id: int,
    openapi_object: Dict[str, Any],
    user_id: int,
) -> Dict[str, Any]:
    service = db.get(Service, service_id)
    if not service:
        return {"status": -1, "message": "Service not found"}

    user = db.get(User, user_id)
    if not user:
        return {"status": -2, "message": "User not found"}

    if service.owner_id != user_id and user not in service.maintainers and user.level.value != 0:  # type: ignore
        return {"status": -3, "message": "You are neither the owner nor the maintainer of this service"}

    existing = (
        db.query(ServiceIteration)
        .filter(
            ServiceIteration.service_id == service_id,
            ~ServiceIteration.is_committed,
            ServiceIteration.creator_id == user_id,
        )
        .first()
    )
    if existing:
        return {
            "status": -4,
            "message": "You have an uncommitted service iteration in progress",
            "service_iteration_id": existing.id,
        }

    if not isinstance(openapi_object, dict) or not isinstance(openapi_object.get("paths"), dict):
        return {"status": -5, "message": "Invalid OpenAPI document: missing 'paths'"}

    if "swagger" in openapi_object and "openapi" not in openapi_object:
        return {"status": -6, "message": "Swagger 2.0 is not supported yet"}

    info = openapi_object.get("info") if isinstance(openapi_object.get("info"), dict) else {}
    iteration = ServiceIteration(
        service_id=service_id,
        creator_id=user_id,
        version=None,
        description=_safe_long_text(info.get("description")) or service.description,
        is_committed=False,
    )
    db.add(iteration)
    db.flush()
    try:
        imported = _fill_iteration_from_openapi(
            db=db,
            service_id=service_id,
            service_iteration_id=iteration.id,
            openapi_object=openapi_object,
            user_id=user_id,
        )
        db.commit()
    except Exception as e:
        db.rollback()
        return {
            "status": -7,
            "message": f"Import OpenAPI failed: {e}",
        }

    return {
        "status": 200,
        "message": "Import OpenAPI to new iteration success",
        "service_iteration_id": iteration.id,
        "imported": {
            **imported,
        },
    }


def import_openapi_to_iteration(
    db: Session,
    service_iteration_id: int,
    openapi_object: Dict[str, Any],
    user_id: int,
) -> Dict[str, Any]:
    check_res = checkServiceIterationPermission(
        db=db, service_iteration_id=service_iteration_id, user_id=user_id
    )
    if not check_res.get("is_ok"):
        return check_res.get("error")  # type: ignore

    iteration: ServiceIteration = check_res["service_iteration"]
    service_id = iteration.service_id

    if not isinstance(openapi_object, dict) or not isinstance(openapi_object.get("paths"), dict):
        return {"status": -5, "message": "Invalid OpenAPI document: missing 'paths'"}
    if "swagger" in openapi_object and "openapi" not in openapi_object:
        return {"status": -6, "message": "Swagger 2.0 is not supported yet"}

    try:
        _replace_iteration_drafts(db=db, service_iteration_id=service_iteration_id)
        imported = _fill_iteration_from_openapi(
            db=db,
            service_id=service_id,
            service_iteration_id=service_iteration_id,
            openapi_object=openapi_object,
            user_id=user_id,
        )
        db.commit()
    except Exception as e:
        db.rollback()
        return {"status": -7, "message": f"Import OpenAPI failed: {e}"}

    return {
        "status": 200,
        "message": "Import OpenAPI to iteration success",
        "service_iteration_id": service_iteration_id,
        "imported": imported,
    }
