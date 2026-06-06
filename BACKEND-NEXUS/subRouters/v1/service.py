"""V1 Service 路由集合。

该模块将 HTTP 请求映射到 `services.service` 中的业务函数，职责包括：
- 请求参数解析与校验（必填项、类型转换）
- 从请求中提取用户身份（通过 access token）
- 在数据库会话上下文中调用 service 层并返回结果

路由前缀为 `/v1/service`，并启用基于 `AuthHandler` 的鉴权中间件。
注意：此文件只负责路由和最小校验，权限细节委托给 service 层实现。
"""

import json

# Robyn 子路由与请求/响应类型
from robyn import SubRouter
from robyn.robyn import Request, Response
# 用于从 Authorization 头提取 Bearer token
from robyn.authentication import BearerGetter

# 自定义鉴权处理器
from authentication import AuthHandler
# 数据库会话工厂（上下文管理器风格）
from database.database import session
# 从 token 中解析用户 id 的工具函数
from services.user import userGetUserIdByAccessToken
# 导入 service 层的业务函数（本文件作为路由适配层使用）
from services.service import *  # type: ignore
from services.iteration_approval import (
    serviceSubmitIterationForApproval,
    serviceApproveIteration,
    serviceRejectIteration,
    serviceGetPendingIterations,
    serviceGetIterationAuditLog,
    serviceGetIterationChangePreview,
    serviceUpdateServiceApprovalSetting,
)


# 创建子路由实例，前缀为 /v1/service
serviceRouterV1 = SubRouter(__file__, prefix="/v1/service")


# 全局异常处理
@serviceRouterV1.exception
def handle_exception(error):
    # 返回统一的 500 响应，包含异常信息以便日志定位
    return Response(status_code=500, description=f"error msg: {error}", headers={})


# 鉴权中间件
# 配置鉴权中间件，使用 Bearer token 提取器
serviceRouterV1.configure_authentication(AuthHandler(token_getter=BearerGetter()))


# 通过服务id获取服务详情
@serviceRouterV1.get("/getServiceById", auth_required=True)
def getServiceById(request: Request):
    # 从 query params 中读取 id
    id = request.query_params.get("id", None)
    # 简单存在性校验
    if not id:
        return Response(status_code=400, description="id is required", headers={})
    # 从 token 中解析当前用户 id（用于权限检查）
    user_id = userGetUserIdByAccessToken(request=request)
    # 在会话上下文中执行 service 层逻辑，并把结果原样返回
    with session() as db:
        res = serviceGetServiceById(db=db, id=int(id), user_id=user_id)
    return res


# 获取全部服务
@serviceRouterV1.get("/getAllServices", auth_required=True)
def getAllServices(request: Request):
    # 分页参数：默认 page_size=10, current_page=1
    page_size = request.query_params.get("page_size", "10")
    current_page = request.query_params.get("current_page", "1")
    # 解析当前用户 id
    user_id = userGetUserIdByAccessToken(request=request)
    # 在 DB 会话中调用 service 层获取分页结果
    with session() as db:
        res = serviceGetAllServices(
            db=db,
            user_id=user_id,
            page_size=int(page_size) if page_size else 10,
            current_page=int(current_page) if current_page else 1,
        )
    return res


# 通过用户id获取用户的所有最新版本服务（Service表中）的列表
@serviceRouterV1.get("/getHisNewestServicesByOwnerId", auth_required=True)
def getHisNewestServicesByOwnerId(request: Request):
    # 分页参数与标记是否只查询我的服务
    page_size = request.query_params.get("page_size", "10")
    current_page = request.query_params.get("current_page", "1")
    is_my_services = request.query_params.get("is_my_services", "true")
    # 当前请求者 id
    my_id = userGetUserIdByAccessToken(request=request)
    assert is_my_services is not None
    # 根据 is_my_services 决定 owner_id 来源：true 使用当前用户，false 从请求中读取 owner_id
    if json.loads(is_my_services.lower()):
        owner_id = my_id
    else:
        owner_id = request.query_params.get("owner_id", None)
        if not owner_id:
            return Response(
                status_code=400,
                description="owner_id is required when is_my_services is false",
                headers={},
            )
    # 在 DB 会话中调用 service 层获取结果并返回
    with session() as db:
        res = serviceGetHisNewestServicesByOwnerId(
            db=db,
            owner_id=int(owner_id),
            my_id=my_id,
            page_size=int(page_size) if page_size else 10,
            current_page=int(current_page) if current_page else 1,
        )
    return res


