"""API 服务层方法集合（业务逻辑），与数据库模型交互。

本模块提供一组面向业务的函数，用于：
- 查询/管理 API 分类（`ApiCategory`）
- 查询/管理 API 及其草稿（`Api` / `ApiDraft`）
- 处理请求/响应参数的创建、复制和序列化

约定：所有函数第一个参数均为 SQLAlchemy 的 `Session` 实例（`db`），并返回包含
`status` 与 `message` 的字典（必要时包含额外数据字段，例如 `apis` / `api` / `category`）。
"""

import time
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database.models import (
    Service,
    Api,
    ApiCategory,
    User,
    ApiDraft,
    RequestParamDraft,
    ResponseParamDraft,
)
from database.enums import ApiLevel, HttpMethod, ParamType, ParamLocation
from services.utils import (
    checkServiceIterationPermission,
    organizeReqParams,
    organizeRespParams,
)


# 通过service_id获取全部categories
def apiGetAllCategoriesByServiceId(db: Session, service_id: int, user_id: int) -> dict:
    """根据 `service_id` 返回该服务下的所有 `ApiCategory`。

    权限：非 L0（最高级别）用户只能查看自己拥有或维护的服务。

    返回格式示例：
    {
        "status": 200,
        "message": "Get all categories success",
        "categories": [ ... ]
    }
    """
    service = db.get(Service, service_id)
    if not service:
        return {
            "status": -1,
            "message": "Service not found",
        }
    # 非L0用户只能查看自己的服务
    user = db.get(User, user_id)
    if service.owner_id != user_id and user.level.value != 0:  # type: ignore
        return {
            "status": -2,
            "message": "You are not the owner of this service",
        }
    # 查询并按主键顺序返回分类列表
    categories = (
        db.query(ApiCategory)
        .filter(ApiCategory.service_id == service_id)
        .order_by(ApiCategory.id)
        .all()
    )
    return {
        "status": 200,
        "message": "Get all categories success",
        "categories": [category.toJson() for category in categories],
    }


# 通过service_id获取全部api（最新版本，可带category_id，不包括api内包含的params）
# ⚠️ 注意：这个方法和service/serviceGetServiceByUuidAndVersion()类似。区别在于这个方法返回的只有apis，不包含service的其他信息；另外这个方法支持通过category_id筛选。
def apiGetAllApisByServiceId(
    db: Session, service_id: int, user_id: int, category_id: int | None = None
) -> dict:
    """获取服务的所有 API（仅返回最新生效表 `Api`），可按 `category_id` 过滤。

    注意：该函数只返回 API 列表，不包含 `Service` 的其他字段。
    权限：非 L0 用户只能查看自己拥有或维护的服务。
    """
    service = db.get(Service, service_id)
    if not service:
        return {
            "status": -1,
            "message": "Service not found",
        }
    # 非L0用户只能查看自己的服务
    user = db.get(User, user_id)
    if service.owner_id != user_id and user.level.value != 0:  # type: ignore
        return {
            "status": -2,
            "message": "You are not the owner of this service",
        }
    # 查询不包含软删除的 API（`is_deleted` 字段为 False）
    query = db.query(Api).filter(Api.service_id == service_id, ~Api.is_deleted)
    if category_id is not None:
        query = query.filter(Api.category_id == category_id)
    apis = query.order_by(Api.id.desc()).all()
    return {
        "status": 200,
        "message": "Get all apis success",
        "apis": [api.toJson() for api in apis],
    }


