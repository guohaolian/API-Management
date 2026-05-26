# BACKEND-NEXUS（后端）

本目录是 NEXUS 的后端服务（Python + Robyn + PostgreSQL）。项目整体说明见仓库根目录的 [README.md](../README.md)。

## 快速开始（本机开发）

**依赖**：Python（见 [pyproject.toml](pyproject.toml) 的 `requires-python`）、`uv`、PostgreSQL。

1) 安装依赖（首次运行）：

```bash
cd BACKEND-NEXUS
uv sync
```

2) 准备环境变量：复制 [.env.example](.env.example) 为 `.env` 并按实际填写。

3) 初始化数据库（首次搭建）：

- 先在 PostgreSQL 中创建用户/数据库（示例以 `.env.example` 默认值为准，用户/库名都是 `cam`）：

```sql
CREATE USER cam WITH PASSWORD 'YOUR_PASSWORD';
CREATE DATABASE cam OWNER cam;
GRANT ALL PRIVILEGES ON DATABASE cam TO cam;
```

- 然后在 `.env` 里填写 `DATABASE_*` / `DATABASE_URI`

- 创建表结构（首次建表建议用 `create_all`）：

```bash
cd BACKEND-NEXUS
uv run python -m database.init_db
```

4) 启动开发环境（热重载）：

```bash
cd BACKEND-NEXUS
./run-dev.ps1
```

后端默认监听 `http://127.0.0.1:1024`（根路径 `/` 返回 `OK`）。

## 环境变量（`.env`）

环境变量文件不纳入 git，请从 [.env.example](.env.example) 复制后修改。字段如下：

```ini
# App
PYTHONPATH=<YOUR-PROJECT-PATH>
PORT=1024

# Auth
ALGORITHM=HS256
LOGIN_SECRET=<YOUR-LOGIN-SECRET>

# Database (PostgreSQL)
DATABASE_ENGINE=postgresql+psycopg2
DATABASE_USERNAME=<YOUR-DATABASE-USERNAME>
DATABASE_PASSWORD=<YOUR-DATABASE-PASSWORD>
DATABASE_HOST=<YOUR-DATABASE-HOST>
DATABASE_PORT=<YOUR-DATABASE-PORT>
DATABASE_NAME=<YOUR-DATABASE-NAME>
DATABASE_URI=postgresql+psycopg2://<YOUR-DATABASE-USERNAME>:<YOUR-DATABASE-PASSWORD>@<YOUR-DATABASE-HOST>:<YOUR-DATABASE-PORT>/<YOUR-DATABASE-NAME>

# Mail (optional; used when committing iteration)
MAIL_SERVER=smtp.example.com
MAIL_PORT=465
MAIL_USERNAME=your_email@example.com
MAIL_PASSWORD=your_smtp_password
MAIL_DEFAULT_SENDER=your_email@example.com
```

## 数据库迁移（模型变更时）

仓库提供了迁移脚本：

- Windows PowerShell：[database/db-migrate.ps1](database/db-migrate.ps1)
- macOS/Linux：[database/db-migrate.sh](database/db-migrate.sh)

脚本内部会执行 `uv run alembic revision --autogenerate` 与 `uv run alembic upgrade head`。

> 注意：本仓库当前未包含 `alembic.ini` / 迁移目录等初始化产物；若你本地尚未配置好 Alembic，需要先完成 Alembic 初始化与配置后再运行迁移脚本。

## 后端逻辑摘要

-   后端技术选型采用 `Python Robyn` 框架，数据库采用 `PostgreSQL`
-   安装依赖使用 `uv sync`；开发热重载可使用 `uv run robyn -m app --dev` 或脚本 `run-dev.ps1/run-dev.sh`
-   项目默认监听 `1024` 端口，可通过修改 `.env` 中的环境变量 `PORT` 修改

以下内容为项目内部逻辑与数据结构说明。

## 数据库表设计

-   使用 `SQLAlchemy` 进行数据库 `ORM` 映射，全部数据库相关放到 `database` 目录中，包含：

    -   `models.py`：数据库表 `ORM` 类
    -   `enums.py`：枚举类，即自定义类型，例如 `ApiLevel`、`UserLevel` 等
    -   `database.py`：数据库连接与配置，定义 `session` 工厂
    -   `db-migrate.sh`：【见下条】