# 通过用户id获取用户的所有维护服务（Service表中）的列表
@serviceRouterV1.get("/getHisMaintainedServicesByUserId", auth_required=True)
def getHisMaintainedServicesByUserId(request: Request):
    # 分页参数
    page_size = request.query_params.get("page_size", "10")
    current_page = request.query_params.get("current_page", "1")
    # 当前请求者 id
    my_id = userGetUserIdByAccessToken(request=request)
    # 支持传入 user_id（查询他人维护的服务），默认值为当前用户
    user_id = request.query_params.get("user_id", str(my_id))

    # 调用 service 层，传入 my_id 以便后端进行权限判定
    with session() as db:
        res = serviceGetHisMaintainedServicesByUserId(
            db=db,
            user_id=int(user_id),
            my_id=my_id,
            page_size=int(page_size) if page_size else 10,
            current_page=int(current_page) if current_page else 1,
        )
    return res


# 通过service_uuid和version获取服务详情（根据version判断是否为最新版本）
@serviceRouterV1.get("/getServiceByUuidAndVersion", auth_required=True)
def getServiceByUuidAndVersion(request: Request):
    # 读取 service_uuid 与 version（version 可为 'latest'）
    service_uuid = request.query_params.get("service_uuid", None)
    version = request.query_params.get("version", None)
    # 必填校验
    if not service_uuid or not version:
        return Response(
            status_code=400,
            description="service_uuid and version are required",
            headers={},
        )
    # 当前用户 id
    user_id = userGetUserIdByAccessToken(request=request)
    # 委托 service 层处理版本查找与权限判断
    with session() as db:
        res = serviceGetServiceByUuidAndVersion(
            db=db,
            service_uuid=service_uuid,
            version=version,
            user_id=user_id,
        )
    return res


# 通过service_uuid获取全部版本号
@serviceRouterV1.get("/getAllVersionsByUuid", auth_required=True)
def getAllVersionsByUuid(request: Request):
    # 读取 service_uuid 并做校验
    service_uuid = request.query_params.get("service_uuid", None)
    if not service_uuid:
        return Response(
            status_code=400,
            description="service_uuid is required",
            headers={},
        )
    # 解析当前用户 id
    user_id = userGetUserIdByAccessToken(request=request)
    # 调用 service 层获取版本列表
    with session() as db:
        res = serviceGetAllVersionsByUuid(
            db=db,
            service_uuid=service_uuid,
            user_id=user_id,
        )
    return res


# 创建新服务
@serviceRouterV1.post("/createNewService", auth_required=True)
def createNewService(request: Request):
    # 读取并解析请求体 JSON
    data = request.json()
    # 必填字段：service_uuid, description
    service_uuid = data["service_uuid"]
    description = data["description"]
    # 创建者（owner）由 token 确定
    owner_id = userGetUserIdByAccessToken(request=request)
    # 调用 service 层执行创建逻辑并返回结果
    with session() as db:
        res = serviceCreateNewService(
            db=db,
            service_uuid=service_uuid,
            owner_id=owner_id,
            description=description,
        )
    return res


# 通过user_id获取全部删除的服务
@serviceRouterV1.get("/getAllDeletedServicesByUserId", auth_required=True)
def getAllDeletedServicesByUserId(request: Request):
    # 分页参数与当前用户 id
    page_size = request.query_params.get("page_size", "10")
    current_page = request.query_params.get("current_page", "1")
    user_id = userGetUserIdByAccessToken(request=request)
    # 在 service 层执行查询并返回
    with session() as db:
        res = serviceGetAllDeletedServicesByUserId(
            db=db,
            user_id=user_id,
            page_size=int(page_size) if page_size else 10,
            current_page=int(current_page) if current_page else 1,
        )
    return res


