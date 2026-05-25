# API Management

CAM 是一个包含「接口管理 UI + 后端 API + 前端代码生成器」的完整工程：

- 后端维护 Service / API / 参数树与版本迭代；
- 前端提供可视化管理界面；
- CLI 可在任意前端项目中生成 TypeScript 调用代码（可注入 axios/fetch 等 request）。

产品说明（PRD）已整理到 [docs/PRD.md](docs/PRD.md)。

## 目录结构

- [BE-CAM](BE-CAM/)：后端（Python + Robyn）
- [FE-CAM](FE-CAM/)：前端（React + Vite）
- [cam-fe-code-generator](cam-fe-code-generator/)：前端代码生成器（Node CLI，命令 `cam`）

## 快速开始（本机开发）

### 1) 启动后端（BE-CAM）

**依赖**：Python（见 [BE-CAM/pyproject.toml](BE-CAM/pyproject.toml) 里的 `requires-python`）、`uv`、PostgreSQL（以及按需的 Redis）。

1. 安装依赖（首次运行）：

  ```bash
  cd BE-CAM
  uv sync
  ```

2. 准备环境变量（复制 `BE-CAM/.env.example` 为 `BE-CAM/.env`，字段说明见 [BE-CAM/README.md](BE-CAM/README.md)）。
  - 默认端口：`PORT=1024`

3. 初始化数据库（首次搭建）：

   1) 安装并启动 PostgreSQL

   2) 创建数据库用户与库（示例以 `.env.example` 默认值为准：用户/库名都是 `cam`）：

   ```sql
   -- 进入 psql（以超级用户 postgres 为例）
   -- psql -U postgres

   CREATE USER cam WITH PASSWORD 'YOUR_PASSWORD';
   CREATE DATABASE cam OWNER cam;
   GRANT ALL PRIVILEGES ON DATABASE cam TO cam;
   ```

   3) 在 [BE-CAM/.env.example](BE-CAM/.env.example) 的基础上填写 `DATABASE_*` 与 `DATABASE_URI`

   4) 创建表结构（首次建表建议用 `create_all`）：

   ```bash
   cd BE-CAM
   uv run python -m database.init_db
   ```

4. 数据库迁移（模型变更时）：

   目前仓库提供了迁移脚本（见 [BE-CAM/database/db-migrate.ps1](BE-CAM/database/db-migrate.ps1)），用于在你修改 `database/models.py` 后生成/执行迁移。
   若你的本地环境已配置好 Alembic（`alembic.ini` / 迁移目录等），可直接运行：

  ```bash
  cd BE-CAM
  ./database/db-migrate.ps1
  ```

5. 启动开发环境（热重载）：

  ```bash
  cd BE-CAM
  ./run-dev.ps1
  ```

后端默认监听：`http://127.0.0.1:1024`（根路径 `/` 返回 `OK`）。

### 2) 启动前端（FE-CAM）

前端默认端口为 `9000`，并且默认会请求本机后端 `http://127.0.0.1:1024`。

1. 安装依赖：

  ```bash
  cd FE-CAM
  npm install
  # 或 pnpm install
  ```

2. 启动：

  ```bash
  npm run dev
  # 或 pnpm dev
  ```

前端开发环境变量已在 [FE-CAM/.env.development](FE-CAM/.env.development) 中给出：

- `VITE_API_BASE_URL=http://127.0.0.1:1024`
- `VITE_FE_PORT=9000`

> 注意：后端 CORS 白名单默认允许 `http://localhost:9000` 与 `http://127.0.0.1:9000`。

### 3) 使用代码生成器（cam-fe-code-generator）

生成器是一个 CLI：你在哪个目录执行 `cam ...`，就会在那个目录生成/读取 `cam.config.json`，并把代码输出到该配置的 `outDir`。

#### 在本机安装/构建（一次性）

```bash
cd cam-fe-code-generator
npm install
npm run build
```

#### 让 `cam` 命令全局可用（推荐本机用）

在 [cam-fe-code-generator](cam-fe-code-generator/) 目录执行：

```bash
npm link
```

之后你在任意项目目录都可以直接用：`cam -h` / `cam --help`。

#### 方式 2：装到某个项目里（更可复现/不污染全局）

1. 在生成器目录打包：

  ```bash
  cd e:\API-Management\cam-fe-code-generator
  npm run build
  npm pack
  ```

  会生成一个类似 `cam-fe-code-generator-1.7.0.tgz` 的文件。

2. 在另一个前端项目根目录安装该 tgz（建议作为开发依赖）：

  ```bash
  cd <你的前端项目根目录>
  npm i -D <生成的tgz文件路径>
  ```

3. 用 `npx` 调用：

  ```bash
  npx cam init
  npx cam update
  ```

  也可以用 `npx cam -h` / `npx cam --help` 查看全部命令与参数。

#### 在另一个独立前端项目里生成代码

在你的“目标前端项目根目录”执行：

```bash
cam login
cam init
cam add <service_name>:<service_uuid>@latest
cam update
```

生成器会默认输出到 `cam.config.json` 里的 `outDir`（默认 `src/cam-auto-generate`）。

> 注意：`cam update` 会递归删除并重建 `outDir`，请确保该目录仅用于生成产物。

#### 生成器请求地址

当前生成器请求后端的 baseURL 在 [cam-fe-code-generator/src/request/index.ts](cam-fe-code-generator/src/request/index.ts) 中配置；本仓库默认按本机后端 `http://127.0.0.1:1024` 使用。

## 常用脚本

**后端**（Windows PowerShell）：

- 开发：`BE-CAM/run-dev.ps1`
- 生产：`BE-CAM/run-prod.ps1`
- 数据库迁移：`BE-CAM/database/db-migrate.ps1`

**前端**：

- 开发：`cd FE-CAM && pnpm dev`
- 构建：`cd FE-CAM && pnpm build`

**生成器**：

- 构建：`cd cam-fe-code-generator && npm run build`

## 更多文档

- 产品说明（PRD）：[docs/PRD.md](docs/PRD.md)
- 后端说明：见 [BE-CAM/README.md](BE-CAM/README.md)
- 生成器说明：见 [cam-fe-code-generator/README.md](cam-fe-code-generator/README.md)
