"""MSIT 연결 + BBS 컬렉터 스모크 테스트.

실행 (backend 디렉터리에서):
  python scripts/msit_connectivity_test.py

검증 항목:
  1) 목록 URL GET (TLS/연결)
  2) `fn_detail` ID 추출 (JS 하이드레이션 목록)
  3) `MsitBbsCollector` 1페이지 수집 (필터 적용 후 DTO 건수)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from domain.master.hub.services.collectors.economic._msit_common import (  # noqa: E402
    BASE_URL,
    extract_fn_detail_ntt_ids,
    get_html,
    make_session,
    parse_bbs_list_rows,
)
from domain.master.hub.services.collectors.economic.msit_bbs_collector import (  # noqa: E402
    BIZ_BOARD,
    PRESS_BOARD,
    MsitBbsCollector,
)


def main() -> None:
    urls = [
        ("press_307", f"{BASE_URL}/bbs/list.do?sCode=user&mPid=208&mId=307&pageIndex=1"),
        ("biz_311", f"{BASE_URL}/bbs/list.do?sCode=user&mPid=121&mId=311&pageIndex=1"),
        (
            "publicinfo_63",
            f"{BASE_URL}/publicinfo/detailList.do?sCode=user&mId=63&mPid=62"
            "&formMode=L&pageIndex=1&publictSeqNo=295&searchSeCd=&searchMapngCd="
            "&searchOpt=ALL&searchTxt=%EC%98%88%EC%82%B0",
        ),
    ]

    for name, url in urls:
        print("===", name, "===")
        print("URL:", url[:120] + ("..." if len(url) > 120 else ""))
        t0 = time.perf_counter()
        try:
            s = make_session()
            html = get_html(s, url, timeout=25)
            dt_ms = int((time.perf_counter() - t0) * 1000)
            print("OK  len(html)=", len(html), "  latency_ms=", dt_ms)
            rows = parse_bbs_list_rows(html)
            ntt = extract_fn_detail_ntt_ids(html)
            print("parse_bbs_list_rows (legacy table)=", len(rows))
            print("extract_fn_detail_ntt_ids (div board)=", len(ntt), "sample:", ntt[:5])
            s.close()
        except Exception as e:
            print("FAIL", type(e).__name__, ":", e)
        print()

    print("=== collector 1 page (fetch_body=False) ===")
    for board in (PRESS_BOARD, BIZ_BOARD):
        c = MsitBbsCollector(board)
        dtos, stats = c.collect_sync(max_pages=1, max_items=10, fetch_body=False)
        print(board.board_key, "stats=", stats, "dtos=", len(dtos))
        for d in dtos[:3]:
            print(" ", d.raw_title[:72], "|", d.published_at)


if __name__ == "__main__":
    main()