# 通过api_id获取api详情（包括api内包含的params）
# 若传入is_latest为False，则api_id为api_draft_id，对应的是历史版本的api，相应params也来自param_draft
def apiGetApiById(
    db: Session, api_id: int, user_id: int, is_latest: bool = True
) -> dict:
    """获取单个 API 详情。

    参数：
    - `is_latest=True` 时，`api_id` 指向正式表 `Api`；
    - `is_latest=False` 时，`api_id` 指向草稿表 `ApiDraft`（例如历史版本）。

    返回会包含序列化的字段以及按 location/status 分组的参数。
    权限控制：非 L0 用户需为服务 owner、maintainer 或 iteration 的 creator（草稿场景）。
    """
    api = db.get(Api, api_id) if is_latest else db.get(ApiDraft, api_id)
    if not api:
        return {
            "status": -1,
            "message": "Api not found",
        }
    # 非L0用户只能查看自己的服务
    user = db.get(User, user_id)
    if not user:
        return {
            "status": -2,
            "message": "User not found",
        }
    if user.level.value != 0:
        if (
            is_latest
            and api.service.owner_id != user_id
            and user not in api.service.maintainers
        ):
            return {
                "status": -3,
                "message": "You are neither the owner nor the maintainer of this service",
            }
        elif (
            not is_latest
            and api.service_iteration.creator_id != user_id
            and user not in api.service_iteration.service.maintainers
            and api.service_iteration.service.owner_id != user_id
        ):
            return {
                "status": -4,
                "message": "You are neither the owner nor the maintainer of this service, nor the creator of this service iteration",
            }
    # 处理并组织请求/响应参数为更易消费的结构（按 location 或 status code 分类）
    request_params_by_location = organizeReqParams(api.request_params)
    response_params_by_status_code = organizeRespParams(api.response_params)

    # 使用模型的 toJson 方法序列化实体，排除大体量或冗余的关系字段，
    # 以便把参数数据以更友好的结构放到顶层返回给前端。
    api_info = api.toJson(
        include_relations=True,
        exclude=[
            "request_params",
            "response_params",
            "service",
            "service_iteration",
            "category",
        ],
    )
    api_info["request_params_by_location"] = request_params_by_location
    api_info["response_params_by_status_code"] = response_params_by_status_code
    return {
        "status": 200,
        "message": "Get api success",
        "api": api_info,
    }


# 通过service_id新增category
def apiAddCategoryByServiceId(
    db: Session,
    service_id: str,
    user_id: int,
    category_name: str,
    description: str | None = None,
) -> dict:
    """为指定服务添加一个新的 `ApiCategory`。

    权限：非 L0 用户需为服务 owner 或 maintainer。
    返回新创建的 category 的 `toJson()`。
    """
    service = db.get(Service, service_id)
    if not service:
        return {
            "status": -1,
            "message": "Service not found",
        }
    # 非L0用户只能操作自己的服务
    user = db.get(User, user_id)
    if service.owner_id != user_id and user not in service.maintainers and user.level.value != 0:  # type: ignore
        return {
            "status": -2,
            "message": "You are neither the owner nor the maintainer of this service",
        }
    # 检查 category 名称在该服务下是否已存在，保持同一服务中分类名唯一
    existing_category = (
        db.query(ApiCategory)
        .filter(ApiCategory.service_id == service_id, ApiCategory.name == category_name)
        .first()
    )
    if existing_category:
        return {
            "status": -3,
            "message": "Category name already exists",
        }
    category = ApiCategory(
        service_id=service_id, name=category_name, description=description
    )
    db.add(category)
    db.commit()
    return {
        "status": 200,
        "message": "Add category success",
        "category": category.toJson(),
    }


# 通过category_id删除category
def apiDeleteCategoryById(db: Session, category_id: int, user_id: int) -> dict:
    """删除指定的 `ApiCategory`。

    权限：非 L0 用户需为服务 owner 或 maintainer。
    注意：删除分类不会自动修改该分类下的 API，需由上层调用者保证数据一致性或在前端提醒。
    """
    category = db.get(ApiCategory, category_id)
    if not category:
        return {
            "status": -1,
            "message": "Category not found",
        }
    # 非L0用户只能操作自己的服务
    user = db.get(User, user_id)
    if not user:
        return {
            "status": -2,
            "message": "User not found",
        }
    if category.service.owner_id != user_id and user not in category.service.maintainers and user.level.value != 0:  # type: ignore
        return {
            "status": -3,
            "message": "You are neither the owner nor the maintainer of this service",
        }
    db.delete(category)
    db.commit()
    return {
        "status": 200,
        "message": "Delete category success",
    }


# 通过category_id修改category
def apiUpdateCategoryById(
    db: Session,
    category_id: int,
    user_id: int,
    category_name: str | None = None,
    description: str | None = None,
) -> dict:
    """更新分类名称或描述。

    - 若 `category_name` 与 `description` 均为空，则返回错误；
    - 若新名称与已有分类冲突则返回错误。
    """
    category = db.get(ApiCategory, category_id)
    if not category:
        return {
            "status": -1,
            "message": "Category not found",
        }
    # 非L0用户只能操作自己的服务
    user = db.get(User, user_id)
    if not user:
        return {
            "status": -2,
            "message": "User not found",
        }
    if category.service.owner_id != user_id and user.level.value != 0:
        return {
            "status": -3,
            "message": "You are not the owner of this service",
        }
    if category_name is None and description is None:
        return {
            "status": -4,
            "message": "Category name or description is required",
        }
    if category_name == category.name and description == category.description:
        return {
            "status": -5,
            "message": "Category name or description not changed",
        }
    # 检查category_name是否已存在
    existing_category = (
        db.query(ApiCategory)
        .filter(
            ApiCategory.service_id == category.service_id,
            ApiCategory.name == category_name,
        )
        .first()
    )
    if existing_category:
        return {
            "status": -6,
            "message": "Category name already exists",
        }
    category.name = category_name  # type: ignore
    category.description = description  # type: ignore
    db.commit()
    return {
        "status": 200,
        "message": "Update category success",
        "category": category.toJson(),
    }


