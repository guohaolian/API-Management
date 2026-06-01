"""API 服务层方法集合（业务逻辑），与数据库模型交互。

本模块提供一组面向业务的函数，用于：
- 查询/管理 API 分类（`ApiCategory`）
- 查询/管理 API 及其草稿（`Api` / `ApiDraft`）
- 处理请求/响应参数的创建、复制和序列化

约定：所有函数第一个参数均为 SQLAlchemy 的 `Session` 实例（`db`），并返回包含
`status` 与 `message` 的字典（必要时包含额外数据字段，例如 `apis` / `api` / `category`）。
"""

import time

# SQLAlchemy 的部分导入：
from sqlalchemy import or_  # 用于构造 OR 条件查询
from sqlalchemy.orm import Session  # 类型注解：表示 DB 会话

# 从 ORM 模型中导入需要的实体类（在本模块中用于 CRUD 操作）
from database.models import (
    Service,
    Api,
    ApiCategory,
    User,
    ApiDraft,
    RequestParamDraft,
    ResponseParamDraft,
)

# 导入枚举类型以保证接口层使用受控值（而不是任意字符串）
from database.enums import ApiLevel, HttpMethod, ParamType, ParamLocation

# 辅助函数：权限校验与参数组织器（将 ORM 参数集合转换为前端友好结构）
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
    # 从会话中根据主键读取 Service（返回实体或 None）
    service = db.get(Service, service_id)
    # 若不存在对应的 service，立即返回错误，避免后续空引用
    if not service:
        return {
            "status": -1,
            "message": "Service not found",
        }

    # 读取用户实体用于权限判断（可能为 None）
    user = db.get(User, user_id)
    # 若 user 为 None，则后续访问 user.level 会抛异常；此处假定调用者在外层保证用户存在。
    # 判定逻辑：若不是 owner 且不是 L0（管理员），则禁止访问
    if service.owner_id != user_id and user.level.value != 0:  # type: ignore
        return {
            "status": -2,
            "message": "You are not the owner of this service",
        }
    # 查询并按主键顺序返回分类列表
    # 构造并执行查询：
    # 1) db.query(ApiCategory) -> Query 对象
    # 2) .filter(...) 添加 where 子句，筛选出当前 service 下的分类
    # 3) .order_by(ApiCategory.id) 按 id 升序（确定稳定的顺序）
    # 4) .all() 执行查询并返回实体列表
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
    # 读取 Service（与上文相同流程）
    service = db.get(Service, service_id)
    if not service:
        return {
            "status": -1,
            "message": "Service not found",
        }
    # 权限检查（获取 User 并检查 level/owner 状态）
    user = db.get(User, user_id)
    if service.owner_id != user_id and user.level.value != 0:  # type: ignore
        return {
            "status": -2,
            "message": "You are not the owner of this service",
        }
    # 查询不包含软删除的 API（`is_deleted` 字段为 False）
    # 基础查询：筛选当前 service 且未被软删除的 API
    query = db.query(Api).filter(Api.service_id == service_id, ~Api.is_deleted)
    if category_id is not None:
        # 如果提供了 category_id，则只返回该分类下的 API
        query = query.filter(Api.category_id == category_id)
    # 按 id 倒序（最新的先返回），并执行查询获取结果列表
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
    # 选择从正式表或草稿表中读取 API 实体
    api = db.get(Api, api_id) if is_latest else db.get(ApiDraft, api_id)
    if not api:
        return {
            "status": -1,
            "message": "Api not found",
        }
    # 非L0用户只能查看自己的服务
    # 读取调用者 user 实体（用于下面更细粒度的权限判断）
    user = db.get(User, user_id)
    if not user:
        return {
            "status": -2,
            "message": "User not found",
        }
    # 非 L0 用户需满足更严格的权限：
    # - 在 `is_latest` 场景（查看正式发布的 Api）时，需为 service 的 owner 或 maintainer；
    # - 在 草稿（history）场景时，允许 iteration 的 creator 查看，同时 owner/maintainer 也有权限。
    # 当非管理员（L0）时，执行更细粒度权限判定
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
    # 把 ORM 的关联集合转换成前端需要的分组结构，调用封装好的工具函数
    request_params_by_location = organizeReqParams(api.request_params)
    response_params_by_status_code = organizeRespParams(api.response_params)

    # 使用模型的 toJson 方法序列化实体，排除大体量或冗余的关系字段，
    # 以便把参数数据以更友好的结构放到顶层返回给前端。
    # 序列化 api 为字典：
    # - include_relations=True 表示允许 toJson 在需要时读取关联字段，
    # - exclude 用来排除不想直接嵌入的关系（我们会把参数以不同结构注入返回值）。
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
    # 读取 service 实体用于权限检查（同上）
    service = db.get(Service, service_id)
    if not service:
        return {
            "status": -1,
            "message": "Service not found",
        }
    # 权限检查：只有 owner 或 maintainer（或 L0）可新增分类
    # 权限检查：读取 user 并判断是否为 owner/maintainer 或管理员
    user = db.get(User, user_id)
    if service.owner_id != user_id and user not in service.maintainers and user.level.value != 0:  # type: ignore
        return {
            "status": -2,
            "message": "You are neither the owner nor the maintainer of this service",
        }
    # 检查 category 名称在该服务下是否已存在，保持同一服务中分类名唯一
    # 检查是否存在同名分类：若 .first() 返回非 None，说明存在冲突
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
        # 构造 ApiCategory 实体但尚未写入 DB；属性映射直接对应数据库字段
        service_id=service_id, name=category_name, description=description
    )
    db.add(category)
    # 将新增实体加入会话并提交，使其持久化到数据库；提交后 category.id 会被分配
    db.commit()
    return {
        "status": 200,
        "message": "Add category success",
        "category": category.toJson(),
    }


