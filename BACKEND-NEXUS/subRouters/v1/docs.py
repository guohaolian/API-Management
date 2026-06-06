"""只读 API 文档门户路由（/v1/docs）。

默认无需登录；若携带 Bearer Token，则允许 Owner/Maintainer/L0 预览未公开服务。
"""

from robyn import SubRouter
from robyn.robyn import Request, Response

from database.database import session
from services.docs import (
    docsGetServiceByUuidAndVersion,
    docsGetAllVersionsByUuid,
    docsGetApiById,
    docsExportOpenapiByUuidAndVersion,
)
from services.user import userGetUserIdByAccessToken

docsRouterV1 = SubRouter(__file__, prefix="/v1/docs")


def _optional_user_id(request: Request) -> int | None:
    try:
        return userGetUserIdByAccessToken(request=request)
    except Exception:
        return None


@docsRouterV1.exception
def handle_exception(error):
    return Response(status_code=500, description=f"error msg: {error}", headers={})


@docsRouterV1.get("/getServiceByUuidAndVersion")
def getServiceByUuidAndVersion(request: Request):
    service_uuid = request.query_params.get("service_uuid", None)
    version = request.query_params.get("version", None)
    if not service_uuid or not version:
        return Response(
            status_code=400,
            description="service_uuid and version are required",
            headers={},
        )
    user_id = _optional_user_id(request)
    with session() as db:
        res = docsGetServiceByUuidAndVersion(
            db=db,
            service_uuid=service_uuid,
            version=version,
            user_id=user_id,
        )
    return res


@docsRouterV1.get("/getAllVersionsByUuid")
def getAllVersionsByUuid(request: Request):
    service_uuid = request.query_params.get("service_uuid", None)
    if not service_uuid:
        return Response(status_code=400, description="service_uuid is required", headers={})
    user_id = _optional_user_id(request)
    with session() as db:
        res = docsGetAllVersionsByUuid(db=db, service_uuid=service_uuid, user_id=user_id)
    return res


@docsRouterV1.get("/getApiById")
def getApiById(request: Request):
    api_id = request.query_params.get("api_id", None)
    is_latest = request.query_params.get("is_latest", "true")
    if not api_id:
        return Response(status_code=400, description="api_id is required", headers={})
    user_id = _optional_user_id(request)
    with session() as db:
        res = docsGetApiById(
            db=db,
            api_id=int(api_id),
            is_latest=is_latest.lower() != "false",
            user_id=user_id,
        )
    return res


@docsRouterV1.get("/exportOpenapiByUuidAndVersion")
def exportOpenapiByUuidAndVersion(request: Request):
    service_uuid = request.query_params.get("service_uuid", None)
    version = request.query_params.get("version", None)
    if not service_uuid or not version:
        return Response(
            status_code=400,
            description="service_uuid and version are required",
            headers={},
        )
    user_id = _optional_user_id(request)
    with session() as db:
        res = docsExportOpenapiByUuidAndVersion(
            db=db,
            service_uuid=service_uuid,
            version=version,
            user_id=user_id,
        )
    return res