# 通过api_id、category_id修改api所属分类（仅支持修改正式表Api，不支持草稿表ApiDraft）
def apiUpdateApiCategory(
    db: Session, api_id: int, category_id: int, user_id: int
) -> dict:
    """将某个正式 API (`Api`) 从一个分类移动到另一个分类。

    - `category_id == -1` 表示移除分类（设为未分类 / NULL）
    - 仅支持对正式表 `Api` 的修改，不影响草稿 `ApiDraft`
    """
    api = db.get(Api, api_id)
    if not api:
        return {
            "status": -1,
            "message": "Api not found",
        }
    # 非L0用户只能操作自己的服务
    user = db.get(User, user_id)
    if not user:
        return {
            "status": -2,
            "message": "User not found",
        }
    if api.service.owner_id != user_id and user not in api.service.maintainers and user.level.value != 0:  # type: ignore
        return {
            "status": -3,
            "message": "You are neither the owner nor the maintainer of this service",
        }
    if api.category_id == category_id:  # type: ignore
        return {
            "status": -4,
            "message": "Api category not changed",
        }
    # 分类ID为-1时，设为未分类
    if category_id == -1:
        api.category_id = None  # type: ignore
        db.commit()
        return {
            "status": 200,
            "message": "Update api category success",
        }
    category = db.get(ApiCategory, category_id)
    if not category:
        return {
            "status": -5,
            "message": "Category not found",
        }
    if category.service_id != api.service_id:  # type: ignore
        return {
            "status": -6,
            "message": "Category not belongs to this service",
        }
    api.category_id = category_id  # type: ignore
    db.commit()
    return {
        "status": 200,
        "message": "Update api category success",
    }


# ---- ⚠️ 以下为service迭代流程相关方法 ----
# 通过service_iteration_id新增api（存ApiDraft表，可指定category_id）
def apiAddApi(
    db: Session,
    service_iteration_id: int,
    user_id: int,
    name: str,
    method: str,
    path: str,
    description: str,
    level: str,
    category_id: int | None = None,
) -> dict:
    """在指定的 `service_iteration` 下新增一个 API 草稿（写入 `ApiDraft`）。

    主要步骤：
    1. 调用 `checkServiceIterationPermission` 验证当前用户是否有在该迭代中修改的权限；
    2. 检查在当前服务或当前迭代下是否存在同名/同 path 的 API 或草稿，避免冲突；
    3. 将传入的 method/level 等值转换为对应的 Enum，若非法则使用默认值；
    4. 创建 `ApiDraft` 记录并提交。
    """
    # 版本迭代行为权限校验
    check_res = checkServiceIterationPermission(
        db=db, service_iteration_id=service_iteration_id, user_id=user_id
    )
    if not check_res["is_ok"]:
        return check_res["error"]
    service_iteration = check_res["service_iteration"]
    # 检查当前服务中是否已存在同名同路径的api
    # 当前服务最新版本的api
    existing_api = (
        db.query(Api)
        .filter(
            Api.service_id == service_iteration.service_id,
            Api.method == method,
            or_(
                Api.path == path,
                Api.name == name,
            ),
        )
        .first()
    )
    # 当前迭代周期的api草稿
    existing_api_draft = (
        db.query(ApiDraft)
        .filter(
            ApiDraft.service_iteration_id == service_iteration_id,
            ApiDraft.method == method,
            or_(
                ApiDraft.path == path,
                ApiDraft.name == name,
            ),
        )
        .first()
    )
    if existing_api or existing_api_draft:
        return {
            "status": -1,
            "message": "Api method and name/path already exists in this service",
        }
    # 符合新增条件
    # 将传入字符串转换为枚举，若出错使用安全默认值
    try:
        api_method = HttpMethod(method)
    except ValueError:
        api_method = HttpMethod.GET
    try:
        api_level = ApiLevel(level)
    except ValueError:
        api_level = ApiLevel.P2
    # 若有category_id，检查category_id是否属于该服务
    if category_id is not None:
        category = db.get(ApiCategory, category_id)
        if not category:
            return {
                "status": -2,
                "message": "Category not found",
            }
        if category.service_id != service_iteration.service_id:
            return {
                "status": -3,
                "message": "Category not belongs to this service",
            }

    api_draft = ApiDraft(
        service_iteration_id=service_iteration_id,
        owner_id=user_id,
        name=name,
        method=api_method,
        path=path,
        description=description,
        level=api_level,
        category_id=category_id,
    )
    db.add(api_draft)
    db.commit()
    return {
        "status": 200,
        "message": "Add api success",
        "api": api_draft.toJson(),
    }


