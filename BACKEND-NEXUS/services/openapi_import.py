import json  # 用于序列化复杂默认值或示例值为 JSON 文本
import re  # 用于简单的字符串规范化（slugify）
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy.orm import Session  # SQLAlchemy 会话类型提示

# 导入枚举与 ORM 模型：枚举用于把 OpenAPI 的类型/位置映射为内部受控值，
# 模型用于创建相应的草稿实体
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
from services.utils import checkServiceIterationPermission  # 权限校验工具


# 最大去引用深度，避免深度嵌套或循环引用导致递归爆栈
_MAX_DEPTH = 24
# 短文本字段的最大长度（example/default 等），超长则截断
_MAX_TEXT_LEN = 256


"""OpenAPI 导入工具。

本模块负责将符合 OpenAPI 规范的文档（OpenAPI 3.x）解析并导入到系统的
`ServiceIteration` / `ApiDraft` / `RequestParamDraft` / `ResponseParamDraft` 等表中。

设计要点：
- 支持从 OpenAPI 的 `paths` 中读取每个 path+method 的 operation，并将其转换为
    系统中的 `ApiDraft`；
- 自动创建 tag 对应的 `ApiCategory`；
- 支持解析 `parameters`、`requestBody`、`responses` 的 schema，并递归展开
    object/array 类型生成参数草稿记录；
- 对 `$ref` 支持有限的递归解析，但会使用深度与已见引用集合避免无限循环。

使用约定：所有导入函数的第一个参数为 SQLAlchemy `Session`（`db`），并返回
描述导入结果的字典或包含 `status`/`message` 的错误结构。
"""


def _safe_long_text(value: Any) -> Optional[str]:
    """将任意值转换为适合存入数据库的长文本（最多不裁剪）。

    - 如果输入为 None，返回 None
    - 基本类型（str/int/float/bool）会直接转换为字符串并 strip
    - 复杂对象会尝试以 JSON 序列化（non-ascii 保留原字符），若失败则 fallback 为 str()
    - 空字符串或仅包含空白的结果会被视为 None

    返回值可直接用于 `description` 等长文本字段。
    """
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
    """类似于 `_safe_long_text`，但对返回长度进行截断（最大 _MAX_TEXT_LEN）。

    用于 `example` 或 `default_value` 等短文本字段，避免把过长文本存入短列。
    """
    text = _safe_long_text(value)
    if text is None:
        return None
    if len(text) > _MAX_TEXT_LEN:
        return text[:_MAX_TEXT_LEN]
    return text


def _normalize_path(path: str) -> str:
    """规范化 OpenAPI 中的 path 字符串，保证以 `/` 开头，空路径视为根 `/`。

    例如：输入 `users/{id}` -> 输出 `/users/{id}`。
    """
    if not path:
        return "/"
    if not path.startswith("/"):
        return "/" + path
    return path