-   数据库首次建表建议使用 [database/init_db.py](database/init_db.py) 的 `create_all`：

    ```bash
    uv run python -m database.init_db
    ```

-   `database/models.py` 中数据库表修改后可使用迁移脚本（前提：你本地已配置好 Alembic）：

    -   macOS/Linux：`bash database/db-migrate.sh`
    -   Windows PowerShell：`./database/db-migrate.ps1`（或 `.\\database\\db-migrate.ps1`）

-   为方便每个表的记录的 `json` 化，让所有表继承自 `SerializableMixin` 基类，包含序列化 `toJson()` 方法，可选择保留属性、排除属性以及是否包含关系表字段；为避免循环引用，`toJson()` 实现时内部 `toJson()` 方法不得设定 `include_relations=True`。

-   `service-maintainer` 为多对多关系，通过中间表 `user_service_link` 关联

-   `ApiLevel` 枚举类从 `P0` 到 `P4` 重要性递减

-   `UserLevel` 枚举类从 `L0` 到 `L4` 权限递减。暂时只考虑 `L0` 和 `L4` 两类用户：`L0` 为超级管理员，有权限访问全部 `API`；`L4` 为普通用户，只可访问自己的 `service`、`api` 等资源。未确定中间类别的用户权限

## 服务与 API 实现

-   将全部服务分为 `user`、`service`、`api` 三类，分别对应三个子路由

-   每个路由实现内部逻辑都交由 `service` 层处理。路由层仅负责接收请求参数、调用 `service` 层方法、返回响应。`service` 层再调用对应的 `model` 层方法进行数据库的 `CRUD`

-   本项目中 `service` 层的方法规范：

    -   方法命名为 `<service_name><operation_name>`，例如 `userLogin()`、`serviceGetAllCategoriesByServiceId()` 等。避免和路由及路由函数函数重名
    -   传入 `SQLAlchemy Session` 实例，命名为 `db`，以及其他所需参数；
    -   请求成功 `200` 时，返回区分 `get` 操作与其他操作，均返回对象，对象值为：
        -   `get` 操作：单个对象或对象列表
        -   其他操作：成功 `message` 与其他必要数据
    -   请求失败 `4xx` 或 `5xx` 时，返回 `Robyn Response` 对象：

        ```python
        return Response(
            status_code=<Fail status code>,
            headers={},
            description="<Fail message>",
        )
        ```

-   **鉴权**

    -   通过 `Robyn` 内置的 `AuthenticationHandler` 实现，具体逻辑在 `authentication.py` 中
    -   登录生成 `access token` 并在后续请求 `Header` 中 `Authorization` 字段携带，格式为 `Bearer <access_token>`
    -   接口鉴权通过 `Robyn` 内置的 `BearerGetter()` 方法获取 `access token` 并进行验证；另外，在 `user` 相关 `service` 中另实现了 `userGetUserIdByAccessToken()` 方法，可传入 `Robyn Request` 或 `access token` 解析出 `user_id`。但注意：二者只能二选一传入
    -   在 `authentication.py` 中定义 `API_PERMISSION_MAP`，用于存储每个 `API` 允许访问的**最低** `UserLevel` 的映射。若 `API` 不在该 `map` 中，默认允许所有用户访问
    -   每个子路由中添加鉴权中间件

        ```python
        <subRouter>.configure_authentication(AuthHandler(token_getter=BearerGetter()))
        ```

        在每个路由中设定 `auth_required=True` 开启鉴权，即只有登录用户有权限访问

-   错误处理：对于一个 API，若缺少必要参数或参数格式错误，返回 `400 Bad Request` 错误；而其他逻辑错误（例如密码错误），则响应正常返回 `200` ，附带 `status` 为负， `message` 为错误描述。

### service 相关

-   每个 `service` 有一个 `owner`，多个 `maintainer`，但计划 `MVP` 版本不引入 `maintainer`。因此除了 `L0` 用户外，只有 `owner` 才能操作其 `service`

-   每个 `service` 中包含一个唯一的 `service_uuid`，用于标识该 `service`。

    -   `service_uuid` 命名格式为 `a/b/c`，`a`、`b`、`c` 均为小写字母或数字，三者均由用户自定义
    -   `version` 命名格式为 `X.Y.Z`，其中 `X`、`Y`、`Z` 均为非负整数。所有服务初始版本均为 `0.0.1`

    **二者在前端做正则校验**