# 辅助函数：递归复制参数列表，支持嵌套的object类型参数
def _copy_params_recursively(
    db: Session,
    source_params: list,
    target_api_draft_id: int,
    parent_param_id: int | None = None,
    param_model_class=RequestParamDraft,
) -> None:
    """辅助：递归复制一组参数（请求或响应草稿），保持父子关系。

    说明：用于在复制 API 草稿时把参数从原草稿复制到新草稿，支持嵌套子参数。
    - `param_model_class` 决定使用 `RequestParamDraft` 还是 `ResponseParamDraft`。
    - 复制时会 `flush()` 以获取新记录的 `id`，便于为子参数设置 `parent_param_id`。
    """
    for param in source_params:
        if param_model_class is RequestParamDraft:
            new_param = RequestParamDraft(
                api_draft_id=target_api_draft_id,
                name=param.name,
                location=param.location,
                type=param.type,
                required=param.required,
                default_value=param.default_value,
                description=param.description,
                example=param.example,
                array_child_type=param.array_child_type,
                parent_param_id=parent_param_id,
            )
        else:
            new_param = ResponseParamDraft(
                api_draft_id=target_api_draft_id,
                status_code=param.status_code,
                name=param.name,
                type=param.type,
                required=param.required,
                description=param.description,
                example=param.example,
                array_child_type=param.array_child_type,
                parent_param_id=parent_param_id,
            )

        db.add(new_param)
        db.flush()  # 获取新创建记录的ID，便于递归创建子参数时设置 parent_param_id

        # 如果该参数含有子参数，则递归复制子参数
        if param.child_params:
            _copy_params_recursively(
                db=db,
                source_params=param.child_params,
                target_api_draft_id=target_api_draft_id,
                parent_param_id=new_param.id,
                param_model_class=param_model_class,
            )


# 通过service_iteration_id、api_draft_id复制api
def apiCopyApiByApiDraftId(
    db: Session, service_iteration_id: int, api_draft_id: int, user_id: int
) -> dict:
    """复制指定 `ApiDraft` 为同一 `service_iteration` 下的新草稿。

    复制行为包括：
    - 复制 API 草稿本体（名称与 path 会加后缀保证唯一性）
    - 递归复制所有请求/响应参数（保持父子关系）
    """
    # 版本迭代行为权限校验
    check_res = checkServiceIterationPermission(
        db=db, service_iteration_id=service_iteration_id, user_id=user_id
    )
    if not check_res["is_ok"]:
        return check_res["error"]
    api_draft = db.get(ApiDraft, api_draft_id)
    if not api_draft:
        return {
            "status": -1,
            "message": "Api draft not found",
        }
    if api_draft.service_iteration_id != service_iteration_id:  # type: ignore
        return {
            "status": -2,
            "message": "Api draft not belongs to this service iteration",
        }
    # 符合复制条件
    # 使用时间戳后缀创建新的 name/path，避免与现有项冲突
    timestamp = int(time.time())
    new_name = f"{api_draft.name}-copy-{timestamp}"
    new_path = f"{api_draft.path}-copy-{timestamp}"

    new_api_draft = ApiDraft(
        service_iteration_id=service_iteration_id,
        owner_id=user_id,
        name=new_name,
        method=api_draft.method,
        path=new_path,
        description=api_draft.description,
        level=api_draft.level,
        category_id=api_draft.category_id,
        is_enabled=api_draft.is_enabled,
    )
    db.add(new_api_draft)
    db.flush()

    # 复制请求参数
    root_req_params = [p for p in api_draft.request_params if p.parent_param_id is None]
    if root_req_params:
        _copy_params_recursively(
            db=db,
            source_params=root_req_params,
            target_api_draft_id=new_api_draft.id,
            parent_param_id=None,
            param_model_class=RequestParamDraft,
        )

    # 复制响应参数
    root_resp_params = [
        p for p in api_draft.response_params if p.parent_param_id is None
    ]
    if root_resp_params:
        _copy_params_recursively(
            db=db,
            source_params=root_resp_params,
            target_api_draft_id=new_api_draft.id,
            parent_param_id=None,
            param_model_class=ResponseParamDraft,
        )

    db.commit()
    return {
        "status": 200,
        "message": "Copy api success",
    }


