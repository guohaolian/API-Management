from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

database_uri = os.getenv("DATABASE_URI")
if not database_uri:
    raise RuntimeError(
        "DATABASE_URI 未配置：请在 BE-CAM 目录创建 .env 并设置 DATABASE_URI（例如 postgresql+psycopg2://user:pass@localhost:5432/dbname）。"
    )

engine = create_engine(
    url=database_uri,
    echo=False,  # 关闭SQL语句输出
    pool_size=20,  # 默认连接池大小
    max_overflow=30,  # 最大溢出连接数
    pool_timeout=60,  # 连接超时时间
    pool_recycle=3600,  # 连接回收时间，防止连接被数据库关闭
    pool_pre_ping=True,  # 每次借出连接前 ping 一下，防止取到断开的连接
)
session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
