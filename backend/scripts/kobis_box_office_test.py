# KOBIS 일별 박스오피스 파서(parse_daily_box_office) 무DB·무키 검증 테스트

from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.master.hub.services.collectors.economic.kobis.kobis_box_office_collector import (  # noqa: E402
    parse_daily_box_office,
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


# KOBIS searchDailyBoxOfficeList.json 실제 응답 형태(2행 축약).
_SAMPLE = {
    "boxOfficeResult": {
        "boxofficeType": "일별 박스오피스",
        "showRange": "20260627~20260627",
        "dailyBoxOfficeList": [
            {
                "rnum": "1", "rank": "1", "rankInten": "0", "rankOldAndNew": "OLD",
                "movieCd": "20260101", "movieNm": "테스트무비A", "openDt": "2026-06-01",
                "salesAmt": "2776060500", "salesShare": "36.3", "salesAcc": "40541108500",
                "audiCnt": "353274", "audiAcc": "5328435", "scrnCnt": "697", "showCnt": "3223",
            },
            {
                "rnum": "2", "rank": "2", "rankInten": "1", "rankOldAndNew": "NEW",
                "movieCd": "20260202", "movieNm": "테스트무비B", "openDt": "2026-06-25",
                "salesAmt": "1500000000", "salesShare": "20.1", "salesAcc": "1500000000",
                "audiCnt": "180000", "audiAcc": "180000", "scrnCnt": "500", "showCnt": "2100",
            },
        ],
    }
}

_TGT = date(2026, 6, 27)


def test_basic_parse() -> None:
    rows = parse_daily_box_office(_SAMPLE, _TGT)
    check("2개 행 산출", len(rows) == 2)
    a = rows[0]
    check("source_type=KOBIS_BOXOFFICE_DAILY", a.source_type == "KOBIS_BOXOFFICE_DAILY")
    check("섹터 코드 CONTENT_MEDIA", a.raw_metadata["industry_sector"] == "CONTENT_MEDIA")
    check("published_at=기준일", a.published_at.date() == _TGT)
    check("영화명 → target", a.target_company_or_fund == "테스트무비A")
    check("매출 → investment_amount(int)", a.investment_amount == 2776060500)
    check("관객수 파싱", a.raw_metadata["audience_count"] == 353274)
    check("rank int 파싱", a.raw_metadata["rank"] == 1)


def test_source_url_unique_per_date() -> None:
    # 동일 영화라도 기준일이 다르면 source_url 이 달라 dedup 가능해야 한다.
    r1 = parse_daily_box_office(_SAMPLE, date(2026, 6, 27))[0]
    r2 = parse_daily_box_office(_SAMPLE, date(2026, 6, 28))[0]
    check("같은 영화·다른 날 source_url 상이", r1.source_url != r2.source_url)
    check("source_url 에 boDt 포함", "boDt=20260627" in r1.source_url)


def test_comma_and_missing() -> None:
    payload = {"boxOfficeResult": {"dailyBoxOfficeList": [
        {"movieCd": "1", "movieNm": "콤마무비", "salesAmt": "1,234,567", "audiCnt": "12,000"},
        {"movieCd": "", "movieNm": "코드없음", "salesAmt": "100"},   # movieCd 없음 → 스킵
        {"movieCd": "2", "movieNm": "", "salesAmt": "100"},          # movieNm 없음 → 스킵
    ]}}
    rows = parse_daily_box_office(payload, _TGT)
    check("유효 행만(1개)", len(rows) == 1)
    check("콤마 숫자 파싱", rows[0].investment_amount == 1234567)
    check("콤마 관객수 파싱", rows[0].raw_metadata["audience_count"] == 12000)


def test_empty_and_fault() -> None:
    check("빈 payload → []", parse_daily_box_office({}, _TGT) == [])
    check("리스트 없음 → []", parse_daily_box_office({"boxOfficeResult": {}}, _TGT) == [])


def main() -> None:
    test_basic_parse()
    test_source_url_unique_per_date()
    test_comma_and_missing()
    test_empty_and_fault()
    print(f"\n{'=' * 40}\nPASS={PASS} FAIL={FAIL}\n{'=' * 40}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
