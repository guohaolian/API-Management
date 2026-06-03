#!/usr/bin/env bash
# 在服务器上执行：与 docs/DEPLOY-ALIYUN.md 第 11 节「日常更新」一致，并复制静态资源到 /var/www/nexus。
# 由 GitHub Actions（.github/workflows/deploy.yml）或手动 SSH 触发。

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

# 阿里云部署配置（服务器上从 deploy.env.example 复制一份，勿提交 git）
ALIYUN_ENV="$REPO_ROOT/deploy/aliyun/deploy.env"
if [ -f "$ALIYUN_ENV" ]; then
  # shellcheck disable=SC1090
  set -a
  source "$ALIYUN_ENV"
  set +a
fi

DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
BACKEND_DIR="$REPO_ROOT/BACKEND-NEXUS"
FRONTEND_DIR="$REPO_ROOT/FRONTEND-NEXUS"
FRONTEND_DIST="$FRONTEND_DIR/dist"
NGINX_WEB_ROOT="${NGINX_WEB_ROOT:-/var/www/nexus}"
SYSTEMD_UNIT="${SYSTEMD_UNIT:-nexus-backend}"
# 与 DEPLOY-ALIYUN.md 一致；若未配置则沿用服务器上已有的 FRONTEND-NEXUS/.env.production
VITE_API_BASE_URL="${VITE_API_BASE_URL:-}"

run_systemctl() {
  local action=$1
  local unit=$2
  if [ "$(id -u)" -eq 0 ]; then
    systemctl "$action" "$unit"
  else
    sudo systemctl "$action" "$unit"
  fi
}

run_nginx_test_reload() {
  if ! command -v nginx >/dev/null 2>&1; then
    echo "跳过 Nginx（未安装）"
    return
  fi
  if [ "$(id -u)" -eq 0 ]; then
    nginx -t
    systemctl reload nginx
  else
    sudo nginx -t
    sudo systemctl reload nginx
  fi
}

echo "==> [1/6] 拉取最新代码 (${DEPLOY_BRANCH})"
if [ ! -d "$REPO_ROOT/.git" ]; then
  echo "ERROR: $REPO_ROOT 不是 git 仓库。自动部署需要 git pull，请先在服务器 git clone 或 git init 并添加 remote。"
  exit 1
fi
git fetch origin "$DEPLOY_BRANCH"
git checkout "$DEPLOY_BRANCH"
git pull --ff-only origin "$DEPLOY_BRANCH"

echo "==> [2/6] 后端依赖 (uv sync)"
cd "$BACKEND_DIR"
UV_BIN="${UV_BIN:-}"
if [ -n "$UV_BIN" ] && [ -x "$UV_BIN" ]; then
  "$UV_BIN" sync
elif command -v uv >/dev/null 2>&1; then
  uv sync
elif [ -x /root/.local/bin/uv ]; then
  /root/.local/bin/uv sync
else
  echo "ERROR: 未找到 uv，请设置 UV_BIN 或安装 uv（见 DEPLOY-ALIYUN.md）"
  exit 1
fi

echo "==> [3/6] 前端构建并发布到 ${NGINX_WEB_ROOT}"
cd "$FRONTEND_DIR"
if [ -n "$VITE_API_BASE_URL" ]; then
  cat > .env.production <<EOF
# 由 deploy/aliyun/deploy.env 生成，勿提交 git
VITE_API_BASE_URL=${VITE_API_BASE_URL}
EOF
elif [ ! -f .env.production ]; then
  echo "ERROR: 未设置 VITE_API_BASE_URL，且不存在 FRONTEND-NEXUS/.env.production"
  echo "请在服务器创建 deploy/aliyun/deploy.env（见 deploy/aliyun/deploy.env.example）"
  exit 1
else
  echo "使用已有 .env.production"
fi

if command -v pnpm >/dev/null 2>&1 && [ -f pnpm-lock.yaml ]; then
  pnpm install
  pnpm run build
else
  npm install
  npm run build
fi

if [ ! -d "$FRONTEND_DIST" ]; then
  echo "ERROR: 前端构建失败，未找到 $FRONTEND_DIST"
  exit 1
fi

mkdir -p "$NGINX_WEB_ROOT"
cp -r "$FRONTEND_DIST"/* "$NGINX_WEB_ROOT"/

echo "==> [4/6] 数据库迁移（可选）"
cd "$BACKEND_DIR"
if [ "${RUN_DB_MIGRATE:-false}" = "true" ] && [ -f alembic.ini ]; then
  if [ -n "$UV_BIN" ] && [ -x "$UV_BIN" ]; then
    "$UV_BIN" run alembic upgrade head
  else
    uv run alembic upgrade head
  fi
else
  echo "跳过迁移（RUN_DB_MIGRATE=true 且存在 alembic.ini 时启用）"
fi

echo "==> [5/6] 重启后端: ${SYSTEMD_UNIT}"
run_systemctl restart "$SYSTEMD_UNIT"
run_systemctl --no-pager status "$SYSTEMD_UNIT" || true

echo "==> [6/6] 重载 Nginx"
run_nginx_test_reload

echo "部署完成: $(date -Is)"
echo "访问: ${VITE_API_BASE_URL:-（见 .env.production）}"
