"""初始化数据库结构（创建表）。

该脚本调用 SQLAlchemy 的 `Base.metadata.create_all(...)` 来在数据库中创建
在 `database.models` 中定义的所有表结构。通常用于开发或在本地环境初次部署时
快速初始化数据库结构。

注意：
- `create_all` 只会创建不存在的表，不会进行迁移或变更已有表的结构。生产环境
  推荐使用 Alembic 等迁移工具管理架构变更。

使用方式（在项目根目录运行）：
    python -m database.init_db
或者：
    python BACKEND-NEXUS/database/init_db.py
"""

from database.database import engine
from database.models import Base


def main() -> None:
    """在目标数据库中创建所有由 `Base` 定义的表。

    该操作会使用 `engine` 连接到数据库并创建缺失的表。创建完成后打印提示。
    """
    # 根据 Base 的 metadata 在数据库中创建所有未存在的表
    Base.metadata.create_all(bind=engine)
    print("DB tables ensured (create_all).")


if __name__ == "__main__":
    # 以脚本方式运行时执行 main()
    main()