# 通过category_id删除category
def apiDeleteCategoryById(
    db: Session,
    category_id: int,
    user_id: int,
    service_iteration_id: int | None = None,
) -> dict:
    """删除指定的 `ApiCategory`。

    权限：非 L0 用户需为服务 owner 或 maintainer；迭代模式下额外校验迭代权限。
    非迭代模式：仅允许删除空分类（无关联 Api）。
    迭代模式：同时删除该迭代下该分类的所有 ApiDraft 及其参数，并解除正式 Api 对该分类的引用。
    """
    category = db.get(ApiCategory, category_id)
    if not category:
        return {
            "status": -1,
            "message": "Category not found",
        }

    if service_iteration_id is not None:
        check_res = checkServiceIterationPermission(
            db=db, service_iteration_id=service_iteration_id, user_id=user_id
        )
        if not check_res["is_ok"]:
            return check_res["error"]
        service_iteration = check_res["service_iteration"]
        if category.service_id != service_iteration.service_id:  # type: ignore
            return {
                "status": -4,
                "message": "Category not belongs to this service iteration",
            }

        api_draft_ids = [
            row[0]
            for row in db.query(ApiDraft.id)
            .filter(
                ApiDraft.service_iteration_id == service_iteration_id,
                ApiDraft.category_id == category_id,
            )
            .all()
        ]
        if api_draft_ids:
            db.query(RequestParamDraft).filter(
                RequestParamDraft.api_draft_id.in_(api_draft_ids)
            ).delete(synchronize_session=False)
            db.query(ResponseParamDraft).filter(
                ResponseParamDraft.api_draft_id.in_(api_draft_ids)
            ).delete(synchronize_session=False)
            db.query(ApiDraft).filter(ApiDraft.id.in_(api_draft_ids)).delete(
                synchronize_session=False
            )

        db.query(Api).filter(Api.category_id == category_id).update(
            {Api.category_id: None}, synchronize_session=False
        )
    else:
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
        if db.query(Api).filter(Api.category_id == category_id).first():
            return {
                "status": -4,
                "message": "Category has apis, cannot delete",
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
    # 权限检查与参数校验：
    # - user 必须存在；
    # - 非 L0 用户只能由 owner 更新（这里采用更严格策略，只有 owner 可改名/描述）。
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
    # 权限检查：仅允许 owner/maintainer（或 L0）修改正式 API 的分类
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
    # checkServiceIterationPermission 返回结构说明：{
    #   "is_ok": bool,
    #   "error": {"status":..., "message":...} 或 None,
    #   "service_iteration": ServiceIteration 实体（当 is_ok 为 True 时）
    # }
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
        # 直接用枚举类构造：如果 method 是合法成员则返回对应枚举，否则抛 ValueError
        api_method = HttpMethod(method)
    except ValueError:
        # 回退到 GET，避免外部错误导致接口抛异常/事务失败
        api_method = HttpMethod.GET
    try:
        api_level = ApiLevel(level)
    except ValueError:
        # 回退到默认级别 P2
        api_level = ApiLevel.P2
    # 说明：上面转换会在传入非法字符串时回退到默认值，避免抛出异常导致事务回退。
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
    # 构造 ApiDraft 实体（尚未持久化），字段逐一映射来自调用参数或经过转换的枚举
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
    # 提交以持久化草稿到数据库（commit 后可在返回中安全使用 .toJson()）
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
            # 逐字段映射：从 source param 的 ORM 对象直接读取属性并构造新的 RequestParamDraft
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
            # ResponseParamDraft 需要额外的 status_code 字段，其他字段同样逐一复制
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
        # flush 而非 commit：
        # - flush 会把新增记录写入当前会话并分配主键（id），但不会提交事务；
        # - 这样可以在同一事务内继续创建子记录并使用新记录的 id 建立外键关系，最后统一 commit。
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
    # - int(time.time()) 返回当前秒级时间戳
    # - 通过字符串插值把原 name/path 拼接后缀，尽量保证新 name/path 唯一
    timestamp = int(time.time())
    new_name = f"{api_draft.name}-copy-{timestamp}"
    new_path = f"{api_draft.path}-copy-{timestamp}"

    # 构造新草稿实体，保留原草稿的重要字段（method/level/description），
    # 但替换 name/path 以防止冲突
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
    # flush 以获取 new_api_draft.id（在随后的参数复制中需要引用）
    db.flush()

    # 复制请求参数
    # 查找根级请求参数（parent_param_id 为 None 的为根参数）
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
    # 查找根级响应参数
    root_resp_params = [p for p in api_draft.response_params if p.parent_param_id is None]
    if root_resp_params:
        _copy_params_recursively(
            db=db,
            source_params=root_resp_params,
            target_api_draft_id=new_api_draft.id,
            parent_param_id=None,
            param_model_class=ResponseParamDraft,
        )

    # 提交事务：在所有关联参数复制完成后一次性提交，保证操作的原子性
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
    # 使用批量删除提高效率：
    # - delete(synchronize_session=False) 会直接在数据库执行 DELETE，而不会尝试更新 SQLAlchemy 会话缓存，
    #   这在我们不再使用被删除对象的情况下是安全且更高效的做法。
    db.query(RequestParamDraft).filter(
        RequestParamDraft.api_draft_id == api_draft_id
    ).delete(synchronize_session=False)
    db.query(ResponseParamDraft).filter(
        ResponseParamDraft.api_draft_id == api_draft_id
    ).delete(synchronize_session=False)

    # 删除草稿实体本身（此处对 api_draft 实例调用 delete，会在 commit 时发出 DELETE）
    db.delete(api_draft)

    # 提交事务以使所有删除生效（如果任一删除失败，将回滚，避免不一致）
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
        # 基本字段解析：从传入 dict 中提取必要字段，遵循示例 JSON 的约定
        # - name/type 为必填；其他字段允许缺省并由后续逻辑赋默认值
        param_name = param["name"]
        param_type = param["type"]
        param_required = param.get("required", False)
        param_default_value = param.get("default_value")
        param_description = param.get("description")
        param_example = param.get("example")
        param_array_child_type = param.get("array_child_type")
        param_children = param.get("children")

        # 确定参数位置（location）：子参数会继承父参数的位置
        # - parent_location 存在时表示当前正在处理的参数是子参数，应继承该值；
        # - 否则从 param dict 读取，缺省为 'body'（常用于复杂对象）
        if parent_location:
            param_location = parent_location
        else:
            param_location = param.get("location", "body")

        # 将位置字符串转换为枚举，非法值回退为 ParamLocation.BODY
        try:
            param_location_enum = ParamLocation(param_location)
        except ValueError:
            # 回退保证不会因为外部传入非法字符串而抛出异常
            param_location_enum = ParamLocation.BODY

        # 将类型字符串转换为枚举，非法值回退为字符串类型
        try:
            param_type_enum = ParamType(param_type)
        except ValueError:
            param_type_enum = ParamType.STRING

        # 处理数组元素类型（如果参数为 array，则 array_child_type 指定元素类型）
        # - 如果无法解析为 ParamType，则设为 None，表示未知/任意元素类型
        param_array_child_type_enum = None
        if param_array_child_type:
            try:
                param_array_child_type_enum = ParamType(param_array_child_type)
            except ValueError:
                param_array_child_type_enum = None

        # 创建参数记录（区分请求与响应模型）并持久化到会话：
        if param_model_class is RequestParamDraft:
            # RequestParamDraft 字段映射说明：
            # - api_draft_id: 关联的 ApiDraft 主键
            # - name/location/type/required/...: 直接来自传入的 param 字段或其枚举化结果
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
            # 响应参数额外包含 status_code，若未指定则默认 200
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

        # 把新记录加入当前会话（未提交）；随后调用 flush 以便获得数据库分配的主键 id
        db.add(param_record)
        db.flush()  # flush 只同步到 DB 层但不提交事务，便于使用 param_record.id

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
