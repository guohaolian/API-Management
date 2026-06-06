"""服务层通用工具函数。

这个模块主要承担三类工作：
1. 对 service iteration 的操作权限做统一校验。
2. 将 RequestParam / ResponseParam 按 location 或 status_code 重新组织。
3. 将内部数据结构转换为 OpenAPI 3.1.0 文档。

这里的实现会直接读取 ORM 对象并组装字典，因此大量逻辑都围绕“转换”和“递归展开”展开。
"""

from database.models import Api
from database.models import ApiDraft
from sqlalchemy.orm import Session
from typing import List, Dict
import re

from database.models import (
    Service,
    ServiceIteration,
    User,
    RequestParam,
    RequestParamDraft,
    ResponseParam,
    ResponseParamDraft,
)
from database.enums import ParamLocation, ParamType, IterationApprovalStatus


def isServiceOwnerOrMaintainer(service: Service, user_id: int, user: User) -> bool:
    """判断用户是否为服务 owner、maintainer 或 L0 管理员。"""
    if user.level.value == 0:  # type: ignore
        return True
    if service.owner_id == user_id:
        return True
    return any(m.id == user_id for m in service.maintainers)


# service 版本迭代行为权限校验（校验service_iteration是否存在，是否已提交，是否为当前user有权限操作）
def checkServiceIterationPermission(
    db: Session,
    service_iteration_id: int,
    user_id: int,
) -> dict:
    # 先按主键读取迭代记录，避免后续在不存在对象上继续访问关系属性
    service_iteration = db.get(ServiceIteration, service_iteration_id)
    if not service_iteration or service_iteration.is_committed:  # type: ignore
        return {
            "is_ok": False,
            "error": {
                "status": -10,
                "message": "Service iteration not found or committed",
            },
        }
    if service_iteration.approval_status == IterationApprovalStatus.PENDING:  # type: ignore
        return {
            "is_ok": False,
            "error": {
                "status": -21,
                "message": "Service iteration is pending approval and cannot be edited",
            },
        }
    # 非 L0 用户只有两类人能改这个迭代：服务 owner 或该迭代 creator
    # 维护者可以发起自己的迭代，但不能随意修改别人的迭代内容
    user = db.get(User, user_id)
    if (
        service_iteration.service.owner_id != user_id
        and service_iteration.creator_id != user_id
        and user.level.value != 0  # type: ignore
    ):
        return {
            "is_ok": False,
            "error": {
                "status": -30,
                "message": "You are neither the owner of this service, nor the creator of this service iteration",
            },
        }
    return {
        "is_ok": True,
        "service_iteration": service_iteration,
        "user": user,
    }


# 组织请求参数，根据location分类
def organizeReqParams(
    request_params: List[RequestParam | RequestParamDraft],
) -> Dict[str, List[Dict]]:
    # 先转换成纯字典，后续递归拼装 children 时更方便，也避免在 ORM 对象上原地改结构
    request_params_raw = [rp.toJson() for rp in request_params]
    # 按 location 分桶，最后生成 OpenAPI 参数时可以直接对应到 query/path/header/cookie/body
    request_params_by_location = {
        ParamLocation.QUERY.value: [],
        ParamLocation.PATH.value: [],
        ParamLocation.HEADER.value: [],
        ParamLocation.COOKIE.value: [],
        ParamLocation.BODY.value: [],
    }
    # 构建id到param的索引表，用于处理子参数
    req_index = {p["id"]: p for p in request_params_raw}
    # 处理 location、type、array_child_type 等字段：如果还保留着枚举对象，先取其 value
    # 这样后面的 OpenAPI 组装只需要处理字符串，不用关心 ORM/Enum 细节
    for p in request_params_raw:
        loc = p.get("location")
        p["location"] = getattr(loc, "value", loc)
        t = p.get("type")
        p["type"] = getattr(t, "value", t)
        act = p.get("array_child_type")
        p["array_child_type"] = getattr(act, "value", act)
    for p in request_params_raw:
        parent_id = p.get("parent_param_id")
        # 存在parent_param_id的参数为子参数，将其添加到父参数的children_params中
        if parent_id:
            parent = req_index.get(parent_id)
            if parent is not None:
                # children_params 只在需要时创建，避免给所有节点都塞一个空数组
                parent.setdefault("children_params", []).append(p)
        # 不存在parent_param_id的参数为根参数，根据location添加到对应的列表中
        else:
            request_params_by_location[p["location"]].append(p)

    return request_params_by_location