# 通过candidate_id和service_id判断是否为服务的维护者
@serviceRouterV1.get("/isServiceMaintainer", auth_required=True)
def isServiceMaintainer(request: Request):
    # 读取查询参数：service_id 与 candidate_id
    service_id = request.query_params.get("service_id", None)
    candidate_id = request.query_params.get("candidate_id", None)
    # 必填校验
    if not service_id or not candidate_id:
        return Response(
            status_code=400,
            description="service_id and candidate_id are required",
            headers={},
        )
    # 解析当前用户 id（用于权限判定）
    user_id = userGetUserIdByAccessToken(request=request)
    # 调用 service 层判断并返回结果
    with session() as db:
        res = serviceIsMaintainer(
            db=db,
            service_id=int(service_id),
            user_id=user_id,
            candidate_id=int(candidate_id),
        )
    return res


# 通过服务id添加或移除maintainer
@serviceRouterV1.post("/addOrRemoveServiceMaintainerById", auth_required=True)
def addOrRemoveServiceMaintainerById(request: Request):
    # 读取请求体并提取参数
    data = request.json()
    service_id = data["service_id"]
    candidate_id = data["candidate_id"]
    # 当前操作用户 id
    user_id = userGetUserIdByAccessToken(request=request)
    # 调用 service 层执行添加/移除 maintainer 的操作
    with session() as db:
        res = serviceAddOrRemoveServiceMaintainerById(
            db=db,
            service_id=int(service_id),
            user_id=user_id,
            candidate_id=int(candidate_id),
        )
    return res


# 通过服务id删除服务（最新版本），历史版本不动
@serviceRouterV1.post("/deleteServiceById", auth_required=True)
def deleteServiceById(request: Request):
    # 软删除 service（只标记最新版本为删除）
    data = request.json()
    id = data["id"]
    # 执行操作的用户 id
    user_id = userGetUserIdByAccessToken(request=request)
    with session() as db:
        res = serviceDeleteServiceById(db=db, id=id, user_id=user_id)
    return res


# 通过服务id还原服务（还原最新版本），历史版本不动
@serviceRouterV1.post("/restoreServiceById", auth_required=True)
def restoreServiceById(request: Request):
    # 恢复被软删除的 service
    data = request.json()
    id = data["id"]
    user_id = userGetUserIdByAccessToken(request=request)
    with session() as db:
        res = serviceRestoreServiceById(db=db, id=id, user_id=user_id)
    return res


# 通过service_iteration_id删除服务历史版本
@serviceRouterV1.post("/deleteIterationById", auth_required=True)
def deleteIterationById(request: Request):
    # 删除指定的 ServiceIteration（历史版本）
    data = request.json()
    service_iteration_id = data["service_iteration_id"]
    user_id = userGetUserIdByAccessToken(request=request)
    with session() as db:
        res = serviceDeleteIterationById(
            db=db,
            service_iteration_id=service_iteration_id,
            user_id=user_id,
        )
    return res


# ---- ⚠️ 以下为service迭代流程相关路由 ----
@serviceRouterV1.get("/getIterationById", auth_required=True)
def getIterationById(request: Request):
    # 读取迭代 id 并校验
    id = request.query_params.get("id", None)
    if not id:
        return Response(
            status_code=400,
            description="id is required",
            headers={},
        )
    # 解析当前用户 id
    user_id = userGetUserIdByAccessToken(request=request)
    # 委托 service 层返回迭代详情
    with session() as db:
        res = serviceGetServiceIterationById(
            db=db,
            id=int(id),
            user_id=user_id,
        )
    return res


# 发起service迭代流程
@serviceRouterV1.post("/startIteration", auth_required=True)
def startIteration(request: Request):
    # 发起新的迭代：把当前 service 快照为草稿
    data = request.json()
    service_id = data["service_id"]
    user_id = userGetUserIdByAccessToken(request=request)
    with session() as db:
        res = serviceStartIteration(db=db, service_id=service_id, user_id=user_id)
    return res


# 完成service迭代流程，service版本更新
@serviceRouterV1.post("/commitIteration", auth_required=True)
async def commitIteration(request: Request):
    # 提交迭代并发布新版本（会触发数据库的大量写入）
    data = request.json()
    service_iteration_id = data["service_iteration_id"]
    new_version = data["new_version"]
    user_id = userGetUserIdByAccessToken(request=request)
    with session() as db:
        res = await serviceCommitIteration(
            db=db,
            service_iteration_id=service_iteration_id,
            new_version=new_version,
            user_id=user_id,
        )
    return res


