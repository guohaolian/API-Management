"""数据库连接与会话工厂。

此模块负责：
- 从环境变量读取 `DATABASE_URI`（通常放在项目根目录的 `.env` 文件中）
- 创建 SQLAlchemy `Engine` 并配置连接池参数
- 暴露一个 `session`（`sessionmaker` 实例）供应用其它模块创建数据库会话

使用示例：
from database.database import session
db: Session = session()
try:
    # 使用 db 执行数据库操作
    pass
finally:
    db.close()

注意：在生产环境中请把数据库连接相关敏感信息放到安全的配置/密钥管理中，而不是代码仓库。
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# 加载位于项目根目录（或运行目录）的 .env 文件，将其中的环境变量注入到 os.environ
load_dotenv()

# 从环境中读取 DATABASE_URI，示例格式：
# postgresql+psycopg2://user:password@host:port/dbname
database_uri = os.getenv("DATABASE_URI")
if not database_uri:
    raise RuntimeError(
        "DATABASE_URI 未配置：请在 BACKEND-NEXUS 目录创建 .env 并设置 DATABASE_URI（例如 postgresql+psycopg2://user:pass@localhost:5432/dbname）。"
    )

# 创建 SQLAlchemy 引擎（Engine）并配置连接池。常用参数说明：
# - echo: 是否打印执行的 SQL（调试时可置 True）
# - pool_size: 连接池的大小（常驻连接数）
# - max_overflow: 超过 pool_size 后可额外创建的连接数
# - pool_timeout: 从池中获取连接时的超时时间（秒），超时会抛出异常
# - pool_recycle: 连接回收时间（秒），在长时间连接后重置以避免被数据库服务器关闭
# - pool_pre_ping: 在取出连接前先发起轻量查询（ping）以检测连接是否仍然可用
engine = create_engine(
    url=database_uri,
    echo=False,
    pool_size=20,
    max_overflow=30,
    pool_timeout=60,
    pool_recycle=3600,
    pool_pre_ping=True,
)

# 创建一个 sessionmaker 工厂。通过调用 `session()` 可以获得一个新的 Session 实例，
# 推荐在使用后调用 `close()` 或使用上下文管理器来确保连接释放回池中。
session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