def organizeRespParams(
    response_params: List[ResponseParam | ResponseParamDraft],
) -> Dict[str, List[Dict]]:
    # 响应参数同样先降维成字典，方便后面按 status_code 分组并重建树形结构
    response_params_raw = [rp.toJson() for rp in response_params]
    # 构建id到param的索引表，用于处理子参数
    resp_index = {p["id"]: p for p in response_params_raw}
    # 将枚举值统一转成基础类型，避免后续 schema 生成时出现 Enum 对象
    for p in response_params_raw:
        t = p.get("type")
        p["type"] = getattr(t, "value", t)
        act = p.get("array_child_type")
        p["array_child_type"] = getattr(act, "value", act)
    response_params_by_status_code = {}
    for p in response_params_raw:
        parent_id = p.get("parent_param_id")
        # 存在parent_param_id的参数为子参数，将其添加到父参数的children_params中
        if parent_id:
            parent = resp_index.get(parent_id)
            if parent is not None:
                # 响应参数树的节点结构与请求参数一致，复用 children_params 的命名
                parent.setdefault("children_params", []).append(p)
        # 不存在parent_param_id的参数为根参数，根据status_code添加到对应的列表中
        else:
            key = str(p["status_code"])  # Python中dict的key必须是str
            response_params_by_status_code.setdefault(key, []).append(p)

    return response_params_by_status_code


