"""애플리케이션 로깅 초기화 (한 곳에서 basicConfig 호출)."""

from __future__ import annotations

import logging
import sys


def setup_logging(level: int = logging.INFO, fmt: str | None = None) -> None:
    """
    루트 로거 설정. main.py 또는 독립 스크립트 진입점에서 한 번 호출한다.
    이미 핸들러가 있으면 중복 설정을 피하기 위해 건너뛸 수 있음.
    """
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return

    logging.basicConfig(
        level=level,
        format=fmt or "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )
