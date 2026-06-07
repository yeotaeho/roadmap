"""신규 Economic 컬렉터(MFDS·BOK ECOS·보조금24·중기부MSS) 파싱·필터 단위 테스트.

네트워크·DB 없이 고정 fixture 로 컬렉터 로직만 검증한다.
실행: python scripts/economic_new_sources_parse_test.py
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from domain.master.hub.services.collectors.economic.mfds.mfds_bbs_collector import (  # noqa: E402
    PRESS_BOARD,
    MfdsBbsCollector,
    MfdsIngestWatermark,
    extract_seq,
    parse_mfds_list_rows,
    row_matches_keyword,
)
from domain.master.hub.services.collectors.economic.bok.bok_ecos_collector import (  # noqa: E402
    BokEcosCollector,
    EcosTarget,
)
from domain.master.hub.services.collectors.economic.subsidy24.subsidy24_collector import (  # noqa: E402
    Subsidy24Collector,
    parse_krw_amount,
    parse_modified_at,
)
from domain.master.hub.services.collectors.economic.mss.mss_bbs_collector import (  # noqa: E402
    _parse_list_page,
    _parse_date,
    MssWatermark,
    MssBbsCollector,
)
from domain.master.hub.services.collectors.economic.nps.nps_dart_collector import (  # noqa: E402
    NpsWatermark,
    NpsDartCollector,
    _is_bulk_holding,
    _parse_rcept_dt,
)
from domain.master.hub.services.collectors.economic.dart.dart_ipo_collector import (  # noqa: E402
    DartIpoCollector,
    DartIpoWatermark,
    _is_ipo_related,
)
from domain.master.hub.services.collectors.economic.kipris.kipris_patent_collector import (  # noqa: E402
    KiprisPatentCollector,
    KiprisWatermark,
    _TECH_KEYWORD_GROUPS,
)
from domain.master.hub.services.collectors.economic.naver.naver_datalab_collector import (  # noqa: E402
    NaverDatalabCollector,
    NaverDatalabWatermark,
    _DATALAB_KEYWORD_GROUPS,
)
from domain.master.hub.services.collectors.economic.naver.naver_search_collector import (  # noqa: E402
    NaverSearchCollector,
    NaverSearchWatermark,
    _NEWS_KEYWORD_GROUPS,
)

_passed = 0
_failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  [OK] {name}")
    else:
        _failed += 1
        print(f"  [FAIL] {name} {('-> ' + detail) if detail else ''}")


# ---------------------------------------------------------------------------
# MFDS fixtures
# ---------------------------------------------------------------------------

# 정적 SSR 목록 — 표준 td.title a / td.date 구조 + JS onclick / data-seq 변형 혼합
MFDS_LIST_HTML = """
<table class="board_list">
  <thead><tr><th>번호</th><th>제목</th><th>등록일</th></tr></thead>
  <tbody>
    <tr>
      <td>101</td>
      <td class="title"><a href="/brd/m_99/view.do?seq=48123&srchFr=">식약처, 국산 신약 'OO정' 품목허가</a></td>
      <td class="date">2026-06-05</td>
    </tr>
    <tr>
      <td>100</td>
      <td class="title"><a href="javascript:;" onclick="fnView('48050')">식약처, 식품 표시 광고 가이드 개정 안내</a></td>
      <td class="date">2026-05-30</td>
    </tr>
    <tr>
      <td>99</td>
      <td class="title"><a href="javascript:;" data-seq="47990">희귀의약품 임상 3상 조건부 승인</a></td>
      <td class="date">2026-05-21</td>
    </tr>
    <tr>
      <td>98</td>
      <td class="title"><a href="/brd/m_99/view.do?seq=47001">2025년 의료기기 허가 통계 발표</a></td>
      <td class="date">2025-12-30</td>
    </tr>
  </tbody>
