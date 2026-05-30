"""用户相关的业务逻辑。

包含 token 生成与解析、通过 token 获取用户身份、用户查询、登录、注册、修改密码等操作。
该模块默认依赖 `.env` 中的 `ALGORITHM` 和 `LOGIN_SECRET`，用于签发和验证 JWT。
"""

from urllib.parse import unquote

from robyn.robyn import Request
from sqlalchemy import or_
from sqlalchemy.orm import Session
from jose import jwt
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

from database.models import User
from database.enums import UserRole

# 读取环境变量配置，供 JWT 签发/校验使用
load_dotenv()
ALGORITHM = os.getenv("ALGORITHM")
SECRET_KEY = os.getenv("LOGIN_SECRET")


# 生成access token
def createAccessToken(
    data: dict, expires_delta: timedelta | None = timedelta(hours=24)
) -> str:
    # 复制输入数据，避免直接修改调用方传入的字典对象
    to_encode = data.copy()
    # 生成过期时间：默认 24 小时后失效
    expire = datetime.now(timezone.utc) + expires_delta
    # JWT payload 中写入 exp 字段
    to_encode.update({"exp": expire})
    # 缺少签名算法或密钥时直接报错，避免签发出不可校验的 token
    if not ALGORITHM or not SECRET_KEY:
        raise Exception("ALGORITHM or SECRET_KEY is not set in .env file")
    # 使用 jose.jwt 对 payload 进行签名编码
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# 解析access token
def decodeAccessToken(token: str) -> dict:
    # 解码同样依赖环境中的算法与密钥；缺失时直接失败
    if not ALGORITHM or not SECRET_KEY:
        raise Exception("ALGORITHM or SECRET_KEY is not set in .env file")
    # 返回 token payload；过期、签名错误等异常由 jwt.decode 抛出
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# 通过access token获取user id
def userGetUserIdByAccessToken(
    request: Request | None = None, token: str | None = None
) -> int:
    # request 和 token 只能二选一，避免出现两种来源同时提供导致歧义
    if request is not None and token is not None:
        raise Exception("Request and token should not be provided at the same time")
    if request is not None:
        # 从 Authorization 头中提取 Bearer token
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            raise Exception("Invalid Authorization header format")
        token = authorization.split("Bearer ")[1]
    elif token is None:
        raise Exception("Either request or token is required")
    # 解码 token 并返回 payload 中约定的用户 id
    payload = decodeAccessToken(token)
    return payload["id"]


# 通过user id获取user信息
def userGetUserById(db: Session, id: int) -> dict:
    # 通过主键直接读取 User
    user = db.get(User, id)
    if user is None:
        return {
            "status": -1,
            "message": "User not found",
        }
    return {
        "status": 200,
        "message": "Get user success",
        "user": user.toJson(),
    }


# 通过用户名或昵称或邮箱获取用户信息
def userGetUserByUsernameOrNicknameOrEmail(
    db: Session, username_or_nickname_or_email: str
) -> dict:
    # 把 url 编码的字符串解码，否则是 %20 等格式
    keyword = unquote(username_or_nickname_or_email).strip()
    # 使用 ilike 做模糊匹配，同时支持用户名、昵称和邮箱三种检索入口
    search_users = (
        db.query(User)
        .filter(
            or_(
                User.username.ilike(f"%{keyword}%"),
                User.nickname.ilike(f"%{keyword}%"),
                User.email.ilike(f"%{keyword}%"),
            )
        )
        .order_by(User.nickname, User.username, User.email)
        .all()
    )
    return {
        "status": 200,
        "message": "Get users success",
        "users": [user.toJson() for user in search_users] if search_users else [],
    }


# 用户登录
def userLogin(db: Session, username: str, password: str) -> dict:
    # 用户名和邮箱都作为登录入口，先查到唯一用户记录
    user = (
        db.query(User)
        .filter(or_(User.username == username, User.email == username))
        .first()
    )
    if user is None:
        return {
            "status": -1,
            "message": "User not found",
        }
    if not user.checkPassword(password):
        return {
            "status": -2,
            "message": "Wrong password",
        }
    # 登录成功后签发 access token，token 中只放最小身份信息
    access_token = createAccessToken(data={"id": user.id, "username": user.username})
    return {
        "status": 200,
        "message": "Login success",
        "access_token": access_token,
    }


# 用户注册
def userRegister(
    db: Session, username: str, password: str, nickname: str, email: str, role: str
) -> dict:
    # 注册前先检查用户名或邮箱是否已存在
    existing_user = (
        db.query(User)
        .filter(or_(User.username == username, User.email == email))
        .first()
    )
    if existing_user:
        return {
            "status": -1,
            "message": "Username or email already registered",
        }
    # role 参数来自外部输入，先尝试映射到枚举；失败则回退为 GUEST
    try:
        user_role = UserRole(role)
    except ValueError:
        user_role = UserRole.GUEST
    # 密码只保存哈希值，不保存明文
    user = User(
        username=username,
        password=User.hashPassword(password),
        nickname=nickname,
        email=email,
        role=user_role,
    )
    # 写入数据库并刷新对象，确保后续可以拿到数据库生成的字段
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "status": 200,
        "message": "Register success",
    }


# 修改密码
def userModifyPassword(
    db: Session, id: int, old_password: str, new_password: str
) -> dict:
    # 先按 id 定位用户
    user = db.get(User, id)
    if user is None:
        return {
            "status": -1,
            "message": "User not found",
        }
    # 旧密码校验失败则拒绝修改
    if not user.checkPassword(old_password):
        return {
            "status": -2,
            "message": "Wrong old password",
        }
    # 避免无意义修改：新旧密码相同则直接返回
    if old_password == new_password:
        return {
            "status": -3,
            "message": "New password cannot be the same as old password",
        }
    # 只更新哈希后的密码字段
    user.password = User.hashPassword(new_password)  # type: ignore
    db.commit()
    return {
        "status": 200,
        "message": "Modify password success",
    }