def _slugify(name: str) -> str:
    """将任意名称转换为仅包含字母数字和下划线的短标识符（slug）。

    用于生成 `ApiDraft.name` 的候选标识，避免出现空格、标点等非法字符。
    """
    name = name.strip()
    name = re.sub(r"[^a-zA-Z0-9]+", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_")


def _derive_api_name(method: str, path: str) -> str:
    """根据 HTTP 方法和 path 自动派生一个语义化的 API 名称（候选）。

    例如：`GET /users/{id}` -> `get_users_by_id`。
    返回值会被 `_slugify` 处理并截断到 128 字符以内，作为 `ApiDraft.name` 的建议值。
    """
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
    """从 OpenAPI 的 `content` 字段中挑选首个合适的 JSON schema。

    优先级：`application/json` -> `application/*+json` -> `*/*` -> 其他第一个含 schema 的媒体类型。
    返回值为 schema dict 或 None。
    """
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
    """解析 OpenAPI 文档中以 `#/` 开头的内部引用（JSON Pointer 风格）。

    - 仅解析文档内的引用（非外部 URL）；
    - 如果路径解析失败或引用不指向 dict 则返回 None。
    """
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
    """对 schema 做初步的去引用（dereference）与合并处理。

    - 支持处理 `$ref`（文档内引用）并将引用目标合并回当前节点；
    - 支持 `oneOf`/`anyOf`/`allOf` 的简化处理：取第一个子项并继续去引用；
    - 使用 `depth` 与 `seen_refs` 防止深度或循环引用造成无限递归。

    返回尽量展平后的 schema dict（不做完整的 schema 合并，只提供用于参数类型推断的视图）。
    """
    if depth > _MAX_DEPTH:
        return {}
    if not isinstance(schema, dict):
        return {}

    # 如果当前节点是一个 $ref 引用，解析并合并引用目标
    if "$ref" in schema:
        ref = schema.get("$ref")
        if isinstance(ref, str):
            # 避免循环引用：如果已经见过该 ref，则返回空结构
            if ref in seen_refs:
                return {}
            seen_refs.add(ref)
            # 解析引用到文档内的目标节点（或返回空 dict）
            target = _resolve_ref(doc, ref) or {}
            # 递归去引用目标并复制为基础结构
            merged = dict(_deref_schema(doc, target, depth + 1, seen_refs))
            # 将当前 schema 除 $ref 外的其它属性合并覆盖到目标上，保留局部覆盖
            for k, v in schema.items():
                if k != "$ref":
                    merged[k] = v
            return merged

    # 对组合类型（oneOf/anyOf/allOf）做简单处理：只取第一个子项作为代表进行去引用。
    # 这并不是完全遵循语义合并的实现，但足以用于类型/属性的静态推断。
    for comb_key in ("oneOf", "anyOf", "allOf"):
        items = schema.get(comb_key)
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                merged = dict(_deref_schema(doc, first, depth + 1, seen_refs))
                # 将组合节点上非组合相关的键合并回结果，保留局部配置
                for k, v in schema.items():
                    if k not in (comb_key,):
                        merged[k] = v
                return merged

    return schema


def _map_schema_type(schema: Dict[str, Any]) -> Tuple[ParamType, Optional[ParamType]]:
    # 读取 JSON Schema 的 type 与 format 字段以作映射决策
    t = schema.get("type")
    fmt = schema.get("format")

    # 如果缺失 type，但存在 properties，则通常表示一个对象类型
    if t is None and isinstance(schema.get("properties"), dict):
        return (ParamType.OBJECT, None)

    # 映射基本类型
    if t == "object":
        return (ParamType.OBJECT, None)
    if t == "array":
        # 对数组类型，解析 items 字段以获得元素类型（array_child_type）
        items = schema.get("items")
        if isinstance(items, dict):
            item_t, _ = _map_schema_type(items)
            return (ParamType.ARRAY, item_t)
        # items 不明确时，默认数组元素为 string
        return (ParamType.ARRAY, ParamType.STRING)
    if t == "integer":
        return (ParamType.INT, None)
    if t == "number":
        return (ParamType.DOUBLE, None)
    if t == "boolean":
        return (ParamType.BOOLEAN, None)
    if t == "string":
        # format 可以指示更特殊的字符串类型，例如 binary
        if fmt == "binary":
            return (ParamType.BINARY, None)
        return (ParamType.STRING, None)

    # 缺省退回到字符串类型以保证兼容性
    return (ParamType.STRING, None)


def _iter_object_properties(schema: Dict[str, Any]) -> Iterable[Tuple[str, Dict[str, Any], bool]]:
    """遍历 object schema 的 `properties` 并返回 (name, schema, required) 的可迭代列表。

    - 若 schema 不包含 `properties` 或类型不正确则返回空列表。
    - `required` 字段会被解析为集合以判断子属性是否为必需。
    """
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
    """根据给定的 schema 创建一个 `RequestParamDraft`（并递归创建子参数）。

    步骤：
    1. 对 schema 做去引用处理以得到可用视图；
    2. 映射为内部的 `ParamType` 与（可选的）`array_child_type`；
    3. 创建并 flush 一个 `RequestParamDraft` 记录；
    4. 若为 object 类型则遍历其 properties 递归创建子参数；
    5. 若为 array 且元素为 object，同样递归创建元素的子属性作为子参数。

    返回创建的 `RequestParamDraft` 实例。
    """
    # 首先对 schema 做去引用和合并，得到一个更易消费的视图
    resolved = _deref_schema(doc, schema, depth=0, seen_refs=set())
    # 将 JSON Schema 类型映射到内部 ParamType（并获取 array 元素类型）
    param_type, array_child_type = _map_schema_type(resolved)

    # 创建参数草稿记录，注意 description 与 example 使用安全的文本截断/序列化函数
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
    # 将新创建的 param 对象加入到会话，但不提交：
    # - db.add 将对象标记为 pending，flush 会将其写入 DB 并分配主键
    # - 使用 flush 是为了在同一事务中获取 param.id 用于子参数的 parent_param_id
    db.add(param)
    db.flush()

    # 如果当前参数是 object，则遍历其 properties 并作为子参数递归创建
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

    # 如果是数组且元素为 object，则对 items schema 的 properties 创建为子参数
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
    """根据给定的 schema 创建一个 `ResponseParamDraft`（并递归创建子参数）。

    行为与 `_create_request_param_from_schema` 类似，但会额外记录 `status_code`。
    返回创建的 `ResponseParamDraft` 实例。
    """
    # 去引用并映射类型（同请求参数处理，但包含 status_code）
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
    # 将响应参数加入会话并 flush 获得 id，后续用于递归子属性 parent_param_id
    db.add(param)
    db.flush()

    # 递归创建对象/数组元素的子属性
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
    """删除指定 iteration 下的所有 ApiDraft 及其关联的参数草稿。

    实现细节：
    - 先收集目标 iteration 下的所有 `ApiDraft.id`；
    - 批量删除 `RequestParamDraft` / `ResponseParamDraft` 中与这些 id 相关的记录；
    - 最后删除 `ApiDraft` 本体。

    使用场景：在向已有 iteration 导入新 OpenAPI 时先清空已有草稿。
    """
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
    """从 OpenAPI 文档中逐条创建 `ApiDraft` 与其参数草稿，并返回导入统计信息。

    主要步骤：
    - 为每个 path+method 创建 `ApiDraft`（自动挑选 name、category 等）；
    - 解析并创建 `parameters`、`requestBody` 与 `responses` 对应的参数草稿，支持递归 object/array；
    - 自动创建 OpenAPI tag 对应的 `ApiCategory` 并缓存映射以减少 DB 查询；
    - 收集导入计数与警告信息返回给调用者。

    返回结构示例：{
        'apis': n, 'request_params': m, 'response_params': k, 'categories': c, 'warnings': [...] }
    """
    tag_to_category_id: Dict[str, int] = {}

    def _get_or_create_category_id(tag_name: str) -> Optional[int]:
        # 归一化并去除空白
        tag_name = (tag_name or "").strip()
        # 空 tag 不创建分类
        if not tag_name:
            return None
        # 如果已经在本次导入中缓存过该 tag，则直接返回缓存的 id
        if tag_name in tag_to_category_id:
            return tag_to_category_id[tag_name]
        # 查询数据库判断该服务下是否已有同名分类
        existing_cat = (
            db.query(ApiCategory)
            .filter(ApiCategory.service_id == service_id, ApiCategory.name == tag_name)
            .first()
        )
        if existing_cat:
            # 缓存 id 并返回
            tag_to_category_id[tag_name] = existing_cat.id
            return existing_cat.id
        # 不存在则创建新分类并 flush 以获取 id
        new_cat = ApiCategory(service_id=service_id, name=tag_name, description=None)
        db.add(new_cat)
        # flush 使数据库分配新记录的 id（在后续把 category_id 写入 api_draft 时可以使用）
        db.flush()
        # 缓存 id 并返回，避免在同一次导入中重复创建同名分类
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
        # path 级别的 parameters（会应用到该 path 下所有方法）
        common_parameters = (
            path_item.get("parameters")
            if isinstance(path_item.get("parameters"), list)
            else []
        )

        # 仅处理常见的 HTTP 方法（忽略其它扩展方法）
        # 仅处理常用 HTTP 方法：get/post/put/delete/patch；忽略 vendor/extension 方法
        for method in ("get", "post", "put", "delete", "patch"):
            op = path_item.get(method)
            if not isinstance(op, dict):
                continue

            # 将方法字符串映射成内部 HttpMethod 枚举，若不可识别则记录警告并跳过
            # 将方法字符串映射为内部 HttpMethod 枚举；如果枚举中不存在该方法则记录警告并跳过
            try:
                method_enum = HttpMethod[method.upper()]
            except KeyError:
                warnings.append(f"Unsupported http method: {method}")
                continue

            # 优先使用 operationId，其次使用 summary 作为 name 候选项
            # 构造 API 名称：优先使用 operationId，再用 summary，否则由 method+path 推导
            operation_id = op.get("operationId")
            summary = op.get("summary")
            name_candidate = (
                operation_id
                if isinstance(operation_id, str) and operation_id.strip()
                else summary
            )
            if not isinstance(name_candidate, str) or not name_candidate.strip():
                name_candidate = _derive_api_name(method, path)
            # 使用 slugify 来生成安全的 name，截断到 128 字符
            name = _slugify(name_candidate)[:128] or _derive_api_name(method, path)

            # 记录基础名称以便发生冲突时追加后缀
            # 保证名称在本次导入中唯一：若重复则在尾部追加递增后缀
            base_name = name
            idx = 2
            while name in used_names:
                suffix = f"_{idx}"
                # 若拼接后超长则先截断 base_name，再拼接后缀，保持总长度不超过 128
                name = (
                    (base_name[: (128 - len(suffix))] + suffix)
                    if len(base_name) + len(suffix) > 128
                    else base_name + suffix
                )
                idx += 1
            used_names.add(name)

            # tags 列表的第一个 tag 用作分类名（若存在）
            # 从 operation 的 tags 中取第一个 tag 作为分类名（如果存在）
            # 使用第一个 tag 作为分类名（如果存在），并获取/创建对应的 ApiCategory id
            tags = op.get("tags") if isinstance(op.get("tags"), list) else []
            first_tag = tags[0] if tags and isinstance(tags[0], str) else ""
            category_id = _get_or_create_category_id(first_tag)

            # 创建 ApiDraft 实体，注意 description 使用安全序列化函数
            # 创建 ApiDraft 实体并写入会话（尚未提交）。description 优先使用 description 字段，退回到 summary
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
            # 将草稿加入 session，随后 flush 以获得 id
            db.add(api_draft)
            db.flush()
            imported_api_count += 1

            # 汇总 path 级别和 operation 级别的 parameters，后续去重处理
            # 汇总 path 级与 operation 级别的参数定义，后续按 (name,in) 去重
            all_parameters: List[Any] = []
            if isinstance(common_parameters, list):
                all_parameters.extend(common_parameters)
            op_parameters = (
                op.get("parameters") if isinstance(op.get("parameters"), list) else []
            )
            if isinstance(op_parameters, list):
                all_parameters.extend(op_parameters)

            # 参数去重：使用 (name, in) 组合作为 key
            # 去重并处理每个参数：使用 (name,in) 组合作为唯一键
            seen_param_keys: Set[Tuple[str, str]] = set()
            for p in all_parameters:
                if not isinstance(p, dict):
                    continue
                # 对参数可能的 $ref 进行去引用，得到展平后的参数对象视图
                p_resolved = _deref_schema(openapi_object, p, depth=0, seen_refs=set())
                pname = p_resolved.get("name")
                pin = p_resolved.get("in")
                if not isinstance(pname, str) or not isinstance(pin, str):
                    continue
                key = (pname, pin)
                if key in seen_param_keys:
                    continue
                seen_param_keys.add(key)

                # 将 OpenAPI 的 in 字段转换为内部 ParamLocation 枚举；若不支持则记录警告并跳过
                try:
                    location_enum = ParamLocation(pin)
                except Exception:
                    warnings.append(f"Unsupported param location: {pin}")
                    continue

                # 获取参数的 schema（若存在），否则使用空 dict 作为占位
                schema = (
                    p_resolved.get("schema")
                    if isinstance(p_resolved.get("schema"), dict)
                    else {}
                )
                # path 类型参数在 OpenAPI 中应被视为必需
                required = bool(p_resolved.get("required")) or (
                    location_enum == ParamLocation.PATH
                )

                # 将参数展平并写入 RequestParamDraft（内部会递归创建子属性）
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

            # 处理 requestBody：优先挑选 JSON schema 并根据是否为 object 展开为多个字段或作为整体 body
            # 处理 requestBody：优先选取 JSON schema，并根据其是否为 object 决定展开为多字段或作为整体 body
            request_body = op.get("requestBody")
            if isinstance(request_body, dict):
                # 先去引用 requestBody（支持 $ref）
                rb_resolved = _deref_schema(openapi_object, request_body, depth=0, seen_refs=set())
                schema = None
                content = rb_resolved.get("content")
                if isinstance(content, dict):
                    schema = _pick_content_schema(content)
                if isinstance(schema, dict):
                    schema_resolved = _deref_schema(openapi_object, schema, depth=0, seen_refs=set())
                    # 若 schema 是对象，则逐个 properties 创建为 body 的子参数
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
                        # 非对象（例如数组或标量），把整个 request body 视为单个字段 'body'
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

            # 处理 responses：迭代每个 status code，挑选 content 中的 JSON schema 并展开
            # 处理 responses：遍历每个 status code，挑选 JSON schema 并按是否为对象决定展开策略
            responses = op.get("responses")
            if isinstance(responses, dict):
                for scode_raw, resp in responses.items():
                    # 跳过 default 条目，专注数值状态码
                    if scode_raw == "default":
                        continue
                    try:
                        status_code = int(scode_raw)
                    except Exception:
                        # 非标准数值状态码忽略
                        continue
                    if not isinstance(resp, dict):
                        continue
                    # 去引用 response 对象以处理 $ref
                    resp_resolved = _deref_schema(openapi_object, resp, depth=0, seen_refs=set())
                    schema = None
                    content = resp_resolved.get("content")
                    if isinstance(content, dict):
                        schema = _pick_content_schema(content)
                    if not isinstance(schema, dict):
                        continue

                    schema_resolved = _deref_schema(openapi_object, schema, depth=0, seen_refs=set())
                    # 若 response body 为对象，则将 properties 展开为独立 response 参数
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
                        # 非对象时，将整个响应体视为名为 'data' 的字段并写入一条 response param
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

def import_openapi_to_iteration(
    db: Session,
    service_iteration_id: int,
    openapi_object: Dict[str, Any],
    user_id: int,
) -> Dict[str, Any]:
    """将 OpenAPI 文档导入到已存在且由当前用户有权限操作的 `ServiceIteration` 中。

    行为：先清空该 iteration 下现有的草稿（`ApiDraft` 等），然后按文档重新生成草稿。
    返回导入统计或错误信息。
    """
    # 校验当前用户对指定 iteration 的操作权限
    check_res = checkServiceIterationPermission(
        db=db, service_iteration_id=service_iteration_id, user_id=user_id
    )
    if not check_res.get("is_ok"):
        # 若权限检查未通过，直接返回权限检查函数提供的错误结构
        return check_res.get("error")  # type: ignore

    # 权限通过后取出 iteration 实体与对应的 service_id
    iteration: ServiceIteration = check_res["service_iteration"]
    service_id = iteration.service_id

    if not isinstance(openapi_object, dict) or not isinstance(openapi_object.get("paths"), dict):
        return {"status": -5, "message": "Invalid OpenAPI document: missing 'paths'"}
    if "swagger" in openapi_object and "openapi" not in openapi_object:
        return {"status": -6, "message": "Swagger 2.0 is not supported yet"}

    # 执行删除现有草稿并按文档重新填充的操作，发生异常则回滚
    try:
        # 清空该 iteration 下现有的 ApiDraft 与参数草稿
        _replace_iteration_drafts(db=db, service_iteration_id=service_iteration_id)
        # 从文档填充新的草稿
        imported = _fill_iteration_from_openapi(
            db=db,
            service_id=service_id,
            service_iteration_id=service_iteration_id,
            openapi_object=openapi_object,
            user_id=user_id,
        )
        # 成功后提交事务
        db.commit()
    except Exception as e:
        # 出错时回滚并返回错误信息
        db.rollback()
        return {"status": -7, "message": f"Import OpenAPI failed: {e}"}

    return {
        "status": 200,
        "message": "Import OpenAPI to iteration success",
        "service_iteration_id": service_iteration_id,
        "imported": imported,
    }