# 通过 service_iteration_id 修改 service description
@serviceRouterV1.post("/updateDescription", auth_required=True)
def updateDescription(request: Request):
    # 更新迭代描述，仅影响该迭代对象
    data = request.json()
    service_iteration_id = data["service_iteration_id"]
    description = data["description"]
    user_id = userGetUserIdByAccessToken(request=request)
    with session() as db:
        res = serviceUpdateDescription(
            db=db,
            service_iteration_id=service_iteration_id,
            description=description,
            user_id=user_id,
        )
    return res


# 对比两个版本的 Service/API/参数树差异
@serviceRouterV1.get("/compareVersionsByUuid", auth_required=True)
def compareVersionsByUuid(request: Request):
    service_uuid = request.query_params.get("service_uuid", None)
    base_version = request.query_params.get("base_version", None)
    compare_version = request.query_params.get("compare_version", None)
    if not service_uuid or not base_version or not compare_version:
        return Response(
            status_code=400,
            description="service_uuid, base_version and compare_version are required",
            headers={},
        )
    user_id = userGetUserIdByAccessToken(request=request)
    with session() as db:
        res = serviceCompareVersionsByUuid(
            db=db,
            service_uuid=service_uuid,
            base_version=base_version,
            compare_version=compare_version,
            user_id=user_id,
        )
    return res


# 导出openapi
@serviceRouterV1.get("/exportOpenapiByUuidAndVersion", auth_required=True)
def exportOpenapiByUuidAndVersion(request: Request):
    # 导出 OpenAPI：需提供 service_uuid 与 version（可为 latest）
    service_uuid = request.query_params.get("service_uuid", None)
    version = request.query_params.get("version", None)
    if not service_uuid or not version:
        return Response(
            status_code=400,
            description="service_uuid and version are required",
            headers={},
        )
    user_id = userGetUserIdByAccessToken(request=request)
    with session() as db:
        res = serviceExportOpenapiByUuidAndVersion(
            db=db,
            service_uuid=service_uuid,
            version=version,
            user_id=user_id,
        )
    return res


# 导入 OpenAPI（创建一个新的迭代，并将 OpenAPI 写入草稿）
@serviceRouterV1.post("/importOpenapiToNewIteration", auth_required=True)
def importOpenapiToNewIteration(request: Request):
    # 从 OpenAPI 对象创建新的 ServiceIteration（并把 API 写入草稿）
    data = request.json()
    service_id = data.get("service_id")
    openapi_object = data.get("openapi_object")
    # 必填校验
    if service_id is None or openapi_object is None:
        return Response(
            status_code=400,
            description="service_id and openapi_object are required",
            headers={},
        )
    user_id = userGetUserIdByAccessToken(request=request)
    with session() as db:
        res = serviceImportOpenapiToNewIteration(
            db=db,
            service_id=int(service_id),
            openapi_object=openapi_object,
            user_id=user_id,
        )
    return res


# ---- 迭代审批与变更审计 ----
@serviceRouterV1.post("/submitIterationForApproval", auth_required=True)
async def submitIterationForApproval(request: Request):
    data = request.json()
    service_iteration_id = data.get("service_iteration_id")
    new_version = data.get("new_version")
    if service_iteration_id is None or not new_version:
        return Response(
            status_code=400,
            description="service_iteration_id and new_version are required",
            headers={},
        )
    user_id = userGetUserIdByAccessToken(request=request)
    with session() as db:
        res = await serviceSubmitIterationForApproval(
            db=db,
            service_iteration_id=int(service_iteration_id),
            new_version=new_version,
            user_id=user_id,
        )
    return res


@serviceRouterV1.post("/approveIteration", auth_required=True)
async def approveIteration(request: Request):
    data = request.json()
    service_iteration_id = data.get("service_iteration_id")
    if service_iteration_id is None:
        return Response(
            status_code=400,
            description="service_iteration_id is required",
            headers={},
        )
    review_comment = data.get("review_comment", "")
    user_id = userGetUserIdByAccessToken(request=request)
    with session() as db:
        res = await serviceApproveIteration(
            db=db,
            service_iteration_id=int(service_iteration_id),
            user_id=user_id,
            review_comment=review_comment or "",
        )
    return res


