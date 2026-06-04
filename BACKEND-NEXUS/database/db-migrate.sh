#!/usr/bin/env bash
set -eu

cd "$(dirname "$0")/.."

GENERATE=false
MESSAGE="db migrate"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --generate|-g)
      GENERATE=true
      shift
      if [ "$#" -gt 0 ] && [ "${1#--}" = "$1" ]; then
        MESSAGE="$1"
        shift
      fi
      ;;
    *)
      shift
      ;;
  esac
done

echo "Database Migration Start..."

if [ "$GENERATE" = true ]; then
  echo "Generating revision: $MESSAGE"
  uv run alembic revision --autogenerate -m "$MESSAGE"
fi

uv run alembic upgrade head
echo "Database Migration Success"