</table>
"""


def test_mfds_extract_seq() -> None:
    print("\n[MFDS] extract_seq")
    check("href query seq", extract_seq("/brd/m_99/view.do?seq=48123", "") == 48123)
    check("onclick fnView", extract_seq("javascript:;", "fnView('48050')") == 48050)
    check("no id -> None", extract_seq("", "") is None)


def test_mfds_parse_list() -> None:
    print("\n[MFDS] parse_mfds_list_rows")
    rows = parse_mfds_list_rows(MFDS_LIST_HTML, PRESS_BOARD)
    check("4 rows parsed", len(rows) == 4, f"got {len(rows)}")
    by_seq = {r["seq"]: r for r in rows}
    check("seq 48123 url canonical", by_seq.get(48123, {}).get("url", "").endswith("view.do?seq=48123"))
    check("data-seq 47990 extracted", 47990 in by_seq)
    check("date parsed year", by_seq.get(48123, {}).get("published_year") == 2026)
    check("2025 row year", by_seq.get(47001, {}).get("published_year") == 2025)


def test_mfds_keyword() -> None:
    print("\n[MFDS] row_matches_keyword")
    kw = PRESS_BOARD.keywords
    check("허가 hit", row_matches_keyword("국산 신약 품목허가", kw))
    check("가이드 개정 miss", not row_matches_keyword("식품 표시 광고 가이드 개정 안내", kw))
    check("조건부 승인 hit", row_matches_keyword("임상 3상 조건부 승인", kw))


def test_mfds_consume() -> None:
    print("\n[MFDS] _consume_rows (year=2026 + keyword filter)")
    rows = parse_mfds_list_rows(MFDS_LIST_HTML, PRESS_BOARD)
    collector = MfdsBbsCollector(PRESS_BOARD)
    stats = {"fetched_total": 0, "filtered_year": 0, "filtered_keyword": 0, "skipped_watermark": 0}
    kept: list = []
    hit = collector._consume_rows(rows, stats, kept, None, None, 100)
    kept_titles = [k["title"] for k in kept]
    check("kept 2 (허가+조건부승인, 2026)", len(kept) == 2, f"kept={kept_titles}")
    check("filtered keyword 1 (가이드)", stats["filtered_keyword"] == 1, str(stats))
    check("filtered year 1 (2025)", stats["filtered_year"] == 1, str(stats))
    check("not early-stop", hit is False)

    print("\n[MFDS] _consume_rows watermark(seq=47990) stops")
    stats2 = {"fetched_total": 0, "filtered_year": 0, "filtered_keyword": 0, "skipped_watermark": 0}
    kept2: list = []
    hit2 = collector._consume_rows(rows, stats2, kept2, 47990, None, 100)
    # 48123(keep) -> 48050(keyword filtered) -> 47990(watermark stop)
    check("watermark stop True", hit2 is True)
    check("kept only 1 before watermark", len(kept2) == 1, f"kept={[k['seq'] for k in kept2]}")
    check("skipped_watermark counted", stats2["skipped_watermark"] == 1, str(stats2))


def test_mfds_to_dto() -> None:
    print("\n[MFDS] _to_dto shape")
    rows = parse_mfds_list_rows(MFDS_LIST_HTML, PRESS_BOARD)
    collector = MfdsBbsCollector(PRESS_BOARD)
    row = next(r for r in rows if r["seq"] == 48123)
    dto = collector._to_dto(row, body_text="본문 텍스트")
    check("source_type", dto.source_type == "GOVT_MFDS_APPROVAL")
    check("source_url set", bool(dto.source_url) and dto.source_url.endswith("seq=48123"))
    check("investment_amount None (signal)", dto.investment_amount is None)
    check("investor", dto.investor_name == "식품의약품안전처")
    check("meta data_role", (dto.raw_metadata or {}).get("data_role") == "TREND_SIGNAL")
    check("meta sector BIO", (dto.raw_metadata or {}).get("industry_sector") == "BIO")
    check("meta seq", (dto.raw_metadata or {}).get("seq") == 48123)
    check("body stored", (dto.raw_metadata or {}).get("body_text") == "본문 텍스트")


# ---------------------------------------------------------------------------
# BOK ECOS fixtures
# ---------------------------------------------------------------------------

ECOS_OK = {
    "StatisticSearch": {
        "list_total_count": 2,
        "row": [
            {
                "STAT_CODE": "722Y001",
                "STAT_NAME": "1.3.1. 한국은행 기준금리",
                "ITEM_CODE1": "0101000",
                "ITEM_NAME1": "한국은행 기준금리",
                "UNIT_NAME": "%",
                "TIME": "202605",
                "DATA_VALUE": "2.75",
            },
            {
                "STAT_CODE": "722Y001",
                "STAT_NAME": "1.3.1. 한국은행 기준금리",
                "ITEM_CODE1": "0101000",
                "ITEM_NAME1": "한국은행 기준금리",
                "UNIT_NAME": "%",
                "TIME": "202604",
                "DATA_VALUE": "2.75",
            },
        ],
    }
}

ECOS_ERR = {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}

ECOS_FLOW = {
    "StatisticSearch": {
        "list_total_count": 1,
        "row": [
            {
                "STAT_CODE": "301Y017",
                "STAT_NAME": "국제수지(직접투자)",
                "ITEM_CODE1": "FDI",
                "ITEM_NAME1": "외국인직접투자",
                "UNIT_NAME": "백만달러",
                "TIME": "202603",
                "DATA_VALUE": "1234.5",
            }
        ],
    }
}


def test_ecos_parse() -> None:
    print("\n[ECOS] _parse_rows")
    base = EcosTarget("722Y001", "M", "0101000", "BOK_ECOS_BASE_RATE", False, "기준금리")
    rows = BokEcosCollector._parse_rows(ECOS_OK, base)
    check("2 rows", len(rows) == 2, f"got {len(rows)}")
    check("error response -> []", BokEcosCollector._parse_rows(ECOS_ERR, base) == [])
    check("empty dict -> []", BokEcosCollector._parse_rows({}, base) == [])


def test_ecos_to_dto_indicator() -> None:
    print("\n[ECOS] _to_dto (indicator, amount None)")
    col = BokEcosCollector("DUMMY_KEY")
    base = EcosTarget("722Y001", "M", "0101000", "BOK_ECOS_BASE_RATE", False, "기준금리")
    dto = col._to_dto(base, ECOS_OK["StatisticSearch"]["row"][0])
    check("source_type", dto.source_type == "BOK_ECOS_BASE_RATE")
    check("synthetic url", dto.source_url == "ecos://722Y001/0101000/202605")
    check("amount None (indicator)", dto.investment_amount is None)
    check("published 2026-05 (TIME=202605)", dto.published_at is not None and dto.published_at.year == 2026 and dto.published_at.month == 5)
    check("meta data_value", (dto.raw_metadata or {}).get("data_value") == "2.75")
    check("meta unit", (dto.raw_metadata or {}).get("unit_name") == "%")
    check("meta role indicator", (dto.raw_metadata or {}).get("data_role") == "MACRO_INDICATOR")


def test_ecos_to_dto_flow() -> None:
    print("\n[ECOS] _to_dto (flow, amount mapped)")
    col = BokEcosCollector("DUMMY_KEY")
    flow = EcosTarget("301Y017", "M", "FDI", "BOK_ECOS_FDI", True, "FDI")
    dto = col._to_dto(flow, ECOS_FLOW["StatisticSearch"]["row"][0])
    # 1234.5 -> round() banker's rounding -> 1234 (대규모 금액에선 무시 가능)
    check("amount mapped int", dto.investment_amount == 1234, f"got {dto.investment_amount}")
    check("role flow", (dto.raw_metadata or {}).get("data_role") == "MACRO_FLOW")


def test_ecos_key_validation() -> None:
    print("\n[ECOS] key validation")
    raised = False
    try:
        BokEcosCollector("")
    except ValueError:
        raised = True
    check("empty key raises ValueError", raised)


def test_subsidy24_parse_amount() -> None:
    print("\n[SUBSIDY24] 금액 파싱")
    check("억원",            parse_krw_amount("최대 5억원 지원") == 500_000_000)
    check("만원",            parse_krw_amount("월 50만원 지급") == 500_000)
    check("억+만원 복합",    parse_krw_amount("3억 2천만원 한도") == 320_000_000)
    check("천만원",          parse_krw_amount("연간 3천만원") == 30_000_000)
    check("백만원",          parse_krw_amount("1,500만원") == 15_000_000)
    check("원단위 5자리",    parse_krw_amount("국공립 100,000원") == 100_000)
    check("파싱 불가",       parse_krw_amount("지원 없음") is None)
    check("None 입력",       parse_krw_amount(None) is None)


def test_subsidy24_parse_datetime() -> None:
    from datetime import timezone, timedelta
    _KST = timezone(timedelta(hours=9))
    print("\n[SUBSIDY24] 수정일시 파싱")
    dt = parse_modified_at("20260430093900")
    check("14자리 파싱", dt is not None and dt.year == 2026 and dt.month == 4)
    dt8 = parse_modified_at("20260501")
    check("8자리 파싱", dt8 is not None and dt8.day == 1)
    check("None 입력", parse_modified_at(None) is None)
    check("빈 문자열", parse_modified_at("") is None)


def test_subsidy24_versioned_source_url() -> None:
    print("\n[SUBSIDY24] 변경 이력 source_url")
    collector = object.__new__(Subsidy24Collector)
    dto = collector._to_dto(
        {
            "서비스ID": "S1",
            "서비스명": "지원 서비스",
            "상세조회URL": "https://example.test/S1",
            "수정일시": "20260607123000",
        }
    )
    check("DTO 생성", dto is not None)
    check(
        "수정일시 버전 포함",
        dto is not None
        and dto.source_url == "https://example.test/S1#modified=20260607123000",
    )


# ---------------------------------------------------------------------------
# MSS BBS fixtures
# ---------------------------------------------------------------------------

MSS_LIST_HTML = """
<table>
<caption><strong>보도자료목록</strong></caption>
<thead><tr><th>번호</th><th>제목</th><th>담당부서</th><th>첨부</th><th>등록일</th><th>조회</th></tr></thead>
<tbody>
  <tr onclick="doBbsFView('86','1068803','16010100','1068803');return false;"
      title="중기부-KB금융, 100억원 규모 상생협력사업 추진">
    <td>9809</td>
    <td class="subject bss-sub-text"><a href="#view">중기부-KB금융, 100억원 규모 상생협력사업 추진</a></td>
    <td class="cd_subject"><span>상생</span></td>
    <td class="attached-files"></td>
    <td>2026.06.05</td>
    <td>395</td>
  </tr>
  <tr onclick="doBbsFView('86','1068779','16010100','1068779');return false;"
      title="신산업 규제개선, 규제자유특구로 해결">
    <td>9808</td>
    <td class="subject bss-sub-text"><a href="#view">신산업 규제개선, 규제자유특구로 해결</a></td>
    <td class="cd_subject"><span>특구정책과</span></td>
    <td class="attached-files"></td>
    <td>2026.06.04</td>
    <td>100</td>
  </tr>
  <tr onclick="doBbsFView('86','1068773','16010100','1068773');return false;"
      title="중기부, 중소벤처24 통합회원 서비스 시범 운영">
    <td>9807</td>
    <td class="subject bss-sub-text"><a href="#view">중기부, 중소벤처24 통합회원 서비스 시범 운영</a></td>
    <td class="cd_subject"><span>정보화담당관</span></td>
    <td class="attached-files"></td>
    <td>2026.06.04</td>
    <td>80</td>
  </tr>
