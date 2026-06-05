"""Mock 响应生成引擎：按参数树定义，优先使用 example / default_value 生成示例数据。"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


def _normalize_type(type_name: Any) -> str:
    if type_name is None:
        return "string"
    return getattr(type_name, "value", type_name)


def _coerce_scalar(type_name: str, raw: str) -> Any:
    if raw in ("null", "undefined", ""):
        return None
    try:
        match type_name:
            case "int":
                return int(raw)
            case "double":
                return float(raw)
            case "boolean":
                lowered = raw.strip().lower()
                if lowered in ("true", "1", "yes"):
                    return True
                if lowered in ("false", "0", "no"):
                    return False
                return bool(raw)
            case _:
                return raw
    except (TypeError, ValueError):
        return raw


def _parse_json_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return raw


def _type_fallback(
    type_name: str,
    *,
    array_child_type: Optional[str] = None,
    children: Optional[List[Dict]] = None,
    param_name: str = "",
) -> Any:
    if type_name == "object":
        if children:
            return build_object_from_params(children)
        return {}

    if type_name == "array":
        child_type = array_child_type or "string"
        if child_type == "object" and children:
            return [build_object_from_params(children)]
        return [_type_fallback(child_type, param_name=param_name)]

    fallbacks = {
        "string": f"mock_{param_name}" if param_name else "mock_string",
        "int": 0,
        "double": 0.0,
        "boolean": False,
        "binary": "mock_binary",
    }
    return fallbacks.get(type_name, "mock_value")


def generate_value_from_param(param: Dict) -> Any:
    """从单个参数节点生成 mock 值，优先级：example > default_value > 类型兜底。"""
    type_name = _normalize_type(param.get("type", "string"))
    array_child_type = _normalize_type(param.get("array_child_type"))
    children = param.get("children_params") or []
    name = param.get("name") or ""

    example = param.get("example")
    if example not in (None, ""):
        if type_name in ("object", "array"):
            parsed = _parse_json_value(str(example))
            if isinstance(parsed, (dict, list)):
                return parsed
        return _coerce_scalar(type_name, str(example))

    default_value = param.get("default_value")
    if default_value not in (None, ""):
        if type_name in ("object", "array"):
            parsed = _parse_json_value(str(default_value))
            if isinstance(parsed, (dict, list)):
                return parsed
        return _coerce_scalar(type_name, str(default_value))

    return _type_fallback(
        type_name,
        array_child_type=array_child_type or None,
        children=children,
        param_name=name,
    )


def build_object_from_params(params: List[Dict]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for param in params:
        name = param.get("name")
        if not name:
            continue
        result[name] = generate_value_from_param(param)
    return result


def generate_mock_body(params: List[Dict]) -> Any:
    """根据响应参数根节点列表生成 mock 响应体。"""
    if not params:
        return {}
    if len(params) == 1 and params[0].get("type") == "object":
        children = params[0].get("children_params") or []
        if children:
            return build_object_from_params(children)
    return build_object_from_params(params)


def build_default_request_values(
    request_params_by_location: Dict[str, List[Dict]],
) -> Dict[str, Any]:
    """为调试台预填请求参数，按 location 分组。"""
    result: Dict[str, Any] = {}
    for location, params in request_params_by_location.items():
        if not params:
            continue
        if location == "body":
            body_params = params
            if (
                len(body_params) == 1
                and body_params[0].get("type") == "object"
                and body_params[0].get("children_params")
            ):
                result["body"] = build_object_from_params(
                    body_params[0]["children_params"]
                )
            else:
                result["body"] = build_object_from_params(body_params)
        else:
            result[location] = {
                p["name"]: generate_value_from_param(p)
                for p in params
                if p.get("name")
            }
    return result


def path_template_to_regex(template: str) -> re.Pattern:
    """将 OpenAPI 风格路径模板转为正则，如 /users/{id}。"""
    parts: List[str] = []
    for segment in template.split("/"):
        if not segment:
            parts.append("")
            continue
        if segment.startswith("{") and segment.endswith("}"):
            parts.append("[^/]+")
        else:
            parts.append(re.escape(segment))
    pattern = "/".join(parts)
    if not pattern.startswith("/"):
        pattern = "/" + pattern
    return re.compile(f"^{pattern}$")


def match_api_path(api_path: str, request_path: str) -> bool:
    return bool(path_template_to_regex(api_path).match(request_path))