@serviceRouterV1.post("/rejectIteration", auth_required=True)
async def rejectIteration(request: Request):
    data = request.json()
    service_iteration_id = data.get("service_iteration_id")
    review_comment = data.get("review_comment")
    if service_iteration_id is None or not review_comment:
        return Response(
            status_code=400,
            description="service_iteration_id and review_comment are required",
            headers={},
        )
    user_id = userGetUserIdByAccessToken(request=request)
    with session() as db:
        res = await serviceRejectIteration(
            db=db,
            service_iteration_id=int(service_iteration_id),
            user_id=user_id,
            review_comment=review_comment,
        )
    return res


@serviceRouterV1.get("/getPendingIterations", auth_required=True)
def getPendingIterations(request: Request):
    page_size = request.query_params.get("page_size", "20")
    current_page = request.query_params.get("current_page", "1")
    user_id = userGetUserIdByAccessToken(request=request)
    with session() as db:
        res = serviceGetPendingIterations(
            db=db,
            user_id=user_id,
            page_size=int(page_size) if page_size else 20,
            current_page=int(current_page) if current_page else 1,
        )
    return res


@serviceRouterV1.get("/getIterationAuditLog", auth_required=True)
def getIterationAuditLog(request: Request):
    service_iteration_id = request.query_params.get("service_iteration_id", None)
    if not service_iteration_id:
        return Response(
            status_code=400,
            description="service_iteration_id is required",
            headers={},
        )
    page_size = request.query_params.get("page_size", "50")
    current_page = request.query_params.get("current_page", "1")
    user_id = userGetUserIdByAccessToken(request=request)
    with session() as db:
        res = serviceGetIterationAuditLog(
            db=db,
            service_iteration_id=int(service_iteration_id),
            user_id=user_id,
            page_size=int(page_size) if page_size else 50,
            current_page=int(current_page) if current_page else 1,
        )
    return res


@serviceRouterV1.get("/getIterationChangePreview", auth_required=True)
def getIterationChangePreview(request: Request):
    service_iteration_id = request.query_params.get("service_iteration_id", None)
    if not service_iteration_id:
        return Response(
            status_code=400,
            description="service_iteration_id is required",
            headers={},
        )
    user_id = userGetUserIdByAccessToken(request=request)
    with session() as db:
        res = serviceGetIterationChangePreview(
            db=db,
            service_iteration_id=int(service_iteration_id),
            user_id=user_id,
        )
    return res


@serviceRouterV1.post("/updateServiceApprovalSetting", auth_required=True)
def updateServiceApprovalSetting(request: Request):
    data = request.json()
    service_id = data.get("service_id")
    if service_id is None or "requires_iteration_approval" not in data:
        return Response(
            status_code=400,
            description="service_id and requires_iteration_approval are required",
            headers={},
        )
    user_id = userGetUserIdByAccessToken(request=request)
    with session() as db:
        res = serviceUpdateServiceApprovalSetting(
            db=db,
            service_id=int(service_id),
            requires_iteration_approval=bool(data["requires_iteration_approval"]),
            user_id=user_id,
        )
    return res


# 导入 OpenAPI 到当前迭代（覆写当前迭代草稿）
@serviceRouterV1.post("/importOpenapiToIteration", auth_required=True)
def importOpenapiToIteration(request: Request):
    # 将 OpenAPI 导入到指定的 ServiceIteration（覆盖该迭代草稿）
    data = request.json()
    service_iteration_id = data.get("service_iteration_id")
    openapi_object = data.get("openapi_object")
    if service_iteration_id is None or openapi_object is None:
        return Response(
            status_code=400,
            description="service_iteration_id and openapi_object are required",
            headers={},
        )
    user_id = userGetUserIdByAccessToken(request=request)
    with session() as db:
        res = serviceImportOpenapiToIteration(
            db=db,
            service_iteration_id=int(service_iteration_id),
            openapi_object=openapi_object,
            user_id=user_id,
        )
    return res