-   `api` 的 `category` 切换只支持在 `service` 最新版本中进行，不属于 `service` 迭代周期内的行为

### ⚠️ Service 版本管理

-   一次 `service` 迭代周期内包含以下几种行为：

    -   修改 `service description`
    -   新增 `API`
    -   删除 `API`
    -   编辑 `API`（包含 `API` 自有属性、请求参数以及响应参数）

-   `Service` 表存储每个 `service` 的最新版本，而 `ServiceIteration` 表存储每个 `service` 迭代周期内的所有变更。`Service` 表中的 `version` 与 `ServiceIteration` 表中当前 `service` 的最新 `version` 对齐

-   ![service 关系图](assets/service-relation-diagram.png)

-   `ServiceIteration` 被标记 `is_committed=False` 时，代表正在当前 `service` 的迭代周期，每个 `service` 每个用户只能有一个迭代周期在进行中；`ServiceIteration` 被标记 `is_committed=True` 时，代表该迭代周期已完成，作为当前 `service` 的历史版本记录

#### service 版本迭代流程

1. 用户发起 `service` 迭代流程 `/startIteration`，创建一个新迭代周期 `ServiceIteration` 记录，标记 `is_committed=False`，并将当前服务最新版本全部信息备份到 `ServiceIteration`，返回一个 `service_iteration_id`，存在客户端，作为本迭代周期的唯一标识

2. 用户在本迭代周期内进行上述四种行为，每次行为均在 `ServiceIteration` 中进行记录。每个行为发生需要通过 `service_iteration_id` 标识当前迭代周期：

    - 修改 `service description`：将修改后的 `description` 存储到 `ServiceIteration`
    - 新增 `API`：新增一条 `ApiDraft` 记录，只记录新增的 `API` 自有信息（`name`、`method`、`path`、`description`、`level`、`category_id`（可选））
    - 删除 `API`：通过 `api_draft_id` 删除 `ApiDraft` 记录，同时利用 `CASCADE` 删除其关联的请求参数和响应参数
    - 编辑 `API`：【⚠️ 复杂】通过 `api_draft_id` 定位到 `ApiDraft` 记录，更新其自有属性（`name`、`method`、`path`、`description`、`level`、`category_id`（可选））。之后，删除其关联的全部请求参数和响应参数，并根据传入的请求参数和响应参数，更新其关联的请求参数和响应参数。

        > 传入 `req_params` 格式约定：
        >
        > ```json
        > [
        >     {
        >         "name": "user",
        >         "location": "body",
        >         "type": "object",
        >         "required": true,
        >         "default_value": null,
        >         "description": "用户信息",
        >         "example": "{}",
        >         "array_child_type": null,
        >         "children": [
        >             {
        >                 "name": "name",
        >                 "type": "string",
        >                 "required": true,
        >                 "default_value": null,
        >                 "description": "用户姓名",
        >                 "example": "张三",
        >                 "array_child_type": null,
        >                 "children": null
        >             },
        >             {
        >                 "name": "profile",
        >                 "type": "object",
        >                 "required": false,
        >                 "default_value": null,
        >                 "description": "用户档案",
        >                 "example": "{}",
        >                 "array_child_type": null,
        >                 "children": [
        >                     {
        >                         "name": "age",
        >                         "type": "int",
        >                         "required": true,
        >                         "default_value": null,
        >                         "description": "年龄",
        >                         "example": "25",
        >                         "array_child_type": null,
        >                         "children": null
        >                     }
        >                 ]
        >             }
        >         ]
        >     },
        >     {
        >         "name": "tags",
        >         "location": "query",
        >         "type": "array",
        >         "required": false,
        >         "default_value": null,
        >         "description": "标签列表",
        >         "example": "[\"tag1\", \"tag2\"]",
        >         "array_child_type": "string",
        >         "children": null
        >     }
        > ]
        > ```
        >
        > `resp_params` 类似，只是 `location` 换为 `status_code`

3. 用户在本迭代周期内完成所有行为后，发起提交 `/commitIteration`，将 `ServiceIteration` 其全部信息拷贝进 `Service` 表中（即全部关联的 `ApiDraft`，及其中记录的全部请求参数和响应参数），同步到数据库中的 `Api`、`RequestParam` 和 `ResponseParam` 表中。之后更新当前 `service` 的 `version`，并将 `ServiceIteration` 标记 `is_committed=True`。保留 `ServiceIteration` 记录，作为历史版本记录