def openapiTemplate(service: Service | ServiceIteration, is_latest: bool) -> Dict:
    """
    根据 Service 或 ServiceIteration 生成 OpenAPI 3.1.0 规范文档。
    参考：https://openapi.apifox.cn/
    原理：
    1. 遍历 Service 中的所有 API。
    2. 将内部定义的 RequestParam 和 ResponseParam 转换为 OpenAPI 的 Schema 对象。
    3. 递归处理对象和数组类型的嵌套结构。
    4. 根据参数位置（query, path, header, cookie, body）将参数放置到对应的 OpenAPI 字段中。
    5. 组装 Info, Paths, Components 等顶级字段。
    """
    contact: User = service.owner if is_latest else service.creator
    apis: List[Api | ApiDraft] = service.apis if is_latest else service.api_drafts
    # paths 保存 OpenAPI 的路径树，components_schemas 保存可复用的 schema 片段
    paths = {}
    components_schemas = {}

    def _to_component_name(name: str) -> str:
        """
        Convert name to PascalCase for component names.
        """
        # Insert space before capital letters to handle camelCase/PascalCase
        s1 = re.sub(r"(?<!^)(?=[A-Z])", " ", name)
        # Replace non-alphanumeric characters with spaces
        clean = re.sub(r"[^a-zA-Z0-9]", " ", s1)
        return "".join(word.capitalize() for word in clean.split())

    def _get_type_schema(type_name: str) -> Dict:
        """
        将内部类型映射为 OpenAPI 支持的数据类型。
        例如：int -> integer (int64), double -> number (double)
        """
        # 这里使用显式映射，而不是猜测类型，保证输出是稳定且可读的 OpenAPI schema
        mapping = {
            "string": {"type": "string"},
            "int": {"type": "integer", "format": "int64"},
            "double": {"type": "number", "format": "double"},
            "boolean": {"type": "boolean"},
            "binary": {"type": "string", "format": "binary"},
            "object": {"type": "object"},
            "array": {"type": "array"},
        }
        return mapping.get(type_name, {"type": "string"})

    def _build_param_schema(param: Dict) -> Dict:
        """
        递归构建参数的 Schema。
        - 如果是 object 类型，递归构建 properties。
        - 如果是 array 类型，递归构建 items。
        - 处理 description, example, default 等元数据。
        """
        # 先拿到基础 schema，再按类型进行增强，避免分支里重复初始化
        schema = _get_type_schema(param.get("type", "string"))

        if param.get("type") == "object":
            # object 需要递归展开 children_params，转成 properties / required
            properties = {}
            required = []
            for child in param.get("children_params", []):
                properties[child["name"]] = _build_param_schema(child)
                if child.get("required"):
                    required.append(child["name"])
            if properties:
                schema["properties"] = properties
                schema["additionalProperties"] = False
            if required:
                schema["required"] = required

        elif param.get("type") == "array":
            # 数组元素类型由 array_child_type 决定，object 数组需要继续递归处理 children
            child_type = param.get("array_child_type", "string")
            if child_type == "object":
                item_schema = {"type": "object"}
                properties = {}
                required = []
                for child in param.get("children_params", []):
                    properties[child["name"]] = _build_param_schema(child)
                    if child.get("required"):
                        required.append(child["name"])
                if properties:
                    item_schema["properties"] = properties
                    item_schema["additionalProperties"] = False
                if required:
                    item_schema["required"] = required
                schema["items"] = item_schema
            else:
                schema["items"] = _get_type_schema(child_type)

        # example 是可选元数据，存在就透传到 schema
        if param.get("example"):
            schema["example"] = param.get("example")
        # default_value 需要根据类型做转换，否则 OpenAPI 文档里会出现字符串化的默认值
        if param.get("default_value"):
            if (
                param.get("default_value") == "null"
                or param.get("default_value") == "undefined"
            ):
                schema["default"] = None
            else:
                # Python 的 match/case 用来把默认值转换成正确的 Python 基础类型
                match param.get("type"):
                    case "string":
                        schema["default"] = str(param.get("default_value"))
                    case "int":
                        schema["default"] = int(param.get("default_value"))
                    case "double":
                        schema["default"] = float(param.get("default_value"))
                    case "boolean":
                        schema["default"] = bool(param.get("default_value"))
                    case _:
                        schema["default"] = param.get("default_value")

        return schema

    def _build_root_schema(params: List[Dict], schema_name: str = None) -> Dict:
        """
        构建根对象的 Schema（用于 RequestBody 或 Response Content）。
        将一组参数列表转换为一个 Object Schema。
        如果提供了 schema_name，则将其注册到 components 中并返回引用。
        """
        # 根对象统一用 object 包裹，children 变成 properties，required 单独收集
        schema = {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }
        for p in params:
            schema["properties"][p["name"]] = _build_param_schema(p)
            if p.get("required"):
                schema["required"].append(p["name"])
        # OpenAPI 中空 required 没有意义，清理掉以减少输出噪音
        if not schema["required"]:
            del schema["required"]

        if schema_name:
            # schema_name 存在时，优先注册到 components，正文里只保留 $ref
            components_schemas[schema_name] = schema
            return {"$ref": f"#/components/schemas/{schema_name}"}

        return schema

    for api in apis:
        # 先把请求和响应参数组织成便于 OpenAPI 生成的结构
        request_params_by_location = organizeReqParams(api.request_params)
        response_params_by_status_code = organizeRespParams(api.response_params)

        if api.path not in paths:
            # 为每个 path 创建一级对象，再按 method 写入 operation
            paths.setdefault(api.path, {})

        parameters = []
        for loc in ["query", "path", "header", "cookie"]:
            for p in request_params_by_location.get(loc, []):
                # OpenAPI parameter 对象：name + in + schema 是最核心的三项
                param_obj = {
                    "name": p["name"],
                    "in": loc,
                    "required": p.get("required", False),
                    "schema": _build_param_schema(p),
                }
                if p.get("description"):
                    param_obj["description"] = p["description"]
                parameters.append(param_obj)

        request_body = None
        body_params = request_params_by_location.get("body", [])
        if body_params:
            # body 参数统一包装成 application/json 的 requestBody
            req_name = _to_component_name(api.name) + "Request"
            request_body = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": _build_root_schema(body_params, req_name)
                    }
                },
            }

        responses = {}
        for status_code, params in response_params_by_status_code.items():
            # 不同状态码分别生成独立 response schema，便于前端按返回码理解结构
            suffix = "" if str(status_code) == "200" else str(status_code)
            resp_name = _to_component_name(api.name) + "Response" + suffix
            responses[status_code] = {
                "description": f"Response for {status_code}",
                "content": {
                    "application/json": {
                        "schema": _build_root_schema(params, resp_name)
                    }
                },
            }

        operation = {
            "description": api.description,
            "operationId": api.name,
            "parameters": parameters,
            "responses": responses,
            "deprecated": not api.is_enabled,
        }
        if request_body:
            operation["requestBody"] = request_body

        # 把 method 统一转成 OpenAPI 需要的小写 HTTP method 名称
        method_str = (
            api.method.value.lower()
            if hasattr(api.method, "value")
            else str(api.method).lower()
        )
        paths[api.path][method_str] = operation

    # 组装最终 OpenAPI 文档，info / paths / components 三部分分别描述元信息、路由、可复用 schema
    return {
        "openapi": "3.1.0",
        "info": {
            "title": (
                service.service_uuid if is_latest else service.service.service_uuid
            ),
            "description": service.description
            or (service.service.description if not is_latest else ""),
            "contact": {
                "name": contact.username,
                "email": contact.email,
            },
            "version": service.version,
        },
        "paths": paths,
        "components": {"schemas": components_schemas},
    }
