from robyn import Robyn, ALLOW_CORS
from robyn.openapi import OpenAPI, OpenAPIInfo, Contact, Components
from robyn.robyn import Response
from subRouters.v1.user import userRouterV1
from subRouters.v1.service import serviceRouterV1
from subRouters.v1.api import apiRouterV1
from subRouters.v1.mock import mockRouterV1

import os
from dotenv import load_dotenv

load_dotenv()
PORT = int(os.getenv("PORT") or 1024)


app = Robyn(
    __file__,
    openapi=OpenAPI(
        info=OpenAPIInfo(
            title="NEXUS Backend API",
            description="NEXUS API Management Platform 后端接口文档。",
            version="0.1.0",
            contact=Contact(name="NEXUS Team"),
            components=Components(
                securitySchemes={
                    "BearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT",
                        "description": "登录后获取的 access token，请求头格式: Authorization: Bearer <token>",
                    }
                }
            ),
        ),
    ),
)
app.openapi.openapi_spec["security"] = [{"BearerAuth": []}]

app.include_router(userRouterV1)
app.include_router(serviceRouterV1)
app.include_router(apiRouterV1)
app.include_router(mockRouterV1)

# 生产环境需要注释：使用nginx解决跨域
#ALLOW_CORS(app, origins=["http://localhost:9000", "http://127.0.0.1:9000"])


@app.exception
def handle_exception(error):
    return Response(status_code=500, headers={}, description=f"error msg: {error}")


@app.get("/", openapi_tags=["Health"])
async def index():
    """健康检查"""
    return "OK"


if __name__ == "__main__":
    app.start(host="0.0.0.0", port=PORT)
