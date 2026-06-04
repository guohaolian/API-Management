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

# 与 [2/6]、[4/6] 共用：deploy.env 可设 UV_BIN；否则 PATH 或 /root/.local/bin/uv
resolve_uv() {
  if [ -n "${UV_BIN:-}" ] && [ -x "$UV_BIN" ]; then
    echo "$UV_BIN"
    return 0
  fi
  if command -v uv >/dev/null 2>&1; then
    command -v uv
    return 0
  fi
  if [ -x /root/.local/bin/uv ]; then
    echo /root/.local/bin/uv
    return 0
  fi
  return 1
}

# pull 前丢弃会阻塞合并的本地噪音（服务器跑过后端/前端常改到这些文件）
discard_deploy_git_noise() {
  local line file
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    file=$(echo "$line" | awk '{print $NF}')
    case "$file" in
      *__pycache__*|*.pyc|FRONTEND-NEXUS/package-lock.json)
        if git checkout -- "$file" 2>/dev/null; then
          echo "  已还原本地改动: $file"
        fi
        ;;
    esac
  done < <(git status --porcelain 2>/dev/null || true)
}

echo "==> [1/6] 拉取最新代码 (${DEPLOY_BRANCH})"
if [ ! -d "$REPO_ROOT/.git" ]; then
  echo "ERROR: $REPO_ROOT 不是 git 仓库。自动部署需要 git pull，请先在服务器 git clone 或 git init 并添加 remote。"
  exit 1
fi
git fetch origin "$DEPLOY_BRANCH"
git checkout "$DEPLOY_BRANCH"
if [ "${DEPLOY_FORCE_RESET:-}" = "true" ]; then
  echo "WARN: DEPLOY_FORCE_RESET=true — 丢弃仓库内所有未提交改动与未跟踪文件（deploy.env 等在 .gitignore 中，会保留）"
  git clean -fd
  git reset --hard "origin/${DEPLOY_BRANCH}"
else
  discard_deploy_git_noise
  if ! git pull --ff-only origin "$DEPLOY_BRANCH"; then
    echo "ERROR: git pull 失败。若曾在服务器上 scp/手动覆盖代码，请 SSH 登录后执行："
    echo "  cd $REPO_ROOT"
    echo "  DEPLOY_FORCE_RESET=true bash deploy/scripts/deploy.sh"
    echo "或见 docs/DEPLOY-SERVER-GIT.md"
    exit 1
  fi
fi

echo "==> [2/6] 后端依赖 (uv sync)"
cd "$BACKEND_DIR"
UV_CMD="$(resolve_uv)" || {
  echo "ERROR: 未找到 uv，请在 deploy/aliyun/deploy.env 设置 UV_BIN=/root/.local/bin/uv（见 DEPLOY-ALIYUN.md）"
  exit 1
}
echo "使用 uv: $UV_CMD"
"$UV_CMD" sync

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
  UV_CMD="$(resolve_uv)" || {
    echo "ERROR: 未找到 uv，无法执行 alembic。请在 deploy.env 设置 UV_BIN=/root/.local/bin/uv"
    exit 1
  }
  echo "使用 uv: $UV_CMD"
  "$UV_CMD" run alembic upgrade head
else
  echo "跳过迁移（需 RUN_DB_MIGRATE=true 且存在 alembic.ini）"
fi

echo "==> [5/6] 重启后端: ${SYSTEMD_UNIT}"
run_systemctl restart "$SYSTEMD_UNIT"
run_systemctl --no-pager status "$SYSTEMD_UNIT" || true

echo "==> [6/6] 重载 Nginx"
run_nginx_test_reload

echo "部署完成: $(date -Is)"
echo "访问: ${VITE_API_BASE_URL:-（见 .env.production）}"