# 通过service_iteration_id、api_draft_id删除api
def apiDeleteApiByApiDraftId(
    db: Session, service_iteration_id: int, api_draft_id: int, user_id: int
) -> dict:
    """删除指定的 API 草稿（包括其所有请求/响应参数）。

    删除采用显式的级联删除逻辑：先删除 params，再删除草稿实体，最后提交事务。
    """
    # 版本迭代行为权限校验
    check_res = checkServiceIterationPermission(
        db=db, service_iteration_id=service_iteration_id, user_id=user_id
    )
    if not check_res["is_ok"]:
        return check_res["error"]
    api_draft = db.get(ApiDraft, api_draft_id)
    if not api_draft:
        return {
            "status": -1,
            "message": "Api draft not found",
        }
    if api_draft.service_iteration_id != service_iteration_id:  # type: ignore
        return {
            "status": -2,
            "message": "Api draft not belongs to this service iteration",
        }
    # 符合删除条件
    db.query(RequestParamDraft).filter(
        RequestParamDraft.api_draft_id == api_draft_id
    ).delete(synchronize_session=False)
    db.query(ResponseParamDraft).filter(
        ResponseParamDraft.api_draft_id == api_draft_id
    ).delete(synchronize_session=False)
    db.delete(api_draft)
    db.commit()
    return {
        "status": 200,
        "message": "Delete api success",
    }


# 通过service_iteration_id、api_draft_id编辑api（包括api自有属性、请求params和响应params）
"""
约定req_params参数格式（支持嵌套结构）：
[
    {
        "name": "user",
        "location": "body",
        "type": "object",
        "required": true,
        "default_value": null,
        "description": "用户信息",
        "example": "{}",
        "array_child_type": null,
        "children": [
            {
                "name": "name",
                "type": "string",
                "required": true,
                "default_value": null,
                "description": "用户姓名",
                "example": "张三",
                "array_child_type": null,
                "children": null
            },
            {
                "name": "profile",
                "type": "object",
                "required": false,
                "default_value": null,
                "description": "用户档案",
                "example": "{}",
                "array_child_type": null,
                "children": [
                    {
                        "name": "age",
                        "type": "int",
                        "required": true,
                        "default_value": null,
                        "description": "年龄",
                        "example": "25",
                        "array_child_type": null,
                        "children": null
                    }
                ]
            }
        ]
    },
    {
        "name": "tags",
        "location": "query",
        "type": "array",
        "required": false,
        "default_value": null,
        "description": "标签列表",
        "example": "[\"tag1\", \"tag2\"]",
        "array_child_type": "string",
        "children": null
    }
]

说明：
- 对于object类型的参数，使用children字段存储子参数
- 对于array类型的参数，使用array_child_type指定数组元素类型
- 对于array类型的参数，若array_child_type为object类型，则children字段存储数组元素子参数
- 子参数不需要location字段，会继承父参数的location
- children为null表示该参数没有子参数
"""


