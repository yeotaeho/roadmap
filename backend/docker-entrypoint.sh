#!/bin/sh
# 컨테이너 부팅 — 마이그레이션 적용(선택) 후 전달된 명령을 실행한다.
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "[entrypoint] alembic upgrade head"
  alembic upgrade head
fi

exec "$@"
