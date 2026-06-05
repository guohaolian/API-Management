"""V1 Mock 路由：在线 Mock 执行与代理。"""

import json

from robyn import SubRouter
from robyn.authentication import BearerGetter
from robyn.robyn import Request, Response

from authentication import AuthHandler
from database.database import session
from services.mock import mockExecuteApi, mockGetDefaultRequest, mockProxyRequest
from services.user import userGetUserIdByAccessToken
from utils import string2Bool


mockRouterV1 = SubRouter(__file__, prefix="/v1/mock")


@mockRouterV1.exception
def handle_exception(error):
    return Response(status_code=500, description=f"error msg: {error}", headers={})


mockRouterV1.configure_authentication(AuthHandler(token_getter=BearerGetter()))


@mockRouterV1.post("/executeMock", auth_required=True)
def executeMock(request: Request):
    data = request.json() or {}
    api_id = data.get("api_id")
    if api_id is None:
        return Response(status_code=400, description="api_id is required", headers={})

    is_latest = data.get("is_latest", True)
    status_code = data.get("status_code")
    request_input = data.get("request")
    user_id = userGetUserIdByAccessToken(request=request)

    with session() as db:
        res = mockExecuteApi(
            db=db,
            api_id=int(api_id),
            user_id=user_id,
            is_latest=string2Bool(is_latest),
            status_code=int(status_code) if status_code is not None else None,
            request_input=request_input,
        )
    return res


@mockRouterV1.get("/getMockDefaults", auth_required=True)
def getMockDefaults(request: Request):
    api_id = request.query_params.get("api_id")
    if not api_id:
        return Response(status_code=400, description="api_id is required", headers={})
    is_latest = request.query_params.get("is_latest", "true")
    user_id = userGetUserIdByAccessToken(request=request)

    with session() as db:
        res = mockGetDefaultRequest(
            db=db,
            api_id=int(api_id),
            user_id=user_id,
            is_latest=string2Bool(is_latest),
        )
    return res


def _handle_mock_proxy(request: Request):
    service_uuid = request.query_params.get("service_uuid")
    mock_path = request.query_params.get("mock_path")
    if not service_uuid or not mock_path:
        return Response(
            status_code=400,
            description="service_uuid and mock_path are required",
            headers={},
        )

    version = request.query_params.get("version")
    service_iteration_id = request.query_params.get("service_iteration_id")
    user_id = userGetUserIdByAccessToken(request=request)

    request_input = None
    if request.body:
        try:
            body = json.loads(request.body)
            if isinstance(body, dict):
                request_input = body.get("request") or body
        except (TypeError, json.JSONDecodeError):
            pass

    with session() as db:
        res = mockProxyRequest(
            db=db,
            service_uuid=service_uuid,
            user_id=user_id,
            method=request.method or "GET",
            mock_path=mock_path,
            version=version,
            service_iteration_id=int(service_iteration_id)
            if service_iteration_id
            else None,
            request_input=request_input,
        )

    if res.get("status") != 200:
        return res

    mock_result = res["mock_result"]
    return Response(
        status_code=mock_result["status_code"],
        description=json.dumps(mock_result["body"], ensure_ascii=False),
        headers={"Content-Type": "application/json"},
    )


@mockRouterV1.get("/proxy", auth_required=True)
def mockProxyGet(request: Request):
    return _handle_mock_proxy(request)


@mockRouterV1.post("/proxy", auth_required=True)
def mockProxyPost(request: Request):
    return _handle_mock_proxy(request)


@mockRouterV1.put("/proxy", auth_required=True)
def mockProxyPut(request: Request):
    return _handle_mock_proxy(request)


@mockRouterV1.delete("/proxy", auth_required=True)
def mockProxyDelete(request: Request):
    return _handle_mock_proxy(request)


@mockRouterV1.patch("/proxy", auth_required=True)
def mockProxyPatch(request: Request):
    return _handle_mock_proxy(request)