# 辅助函数：递归处理参数列表，支持嵌套的object类型参数
def _process_params_recursively(
    db: Session,
    params: list,
    api_draft_id: int,
    parent_param_id: int | None = None,
    parent_location: str | None = None,
    param_model_class=RequestParamDraft,
) -> None:
    """辅助：递归创建参数记录（支持嵌套 object 与 array 的元素为 object 的场景）。

    输入格式参考文件顶部注释中的示例 JSON。函数会：
    - 解析并验证 `location` / `type` 等字段，将字符串转换为对应的枚举（非法值使用默认）
    - 处理 `array_child_type`（若存在）并转换为枚举
    - 对 object/array-of-object 类型递归处理其 `children`
    - 为子参数自动继承父参数的 `location`
    """
    for param in params:
        param_name = param["name"]
        param_type = param["type"]
        param_required = param.get("required", False)
        param_default_value = param.get("default_value")
        param_description = param.get("description")
        param_example = param.get("example")
        param_array_child_type = param.get("array_child_type")
        param_children = param.get("children")

        # 确定参数位置：子参数继承父参数的 location
        if parent_location:
            param_location = parent_location
        else:
            param_location = param.get("location", "body")

        # 验证并转换枚举值
        try:
            param_location_enum = ParamLocation(param_location)
        except ValueError:
            param_location_enum = ParamLocation.BODY

        try:
            param_type_enum = ParamType(param_type)
        except ValueError:
            param_type_enum = ParamType.STRING

        # 处理array_child_type
        param_array_child_type_enum = None
        if param_array_child_type:
            try:
                param_array_child_type_enum = ParamType(param_array_child_type)
            except ValueError:
                param_array_child_type_enum = None

        # 创建参数记录（区分请求与响应的模型）
        if param_model_class is RequestParamDraft:
            param_record = RequestParamDraft(
                api_draft_id=api_draft_id,
                name=param_name,
                location=param_location_enum,
                type=param_type_enum,
                required=param_required,
                default_value=param_default_value,
                description=param_description,
                example=param_example,
                array_child_type=param_array_child_type_enum,
                parent_param_id=parent_param_id,
            )
        else:  # ResponseParamDraft
            # 响应参数需要status_code，这里使用默认值200
            status_code = param.get("status_code", 200)
            param_record = ResponseParamDraft(
                api_draft_id=api_draft_id,
                status_code=status_code,
                name=param_name,
                type=param_type_enum,
                required=param_required,
                description=param_description,
                example=param_example,
                array_child_type=param_array_child_type_enum,
                parent_param_id=parent_param_id,
            )

        db.add(param_record)
        db.flush()  # 获取新创建记录的ID，便于递归为子参数设置 parent_param_id

        # 如果是 object 且存在 children，或者是 array 且元素类型为 object 且存在 children，则递归创建子参数
        if (param_type_enum == ParamType.OBJECT and param_children) or (
            param_type_enum == ParamType.ARRAY
            and param_array_child_type_enum == ParamType.OBJECT
            and param_children
        ):
            _process_params_recursively(
                db=db,
                params=param_children,
                api_draft_id=api_draft_id,
                parent_param_id=param_record.id,  # type: ignore
                parent_location=param_location,
                param_model_class=param_model_class,
            )


# 通过service_iteration_id、api_draft_id更新API
def apiUpdateApiByApiDraftId(
    db: Session,
    service_iteration_id: int,
    api_draft_id: int,
    user_id: int,
    name: str,
    method: str,
    path: str,
    description: str,
    level: str,
    req_params: list,
    resp_params: list,
) -> dict:
    # 版本迭代行为权限校验
    check_res = checkServiceIterationPermission(
        db=db, service_iteration_id=service_iteration_id, user_id=user_id
    )
    if not check_res["is_ok"]:
        return check_res["error"]
    api_draft = db.get(ApiDraft, api_draft_id)
    if not api_draft:
        return {
            "status": -1,
            "message": "Api draft not found",
        }
    if api_draft.service_iteration_id != service_iteration_id:  # type: ignore
        return {
            "status": -2,
            "message": "Api draft not belongs to this service iteration",
        }
    # 符合更新条件
    try:
        api_method = HttpMethod(method)
    except ValueError:
        api_method = HttpMethod.GET
    try:
        api_level = ApiLevel(level)
    except ValueError:
        api_level = ApiLevel.P2
    api_draft.name = name  # type: ignore
    api_draft.method = api_method  # type: ignore
    api_draft.path = path  # type: ignore
    api_draft.description = description  # type: ignore
    api_draft.level = api_level  # type: ignore
    # 更新请求参数和响应参数
    # 先删除已存在的请求参数和响应参数，再新增
    db.query(RequestParamDraft).filter(
        RequestParamDraft.api_draft_id == api_draft_id
    ).delete()
    db.query(ResponseParamDraft).filter(
        ResponseParamDraft.api_draft_id == api_draft_id
    ).delete()

    # 处理请求参数（支持嵌套结构）
    if req_params:
        _process_params_recursively(
            db=db,
            params=req_params,
            api_draft_id=api_draft_id,
            param_model_class=RequestParamDraft,
        )

    # 处理响应参数（支持嵌套结构）
    if resp_params:
        _process_params_recursively(
            db=db,
            params=resp_params,
            api_draft_id=api_draft_id,
            param_model_class=ResponseParamDraft,
        )

    db.commit()
    return {
        "status": 200,
        "message": "Update api success",
    }
