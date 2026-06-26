# MSIT/MFDS 연도 해석(미명시→현재 연도) 무네트워크 회귀 테스트 — 연말 0건 사망 방지

from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.master.hub.services.bronze_economic_ingest_service import (  # noqa: E402
    MFDS_PRESS_BOARD,
    PRESS_BOARD,
    _mfds_with_year,
    _resolve_board,
)

PASS = 0
FAIL = 0


def check(name: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}")


def test_msit_none_resolves_current_year() -> None:
    cur = datetime.now().year
    board = _resolve_board(PRESS_BOARD, None)
    check("MSIT None→현재 연도", board.target_year == cur)


def test_msit_explicit_year_overrides() -> None:
    board = _resolve_board(PRESS_BOARD, 2030)
    check("MSIT 명시 연도 override", board.target_year == 2030)


def test_msit_not_hardcoded_2026() -> None:
    # 현재 연도가 2026이 아닌 한, None 해석은 2026을 반환하면 안 된다(시한폭탄 회귀 방지).
    cur = datetime.now().year
    board = _resolve_board(PRESS_BOARD, None)
    check("MSIT None 은 2026 고정이 아님", board.target_year == cur and (cur != 2026 or board.target_year == 2026))


def test_mfds_year_override() -> None:
    cur = datetime.now().year
    check("MFDS 현재 연도 해석", _mfds_with_year(MFDS_PRESS_BOARD, cur).target_year == cur)
    check("MFDS 명시 연도 override", _mfds_with_year(MFDS_PRESS_BOARD, 2030).target_year == 2030)


def main() -> int:
    test_msit_none_resolves_current_year()
    test_msit_explicit_year_overrides()
    test_msit_not_hardcoded_2026()
    test_mfds_year_override()
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
