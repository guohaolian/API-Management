"""V1 API 路由集合。

本模块把 HTTP 请求路由到 `services.api` 中实现的业务函数，负责：
- 参数解析与简单校验（必填参数、类型转换）
- 从请求中提取用户身份（通过 access token）
- 在数据库会话上下文中调用 service 层方法并直接返回其结果

路由遵循前缀 `/v1/api`，并启用基于 `AuthHandler` 的鉴权中间件。
注意：这里的路由处理函数返回的对象通常是 `services.api` 的返回字典或 Robyn `Response`。
"""

import json
from robyn import SubRouter
from robyn.robyn import Request, Response
from robyn.authentication import BearerGetter

from authentication import AuthHandler
from database.database import session
from services.user import userGetUserIdByAccessToken
from services.api import *  # type: ignore
from utils import string2Bool


apiRouterV1 = SubRouter(__file__, prefix="/v1/api")


# 全局异常处理：将未捕获的异常转换为 500 返回，便于统一日志记录与前端提示
@apiRouterV1.exception
def handle_exception(error):
    return Response(status_code=500, description=f"error msg: {error}", headers={})


# 鉴权中间件：使用自定义的 AuthHandler，从 Authorization: Bearer <token> 中解析用户
apiRouterV1.configure_authentication(AuthHandler(token_getter=BearerGetter()))


# 通过 service_id 获取全部 category 列表（仅返回分类元信息，不包含 API）
@apiRouterV1.get("/getAllCategoriesByServiceId", auth_required=True)
def getAllCategoriesByServiceId(request: Request):
    service_id = request.query_params.get("service_id", None)
    if not service_id:
        return Response(
            status_code=400, headers={}, description="service_id is required"
        )
    user_id = userGetUserIdByAccessToken(request)
    with session() as db:
        res = apiGetAllCategoriesByServiceId(
            db=db, service_id=int(service_id), user_id=user_id
        )
    return res


# 通过 service_id + category_id 获取该分类下的 API 列表（默认最新版本）
@apiRouterV1.get("/getAllApisByServiceId", auth_required=True)
def getAllApisByServiceId(request: Request):
    service_id = request.query_params.get("service_id", None)
    category_id = request.query_params.get("category_id", None)
    if not service_id or not category_id:
        return Response(
            status_code=400,
            headers={},
            description="service_id and category_id are required",
        )
    user_id = userGetUserIdByAccessToken(request)
    with session() as db:
        res = apiGetAllApisByServiceId(
            db=db,
            service_id=int(service_id),
            category_id=int(category_id),
            user_id=user_id,
        )
    return res


# 通过 api_id 获取 API 详情，可选查询最新/草稿版本（is_latest=true/false）
@apiRouterV1.get("/getApiById", auth_required=True)
def getApiById(request: Request):
    api_id = request.query_params.get("api_id", None)
    if not api_id:
        return Response(status_code=400, headers={}, description="api_id is required")
    is_latest = request.query_params.get("is_latest", "true")
    user_id = userGetUserIdByAccessToken(request)
    with session() as db:
        res = apiGetApiById(
            db=db,
            api_id=int(api_id),
            user_id=user_id,
            is_latest=string2Bool(is_latest),
        )
    return res


# 新增 category：需要在请求 body 中提供 service_id、category_name、description
@apiRouterV1.post("/addCategoryByServiceId", auth_required=True)
def addCategoryByServiceId(request: Request):
    data = request.json()
    service_id = data["service_id"]
    category_name = data["category_name"]
    description = data["description"]
    user_id = userGetUserIdByAccessToken(request)
    with session() as db:
        res = apiAddCategoryByServiceId(
            db=db,
            service_id=int(service_id),
            user_id=user_id,
            category_name=category_name,
            description=description,
        )
    return res


# 删除 category：传入 category_id（权限在 service 层检查）
@apiRouterV1.post("/deleteCategoryById", auth_required=True)
def deleteCategoryById(request: Request):
    data = request.json()
    category_id = data["category_id"]
    service_iteration_id = data.get("service_iteration_id")
    user_id = userGetUserIdByAccessToken(request)
    with session() as db:
        res = apiDeleteCategoryById(
            db=db,
            category_id=category_id,
            user_id=user_id,
            service_iteration_id=int(service_iteration_id)
            if service_iteration_id is not None
            else None,
        )
    return res


# 更新 category：传入 category_id、category_name、description
@apiRouterV1.post("/updateCategoryById", auth_required=True)
def updateCategoryById(request: Request):
    data = request.json()
    category_id = data["category_id"]
    category_name = data["category_name"]
    description = data["description"]
    user_id = userGetUserIdByAccessToken(request)
    with session() as db:
        res = apiUpdateCategoryById(
            db=db,
            category_id=int(category_id),
            user_id=user_id,
            category_name=category_name,
            description=description,
        )
    return res


# 修改 API 所属分类（只支持已发布的 Api，而非草稿）
@apiRouterV1.post("/updateApiCategoryById", auth_required=True)
def updateApiCategoryById(request: Request):
    data = request.json()
    api_id = data["api_id"]
    category_id = data["category_id"]
    user_id = userGetUserIdByAccessToken(request)
    with session() as db:
        res = apiUpdateApiCategory(
            db=db, api_id=int(api_id), category_id=int(category_id), user_id=user_id
        )
    return res


# ---- ⚠️ 以下为 service 迭代（ServiceIteration）相关路由 ----
# 通过service_iteration_id新增api（存ApiDraft表，可指定category_id）
@apiRouterV1.post("/addApi", auth_required=True)
def addApi(request: Request):
    data = request.json()
    service_iteration_id = data["service_iteration_id"]
    name = data["name"]
    method = data["method"]
    path = data["path"]
    description = data["description"]
    level = data["level"]
    category_id = data.get("category_id", None)
    user_id = userGetUserIdByAccessToken(request)
    with session() as db:
        res = apiAddApi(
            db=db,
            service_iteration_id=int(service_iteration_id),
            user_id=user_id,
            name=name,
            method=method,
            path=path,
            description=description,
            level=level,
            category_id=int(category_id) if category_id else None,
        )
    return res


# 复制 ApiDraft：在同一 iteration 内复制指定草稿为新草稿
@apiRouterV1.post("/copyApiByApiDraftId", auth_required=True)
def copyApiByApiDraftId(request: Request):
    data = request.json()
    service_iteration_id = data["service_iteration_id"]
    api_draft_id = data["api_draft_id"]
    user_id = userGetUserIdByAccessToken(request)
    with session() as db:
        res = apiCopyApiByApiDraftId(
            db=db,
            service_iteration_id=int(service_iteration_id),
            api_draft_id=int(api_draft_id),
            user_id=user_id,
        )
    return res


# 删除 ApiDraft：权限与存在性检查在 service 层处理
@apiRouterV1.post("/deleteApiByApiDraftId", auth_required=True)
def deleteApiByApiDraftId(request: Request):
    data = request.json()
    service_iteration_id = data["service_iteration_id"]
    api_draft_id = data["api_draft_id"]
    user_id = userGetUserIdByAccessToken(request)
    with session() as db:
        res = apiDeleteApiByApiDraftId(
            db=db,
            service_iteration_id=int(service_iteration_id),
            api_draft_id=int(api_draft_id),
            user_id=user_id,
        )
    return res


# 更新 ApiDraft 的元信息与参数（req_params 与 resp_params 为 JSON 字符串，需反序列化）
@apiRouterV1.post("/updateApiByApiDraftId", auth_required=True)
def updateApiByApiDraftId(request: Request):
    data = request.json()
    service_iteration_id = data["service_iteration_id"]
    api_draft_id = data["api_draft_id"]
    name = data["name"]
    method = data["method"]
    path = data["path"]
    description = data["description"]
    level = data["level"]
    req_params = json.loads(data["req_params"])
    resp_params = json.loads(data["resp_params"])

    user_id = userGetUserIdByAccessToken(request)
    with session() as db:
        res = apiUpdateApiByApiDraftId(
            db=db,
            service_iteration_id=int(service_iteration_id),
            api_draft_id=int(api_draft_id),
            user_id=user_id,
            name=name,
            method=method,
            path=path,
            description=description,
            level=level,
            req_params=req_params,
            resp_params=resp_params,
        )
    return res
