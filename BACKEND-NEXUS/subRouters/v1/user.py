"""V1 用户路由。

逐路由负责参数解析、最小校验、从 token 提取用户身份，并在 DB 会话中调用 services.user 层函数。
注：实际权限与业务逻辑由 `services.user` 实现，这里只做路由适配。
"""

# 从服务层导入需要的函数
from services.user import userGetUserByUsernameOrNicknameOrEmail, userModifyPassword

# Robyn 子路由与请求/响应类型
from robyn import SubRouter
from robyn.robyn import Request, Response
from robyn.authentication import BearerGetter

# 自定义鉴权处理器
from authentication import AuthHandler
# 数据库会话工厂
from database.database import session
# 服务层用户相关函数
from services.user import (
    userGetUserIdByAccessToken,
    userLogin,
    userRegister,
    userGetUserById,
)


# 创建子路由实例，前缀为 /v1/user
userRouterV1 = SubRouter(__file__, prefix="/v1/user")


# 全局异常处理：把未捕获异常转为 500 响应，便于统一错误上报
@userRouterV1.exception
def handle_exception(error):
    # 返回统一格式的 500 响应，包含异常信息用于排查
    return Response(status_code=500, description=f"error msg: {error}", headers={})


# 配置鉴权中间件（使用 Bearer token）
userRouterV1.configure_authentication(AuthHandler(token_getter=BearerGetter()))


# 通过用户id获取用户详情
@userRouterV1.get("/getUserById", auth_required=True)
async def getUserById(request: Request):
    # 从 query params 读取 id
    id = request.query_params.get("id", None)
    # 校验必填项
    if not id:
        return Response(
            status_code=400,
            description="id is required",
            headers={},
        )
    # 在 DB 会话中调用 service 层获取用户信息并返回
    with session() as db:
        res = userGetUserById(db=db, id=int(id))
    return res


# 通过access_token获取用户详情
@userRouterV1.get("/getMyInfo", auth_required=True)
async def getMyInfo(request: Request):
    # 从 token 解析当前用户 id
    user_id = userGetUserIdByAccessToken(request=request)
    # 直接复用 userGetUserById 返回当前用户信息
    with session() as db:
        res = userGetUserById(db=db, id=user_id)
    return res


# 通过用户名或昵称或邮箱获取用户信息
@userRouterV1.get("/getUserByUsernameOrNicknameOrEmail", auth_required=True)
async def getUserByUsernameOrNicknameOrEmail(request: Request):
    # 从 query params 读取搜索关键词（支持 username / nickname / email）
    username_or_nickname_or_email = request.query_params.get(
        "username_or_nickname_or_email", None
    )
    # 必填校验
    if not username_or_nickname_or_email:
        return Response(
            status_code=400,
            description="username_or_nickname_or_email is required",
            headers={},
        )
    # 调用 service 层执行模糊匹配查询并返回结果
    with session() as db:
        res = userGetUserByUsernameOrNicknameOrEmail(
            db=db,
            username_or_nickname_or_email=username_or_nickname_or_email,
        )
    return res


# 用户登录
@userRouterV1.post("/login")
async def login(request: Request):
    # 读取登录表单字段
    data = request.json()
    username = data["username"]
    password = data["password"]
    # 在 service 层进行登录校验并签发 token
    with session() as db:
        res = userLogin(db=db, username=username, password=password)
    return res


# 用户注册
@userRouterV1.post("/register")
async def register(request: Request):
    # 读取注册信息（前端需保证这些字段存在）
    data = request.json()
    username = data["username"]
    password = data["password"]
    nickname = data["nickname"]
    email = data["email"]
    role = data["role"]
    # 调用 service 层完成注册（包含唯一性校验与密码哈希）
    with session() as db:
        res = userRegister(
            db=db,
            username=username,
            password=password,
            nickname=nickname,
            email=email,
            role=role,
        )
    return res


# 修改密码
@userRouterV1.post("/modifyPassword", auth_required=True)
async def modifyPassword(request: Request):
    # 修改密码：需要从 token 中确定用户 id，并从请求体读取旧/新密码
    data = request.json()
    id = userGetUserIdByAccessToken(request=request)
    old_password = data["old_password"]
    new_password = data["new_password"]
    # 委托 service 层执行校验与修改操作
    with session() as db:
        res = userModifyPassword(
            db=db,
            id=id,
            old_password=old_password,
            new_password=new_password,
        )
    return res