</tbody>
</table>
"""


def test_mss_parse_list() -> None:
    print("\n[MSS] _parse_list_page")
    items = _parse_list_page(MSS_LIST_HTML)
    check("3개 항목", len(items) == 3, f"got {len(items)}")
    check("bcIdx 추출", items[0]["bc_idx"] == 1068803)
    check("제목 추출", "100억원" in items[0]["title"])
    check("담당부서", items[0]["dept"] == "상생")
    check("날짜 추출", items[0]["date_str"] == "2026.06.05")
    check("두번째 bcIdx", items[1]["bc_idx"] == 1068779)


def test_mss_parse_date() -> None:
    print("\n[MSS] _parse_date")
    dt = _parse_date("2026.06.05")
    check("날짜 파싱", dt is not None and dt.year == 2026 and dt.month == 6 and dt.day == 5)
    check("None 입력", _parse_date(None) is None)  # type: ignore[arg-type]
    check("잘못된 형식", _parse_date("20260605") is None)


def test_mss_watermark_stop() -> None:
    print("\n[MSS] watermark 중단 로직")
    items = _parse_list_page(MSS_LIST_HTML)
    # bcIdx=1068779 이하 항목은 skip
    wm = MssWatermark(bc_idx=1068779)
    kept = [it for it in items if it["bc_idx"] > (wm.bc_idx or 0)]
    check("워터마크 이전 1건", len(kept) == 1, f"kept={[i['bc_idx'] for i in kept]}")
    check("1068803만 남음", kept[0]["bc_idx"] == 1068803)


def test_mss_to_dto() -> None:
    print("\n[MSS] _to_dto shape")
    items = _parse_list_page(MSS_LIST_HTML)
    dto = MssBbsCollector._to_dto(items[0])
    check("source_type", dto.source_type == "GOVT_MSS_PRESS")
    check("source_url bcIdx", "1068803" in dto.source_url)
    check("investor_name", dto.investor_name == "중소벤처기업부")
    check("amount 100억", dto.investment_amount == 10_000_000_000)
    check("published_at 2026-06-05", dto.published_at is not None and dto.published_at.day == 5)
    check("metadata bc_idx", (dto.raw_metadata or {}).get("bc_idx") == 1068803)
    check("metadata data_role", (dto.raw_metadata or {}).get("data_role") == "POLICY_SIGNAL")


# ---------------------------------------------------------------------------
# NPS 국민연금 컬렉터 테스트
# ---------------------------------------------------------------------------

_NPS_ITEMS = [
    {"rcept_no": "20260605001234", "corp_code": "00401796", "corp_name": "삼성전기",
     "corp_cls": "Y", "report_nm": "주식등의대량보유상황보고서(약식)", "flr_nm": "국민연금공단", "rcept_dt": "20260605"},
    {"rcept_no": "20260605001235", "corp_code": "00403590", "corp_name": "한미약품",
     "corp_cls": "Y", "report_nm": "임원ㆍ주요주주특정증권등소유상황보고서", "flr_nm": "국민연금공단", "rcept_dt": "20260605"},
    {"rcept_no": "20260604000999", "corp_code": "00000001", "corp_name": "진양제약",
     "corp_cls": "Y", "report_nm": "주식등의대량보유상황보고서(일반)", "flr_nm": "최재준", "rcept_dt": "20260604"},
]


def test_nps_bulk_holding_filter() -> None:
    print("\n[NPS] 대량보유보고서 필터")
    check("약식 포함", _is_bulk_holding("주식등의대량보유상황보고서(약식)"))
    check("일반 포함", _is_bulk_holding("주식등의대량보유상황보고서(일반)"))
    check("임원주요주주 제외", not _is_bulk_holding("임원ㆍ주요주주특정증권등소유상황보고서"))
    check("빈문자 제외", not _is_bulk_holding(""))


def test_nps_parse_rcept_dt() -> None:
    print("\n[NPS] rcept_dt 파싱")
    dt = _parse_rcept_dt("20260605")
    check("YYYYMMDD 파싱", dt is not None and dt.year == 2026 and dt.month == 6 and dt.day == 5)
    check("None 입력", _parse_rcept_dt(None) is None)
    check("짧은 문자열", _parse_rcept_dt("2026") is None)


def test_nps_to_dto() -> None:
    print("\n[NPS] _to_dto")
    item = _NPS_ITEMS[0]
    dto = NpsDartCollector._to_dto(item)
    check("source_type", dto.source_type == "NPS_PORTFOLIO_DART")
    check("source_url rcept_no", "20260605001234" in (dto.source_url or ""))
    check("investor_name", dto.investor_name == "국민연금공단")
    check("target_company", dto.target_company_or_fund == "삼성전기")
    check("title prefix", dto.raw_title.startswith("[국민연금]"))
    check("metadata rcept_no", (dto.raw_metadata or {}).get("rcept_no") == "20260605001234")
    check("metadata data_role", (dto.raw_metadata or {}).get("data_role") == "INSTITUTIONAL_PORTFOLIO")
    check("published 2026-06-05", dto.published_at is not None and dto.published_at.day == 5)


def test_nps_watermark() -> None:
    print("\n[NPS] watermark 동작")
    wm = NpsWatermark(last_rcept_dt="20260604")
    check("last_rcept_dt 저장", wm.last_rcept_dt == "20260604")
    check("None watermark", NpsWatermark().last_rcept_dt is None)


# ---------------------------------------------------------------------------
# 네이버 검색 컬렉터 테스트
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# DART IPO 발행공시 컬렉터 테스트
# ---------------------------------------------------------------------------

_IPO_ITEMS = [
    {"rcept_no": "20260605003001", "corp_code": "00123456", "corp_name": "테크스타트업",
     "corp_cls": "K", "report_nm": "증권신고서(지분증권)", "flr_nm": "테크스타트업", "rcept_dt": "20260605"},
    {"rcept_no": "20260605003002", "corp_code": "00234567", "corp_name": "케이티스카이라이프",
     "corp_cls": "Y", "report_nm": "증권신고서(채무증권)", "flr_nm": "케이티스카이라이프", "rcept_dt": "20260605"},
    {"rcept_no": "20260605003003", "corp_code": "00345678", "corp_name": "소액공모회사",
     "corp_cls": "K", "report_nm": "소액공모공시서류", "flr_nm": "소액공모회사", "rcept_dt": "20260605"},
]


def test_ipo_filter() -> None:
    print("\n[DART_IPO] 필터 로직")
    check("지분증권 포함", _is_ipo_related("증권신고서(지분증권)"))
    check("기재정정_지분증권 포함", _is_ipo_related("[기재정정]증권신고서(지분증권)"))
    check("소액공모 포함", _is_ipo_related("소액공모공시서류"))
    check("소액공모실적 포함", _is_ipo_related("소액공모실적보고서"))
    check("채무증권 제외", not _is_ipo_related("증권신고서(채무증권)"))
    check("파생결합 제외", not _is_ipo_related("일괄신고추가서류(파생결합증권-주가연계증권)"))
    check("투자설명서 제외", not _is_ipo_related("투자설명서(일괄신고)"))
    check("빈문자 제외", not _is_ipo_related(""))


def test_ipo_to_dto() -> None:
    print("\n[DART_IPO] _to_dto")
    item = _IPO_ITEMS[0]
    dto = DartIpoCollector._to_dto(item)
    check("source_type", dto.source_type == "DART_IPO_DISCLOSURE")
    check("source_url rcept_no", "20260605003001" in (dto.source_url or ""))
    check("target_company", dto.target_company_or_fund == "테크스타트업")
    check("title prefix", dto.raw_title.startswith("[IPO공시]"))
    check("metadata data_role", (dto.raw_metadata or {}).get("data_role") == "IPO_SIGNAL")
    check("metadata report_nm", (dto.raw_metadata or {}).get("report_nm") == "증권신고서(지분증권)")
    check("published 2026-06-05", dto.published_at is not None and dto.published_at.day == 5)


def test_ipo_watermark() -> None:
    print("\n[DART_IPO] watermark")
    wm = DartIpoWatermark(last_rcept_dt="20260601")
    check("last_rcept_dt 저장", wm.last_rcept_dt == "20260601")
    check("None watermark", DartIpoWatermark().last_rcept_dt is None)


# ---------------------------------------------------------------------------
# KIPRIS 특허 트렌드 컬렉터 테스트
# ---------------------------------------------------------------------------

def test_kipris_keyword_groups() -> None:
    print("\n[KIPRIS] 키워드 그룹 구조")
    check("그룹 개수 >= 5", len(_TECH_KEYWORD_GROUPS) >= 5)
    group_names = [g for g, _ in _TECH_KEYWORD_GROUPS]
    check("AI_ML 그룹 존재", "AI_ML" in group_names)
    check("BIOHEALTH 그룹 존재", "BIOHEALTH" in group_names)
    check("ENERGY_CLIMATE 그룹 존재", "ENERGY_CLIMATE" in group_names)
    total_keywords = sum(len(kws) for _, kws in _TECH_KEYWORD_GROUPS)
    check("총 키워드 12개 이상", total_keywords >= 12)
    check("키워드 월 한도 내 (100건 이하)", total_keywords <= 100)


def test_kipris_to_dto() -> None:
    print("\n[KIPRIS] _to_dto 변환")
    import urllib.parse
    from datetime import datetime, timezone, timedelta

    _KST = timezone(timedelta(hours=9))
    week_start = datetime(2026, 6, 2, tzinfo=_KST)
    dto = KiprisPatentCollector._to_dto(
        keyword="인공지능",
        group_name="AI_ML",
        total=42,
        sample_apps=["10-2026-0001234", "10-2026-0001235"],
        week_start_str="20260602",
        week_end_str="20260608",
        week_start_dt=week_start,
    )
    check("source_type", dto.source_type == "PATENT_KIPRIS_TREND")
    check("source_url에 키워드 인코딩 포함", urllib.parse.quote("인공지능") in (dto.source_url or ""))
    check("source_url에 날짜 포함", "20260602" in (dto.source_url or ""))
    check("raw_title에 건수 포함", "42" in (dto.raw_title or ""))
    meta = dto.raw_metadata or {}
    check("metadata.keyword", meta.get("keyword") == "인공지능")
    check("metadata.group_name", meta.get("group_name") == "AI_ML")
    check("metadata.total_count", meta.get("total_count") == 42)
    check("metadata.week_start", meta.get("week_start") == "20260602")
    check("metadata.data_role", meta.get("data_role") == "PATENT_TREND_SIGNAL")
    check("metadata.sample_apps length", len(meta.get("sample_applications", [])) == 2)
    check("published_at KST", dto.published_at == week_start)


def test_kipris_watermark() -> None:
    print("\n[KIPRIS] 워터마크 구조")
    wm_none = KiprisWatermark()
    check("기본값 None", wm_none.last_week_start is None)
    wm = KiprisWatermark(last_week_start="20260602")
    check("주 시작일 저장", wm.last_week_start == "20260602")
    check("frozen dataclass (불변)", wm is not None)


def test_kipris_bool_params() -> None:
    print("\n[KIPRIS] API 필수 Boolean 파라미터")
    from domain.master.hub.services.collectors.economic.kipris.kipris_patent_collector import _BOOL_PARAMS
    check("patent=Y", _BOOL_PARAMS.get("patent") == "Y")
    check("utility=N (실용신안 제외)", _BOOL_PARAMS.get("utility") == "N")
    check("register=Y", _BOOL_PARAMS.get("register") == "Y")


# ---------------------------------------------------------------------------
# Naver DataLab 컬렉터 테스트
# ---------------------------------------------------------------------------

def test_datalab_keyword_groups() -> None:
    print("\n[DATALAB] 키워드 그룹 구조")
    check("그룹 개수 7개", len(_DATALAB_KEYWORD_GROUPS) == 7)
    names = [g for g, _ in _DATALAB_KEYWORD_GROUPS]
    check("AI_TECH 포함", "AI_TECH" in names)
    for gname, kws in _DATALAB_KEYWORD_GROUPS:
        check(f"{gname} 키워드 1~5개", 1 <= len(kws) <= 5)


def test_datalab_to_dto() -> None:
    print("\n[DATALAB] _to_dto 변환")
    from datetime import datetime, timezone, timedelta
    _KST = timezone(timedelta(hours=9))
    week_start = datetime(2026, 6, 1, tzinfo=_KST)

    dto = NaverDatalabCollector._to_dto(
        group_name="AI_TECH",
        keywords=["인공지능", "AI", "생성형AI"],
        ratio=72.5,
        week_start_str="20260601",
        week_end_str="20260607",
        week_start_dt=week_start,
    )
    check("source_type", dto.source_type == "DISCOURSE_NAVER_DATALAB")
    check("source_url에 그룹명 포함", "AI_TECH" in (dto.source_url or ""))
    check("source_url에 weekStart 포함", "20260601" in (dto.source_url or ""))
    check("raw_title에 ratio 포함", "72.5" in (dto.raw_title or ""))
    meta = dto.raw_metadata or {}
    check("metadata.group_name", meta.get("group_name") == "AI_TECH")
    check("metadata.ratio", meta.get("ratio") == 72.5)
    check("metadata.week_start", meta.get("week_start") == "20260601")
    check("metadata.keywords 길이", len(meta.get("keywords", [])) == 3)
    check("metadata.data_role", meta.get("data_role") == "SEARCH_TREND_SIGNAL")
    check("published_at KST", dto.published_at == week_start)
    check("investment_amount None", dto.investment_amount is None)
    check("currency KRW (기본값)", dto.currency == "KRW")


def test_datalab_watermark() -> None:
    print("\n[DATALAB] 워터마크 구조")
    wm_none = NaverDatalabWatermark()
    check("기본값 None", wm_none.last_week_start is None)
    wm = NaverDatalabWatermark(last_week_start="20260601")
    check("주 시작일 저장", wm.last_week_start == "20260601")


def test_datalab_source_url_unique() -> None:
    print("\n[DATALAB] source_url 멱등성")
    from datetime import datetime, timezone, timedelta
    _KST = timezone(timedelta(hours=9))
    wk = datetime(2026, 6, 1, tzinfo=_KST)
    dto1 = NaverDatalabCollector._to_dto("AI_TECH", ["AI"], 50.0, "20260601", "20260607", wk)
    dto2 = NaverDatalabCollector._to_dto("AI_TECH", ["AI"], 55.0, "20260601", "20260607", wk)
    dto3 = NaverDatalabCollector._to_dto("STARTUP_VC", ["스타트업"], 30.0, "20260601", "20260607", wk)
    check("같은 그룹+주 → 동일 URL (멱등)", dto1.source_url == dto2.source_url)
    check("다른 그룹 → 다른 URL", dto1.source_url != dto3.source_url)


def test_datalab_batch_size() -> None:
    print("\n[DATALAB] 배치 사이즈 (API 5그룹/요청 한도)")
    from domain.master.hub.services.collectors.economic.naver.naver_datalab_collector import _BATCH_SIZE
    check("BATCH_SIZE=5 (API 한도)", _BATCH_SIZE == 5)
    n_batches = (len(_DATALAB_KEYWORD_GROUPS) + _BATCH_SIZE - 1) // _BATCH_SIZE
    check("7그룹 → 2배치 요청", n_batches == 2)


def test_datalab_7_groups() -> None:
    print("\n[DATALAB] 7그룹 구성 (청년 진로 그룹 포함)")
    group_names = [g for g, _ in _DATALAB_KEYWORD_GROUPS]
    check("총 7그룹", len(_DATALAB_KEYWORD_GROUPS) == 7)
    check("CAREER_SWITCH 존재", "CAREER_SWITCH" in group_names)
    check("GOV_SUPPORT 존재", "GOV_SUPPORT" in group_names)
    check("AI_TECH 존재", "AI_TECH" in group_names)
    career_kws = next(kws for g, kws in _DATALAB_KEYWORD_GROUPS if g == "CAREER_SWITCH")
    check("CAREER_SWITCH에 이직 키워드", "이직" in career_kws)
    gov_kws = next(kws for g, kws in _DATALAB_KEYWORD_GROUPS if g == "GOV_SUPPORT")
    check("GOV_SUPPORT에 청년지원 키워드", "청년지원" in gov_kws)


# ---------------------------------------------------------------------------
# Naver Search (뉴스 기사 수) 테스트
# ---------------------------------------------------------------------------


def test_naver_search_keyword_groups() -> None:
    print("\n[NAVER_SEARCH] 키워드 그룹 구성 (7그룹 24개 키워드)")
    group_names = [g for g, _ in _NEWS_KEYWORD_GROUPS]
    check("총 7그룹", len(_NEWS_KEYWORD_GROUPS) == 7)
    total_kws = sum(len(kws) for _, kws in _NEWS_KEYWORD_GROUPS)
    check("총 24개 키워드", total_kws == 24)
    check("CAREER_SWITCH 존재", "CAREER_SWITCH" in group_names)
    check("GOV_SUPPORT 존재", "GOV_SUPPORT" in group_names)
    career_kws = next(kws for g, kws in _NEWS_KEYWORD_GROUPS if g == "CAREER_SWITCH")
    check("CAREER_SWITCH에 이직 키워드", "이직" in career_kws)
    gov_kws = next(kws for g, kws in _NEWS_KEYWORD_GROUPS if g == "GOV_SUPPORT")
    check("GOV_SUPPORT에 청년지원 키워드", "청년지원" in gov_kws)


def test_naver_search_to_dto() -> None:
    print("\n[NAVER_SEARCH] _to_dto 변환")
    from datetime import datetime, timezone, timedelta
    _KST = timezone(timedelta(hours=9))
    target_dt = datetime(2026, 6, 6, tzinfo=_KST)

    dto = NaverSearchCollector._to_dto(
        group_name="AI_ML",
        keyword="인공지능",
        article_count=1234,
        date_str="20260606",
        target_dt=target_dt,
    )
    check("source_type", dto.source_type == "DISCOURSE_NAVER_NEWS")
    check("source_url에 키워드 인코딩 포함", "%EC%9D%B8%EA%B3%B5%EC%A7%80%EB%8A%A5" in (dto.source_url or ""))
    check("source_url에 날짜 포함", "2026.06.06" in (dto.source_url or ""))
    check("raw_title에 기사 수 포함", "1234" in (dto.raw_title or ""))
    check("raw_title에 그룹명 포함", "AI_ML" in (dto.raw_title or ""))
    meta = dto.raw_metadata or {}
    check("metadata.group_name", meta.get("group_name") == "AI_ML")
    check("metadata.keyword", meta.get("keyword") == "인공지능")
    check("metadata.article_count", meta.get("article_count") == 1234)
    check("metadata.date", meta.get("date") == "20260606")
    check("metadata.data_role", meta.get("data_role") == "NEWS_SUPPLY_SIGNAL")
    check("investment_amount None", dto.investment_amount is None)
    check("currency KRW", dto.currency == "KRW")
    check("published_at KST", dto.published_at == target_dt)


def test_naver_search_watermark() -> None:
    print("\n[NAVER_SEARCH] 워터마크 구조")
    wm_none = NaverSearchWatermark()
    check("기본값 None", wm_none.last_collected_date is None)
    wm = NaverSearchWatermark(last_collected_date="20260606")
    check("날짜 저장", wm.last_collected_date == "20260606")


def test_naver_search_source_url_unique() -> None:
    print("\n[NAVER_SEARCH] source_url 멱등성")
    from datetime import datetime, timezone, timedelta
    _KST = timezone(timedelta(hours=9))
    dt = datetime(2026, 6, 6, tzinfo=_KST)
    dto1 = NaverSearchCollector._to_dto("AI_ML", "인공지능", 100, "20260606", dt)
    dto2 = NaverSearchCollector._to_dto("AI_ML", "인공지능", 200, "20260606", dt)
    dto3 = NaverSearchCollector._to_dto("AI_ML", "AI", 100, "20260606", dt)
    dto4 = NaverSearchCollector._to_dto("AI_ML", "인공지능", 100, "20260607", dt)
    check("같은 키워드+날짜 → 동일 URL (멱등)", dto1.source_url == dto2.source_url)
    check("다른 키워드 → 다른 URL", dto1.source_url != dto3.source_url)
    check("다른 날짜 → 다른 URL", dto1.source_url != dto4.source_url)


def main() -> int:
    print("=" * 78)
    print("신규 Economic 컬렉터 파싱 단위 테스트 (MFDS/BOK ECOS/보조금24/중기부MSS/NPS/NaverSearch/KIPRIS/DataLab) - 무네트워크")
    print("=" * 78)

    test_mfds_extract_seq()
    test_mfds_parse_list()
    test_mfds_keyword()
    test_mfds_consume()
    test_mfds_to_dto()

    test_ecos_parse()
    test_ecos_to_dto_indicator()
    test_ecos_to_dto_flow()
    test_ecos_key_validation()

    test_subsidy24_parse_amount()
    test_subsidy24_parse_datetime()
    test_subsidy24_versioned_source_url()

    test_mss_parse_list()
    test_mss_parse_date()
    test_mss_watermark_stop()
    test_mss_to_dto()

    test_nps_bulk_holding_filter()
    test_nps_parse_rcept_dt()
    test_nps_to_dto()
    test_nps_watermark()

    test_ipo_filter()
    test_ipo_to_dto()
    test_ipo_watermark()

    test_kipris_keyword_groups()
    test_kipris_to_dto()
    test_kipris_watermark()
    test_kipris_bool_params()

    test_datalab_keyword_groups()
    test_datalab_to_dto()
    test_datalab_watermark()
    test_datalab_source_url_unique()
    test_datalab_batch_size()
    test_datalab_7_groups()

    test_naver_search_keyword_groups()
    test_naver_search_to_dto()
    test_naver_search_watermark()
    test_naver_search_source_url_unique()

    print("\n" + "=" * 78)
    print(f"결과: PASS={_passed}  FAIL={_failed}")
    print("=" * 78)
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
