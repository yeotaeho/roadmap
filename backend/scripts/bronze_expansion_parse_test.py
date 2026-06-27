# People·Discourse·Opportunity·Company 신규 수집기 무네트워크 파싱 회귀 테스트

from __future__ import annotations

import json
import os
import sys
from datetime import date

# settings 임포트를 위한 최소 환경값 (DB 미접속 — 파싱만 검증).
for _k, _v in dict(
    NEON_DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
    JWT_SECRET="x",
    NAVER_CLIENT_ID="x",
    NAVER_CLIENT_SECRET="x",
    NAVER_REDIRECT_URI="x",
).items():
    os.environ.setdefault(_k, _v)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


# ---------------------------------------------------------------------------
# People — 고용24 채용 (직종별 건수 집계)
# ---------------------------------------------------------------------------
def test_goyong24_recruit() -> None:
    from domain.master.hub.services.collectors.people.goyong24.recruit_collector import (
        parse_recruit_payload,
        aggregate_recruit_demand,
    )

    xml = """<dhsList>
      <emp><wantedAuthNo>K1</wantedAuthNo><jobsNm>응용SW개발</jobsNm><title>AI개발</title></emp>
      <emp><wantedAuthNo>K2</wantedAuthNo><jobsNm>응용SW개발</jobsNm><title>데이터</title></emp>
      <emp><wantedAuthNo>K3</wantedAuthNo><jobsNm>간호</jobsNm><title>간호사</title></emp>
    </dhsList>"""
    items = parse_recruit_payload(xml)
    rows = aggregate_recruit_demand(items, date(2026, 6, 23))
    check("goyong24 XML 파싱 3건", len(items) == 3)
    check("goyong24 직종별 집계 2직종", len(rows) == 2)
    top = max(rows, key=lambda r: r.search_volume_or_count)
    check("goyong24 최다직종=응용SW개발(2건)", top.keyword_or_job == "응용SW개발" and top.search_volume_or_count == 2)
    check("goyong24 data_role=DEMAND_HIRING_SIGNAL", rows[0].raw_metadata["data_role"] == "DEMAND_HIRING_SIGNAL")

    js = '{"root":{"emp":[{"jobsNm":"요리","title":"셰프"},{"jobsNm":"요리","title":"조리"}]}}'
    rows2 = aggregate_recruit_demand(parse_recruit_payload(js), date(2026, 6, 23))
    check("goyong24 JSON 집계", rows2 and rows2[0].search_volume_or_count == 2)


def test_saramin() -> None:
    from domain.master.hub.services.collectors.people.saramin.saramin_recruit_collector import (
        _DEFAULT_KEYWORDS,
        _JOB_KEYWORDS,
        _KEYWORDS,
        parse_total,
    )

    check("saramin total 정수 추출", parse_total({"jobs": {"total": "1,234"}}) == 1234)
    check("saramin total 없음 None", parse_total({"jobs": {}}) is None)
    # ⑤b — 직무·스킬 키워드 보강(섹터 키워드 보존 + 직무 키워드 추가).
    check("기본 수집 = 섹터 + 직무", set(_DEFAULT_KEYWORDS) == set(_KEYWORDS) | set(_JOB_KEYWORDS))
    check("직무 키워드 포함(데이터엔지니어)", "데이터엔지니어" in _DEFAULT_KEYWORDS)
    check("섹터 키워드 보존(인공지능)", "인공지능" in _DEFAULT_KEYWORDS)
    check("직무 키워드 다수(>=10)", len(_JOB_KEYWORDS) >= 10)


# ---------------------------------------------------------------------------
# Discourse — 뉴스 RSS
# ---------------------------------------------------------------------------
def test_news_rss() -> None:
    from domain.master.hub.services.collectors.discourse.news_rss.news_rss_collector import (
        parse_feed_entries,
        NewsFeed,
    )

    rss = """<?xml version='1.0'?><rss version='2.0'><channel><title>t</title>
      <item><title>AI 반도체 투자 급증</title><link>https://ex.com/a1</link>
        <description>본문 &lt;b&gt;요약&lt;/b&gt;</description>
        <pubDate>Mon, 23 Jun 2026 09:00:00 +0900</pubDate><guid>g1</guid></item>
      <item><title>바이오 상장</title><link>https://ex.com/a2</link><description>x</description></item>
      <item><title></title><link>https://ex.com/empty</link></item>
    </channel></rss>"""
    rows = parse_feed_entries(rss, NewsFeed("한국경제", "economy", "u"), max_items=10)
    check("news_rss 유효 2건(빈제목 제외)", len(rows) == 2)
    check("news_rss source_type", rows[0].source_type == "DISCOURSE_NEWS_RSS")
    check("news_rss publisher 매핑", rows[0].author_or_publisher == "한국경제")
    check("news_rss content HTML 보존", rows[0].content_body and "요약" in rows[0].content_body)
    # 09:00 KST == 00:00 UTC (timegm 정확 변환)
    pub = rows[0].published_at
    check("news_rss published_at KST→UTC 정확", pub.day == 23 and pub.hour == 0)


def test_news_rss_body_enrichment() -> None:
    # 한국경제처럼 RSS 본문이 없거나 짧을 때 원문 페이지를 fetch 해 보강한다.
    from domain.master.hub.services.collectors.discourse.news_rss.news_rss_collector import (
        parse_feed_entries,
        extract_article_body,
        NewsFeed,
    )

    # extract_article_body — schema.org/일반 본문 셀렉터 우선, 네비 노이즈 제외
    html = (
        "<html><body><nav>전체메뉴 로그인</nav>"
        "<div class='article-body'>" + ("기사 본문 내용입니다. " * 20) + "</div>"
        "</body></html>"
    )
    body = extract_article_body(html)
    check("extract_article_body 본문만 추출", "기사 본문 내용" in body and "전체메뉴" not in body)
    check("extract_article_body itemprop 지원",
          "본문" in extract_article_body("<div itemprop='articleBody'>핵심 본문 텍스트</div>"))
    check("extract_article_body 빈 입력 빈 문자열", extract_article_body("") == "")

    feed = NewsFeed("한국경제", "economy", "u")

    # 본문 없는 항목(summary 0자) → fetch_article 로 보강
    rss_empty = ("<?xml version='1.0'?><rss version='2.0'><channel>"
                 "<item><title>제목만 있는 기사</title><link>https://ex.com/a1</link></item>"
                 "</channel></rss>")
    enriched = "원문 페이지에서 가져온 충분히 긴 본문 텍스트입니다. " * 10
    rows = parse_feed_entries(rss_empty, feed, fetch_article=lambda url: enriched)
    check("본문 없음 → fetch_article 보강", rows[0].content_body and "원문 페이지에서" in rows[0].content_body)

    # summary 충분 → fetch_article 미호출(회귀 방지)
    rss_full = ("<?xml version='1.0'?><rss version='2.0'><channel>"
                "<item><title>긴 요약</title><link>https://ex.com/a2</link>"
                "<description>" + ("충분히 긴 요약 본문 문장. " * 30) + "</description></item>"
                "</channel></rss>")
    called: list[str] = []
    parse_feed_entries(rss_full, feed, fetch_article=lambda url: called.append(url) or "x")
    check("요약 충분 → fetch 미호출", not called)

    # fetch 결과가 비거나 더 짧으면 기존 summary 유지
    rss_teaser = ("<?xml version='1.0'?><rss version='2.0'><channel>"
                  "<item><title>티저</title><link>https://ex.com/a3</link>"
                  "<description>짧은 티저</description></item></channel></rss>")
    rows3 = parse_feed_entries(rss_teaser, feed, fetch_article=lambda url: "")
    check("fetch 실패 → 기존 summary 유지", rows3[0].content_body == "짧은 티저")

    # 하위호환 — fetch_article 미주입 시 기존 동작(보강 없음)
    rows4 = parse_feed_entries(rss_empty, feed)
    check("fetch_article 미주입 → 기존 동작(본문 None)", rows4[0].content_body is None)


def test_gov_report() -> None:
    # 정부 보도자료 RSS(korea.kr) — 부처명은 제목 [부처] 접두에서 추출, description=전체 본문.
    from domain.master.hub.services.collectors.discourse.gov_report.gov_report_collector import (
        parse_gov_rss,
    )

    rss = (
        "<?xml version='1.0'?><rss version='2.0'><channel>"
        "<item><title>[외교부]제2차 서밋 참석</title>"
        "<link>https://www.korea.kr/x/1</link>"
        "<description>보도자료 &lt;b&gt;본문&lt;/b&gt; 전체 내용</description>"
        "<pubDate>Sat, 27 Jun 2026 02:02:37 GMT</pubDate></item>"
        "<item><title>부처없는 제목</title><link>https://www.korea.kr/x/2</link>"
        "<description>요약</description></item>"
        "</channel></rss>"
    )
    rows = parse_gov_rss(rss, max_items=10)
    check("gov_report 2건 파싱", len(rows) == 2)
    check("gov_report source_type", rows[0].source_type == "DISCOURSE_GOV_REPORT")
    check("gov_report 부처명 추출(외교부)", rows[0].author_or_publisher == "외교부")
    check("gov_report headline 대괄호 제거", rows[0].headline == "제2차 서밋 참석")
    check(
        "gov_report content HTML 제거",
        rows[0].content_body and "본문" in rows[0].content_body and "<b>" not in rows[0].content_body,
    )
    check("gov_report 부처 없으면 None", rows[1].author_or_publisher is None)


# ---------------------------------------------------------------------------
# Opportunity — K-Startup / 나라장터
# ---------------------------------------------------------------------------
def test_kstartup() -> None:
    from domain.master.hub.services.collectors.opportunity.kstartup.kstartup_collector import (
        extract_items,
        parse_item,
    )

    ks = json.dumps(
        {
            "data": [
                {
                    "pbanc_sn": "123",
                    "biz_pbanc_nm": "2026 예비창업패키지",
                    "pbanc_ctnt": "<p>지원내용</p>",
                    "sprv_inst": "창업진흥원",
                    "pbanc_rcpt_bgng_dt": "20260601",
                    "pbanc_rcpt_end_dt": "20260630",
                    "detl_pg_url": "https://k-startup.go.kr/x/123",
                },
                {"pbanc_sn": "124", "biz_pbanc_nm": "청년창업사관학교"},
            ]
        }
    )
    items = extract_items(ks)
    check("kstartup data[] 2건", len(items) == 2)
    d = parse_item(items[0])
    check("kstartup source_type", d.source_type == "OPP_KSTARTUP_GRANT")
    check("kstartup 본문 원형 보존", d.raw_content == "<p>지원내용</p>")
    check("kstartup deadline 파싱", d.deadline_at is not None and d.deadline_at.month == 6)
    check("kstartup URL fallback(pbanc_sn)", parse_item(items[1]).source_url.endswith("124"))


def test_narajangteo() -> None:
    from domain.master.hub.services.collectors.opportunity.narajangteo.narajangteo_collector import (
        extract_items,
        parse_item,
    )

    nj = json.dumps(
        {
            "response": {
                "body": {
                    "items": [
                        {
                            "bidNtceNo": "B1",
                            "bidNtceNm": "AI시스템 구축 용역",
                            "ntceInsttNm": "조달청",
                            "bidNtceDt": "2026-06-20 10:00",
                            "bidClseDt": "2026-06-30 18:00",
                            "asignBdgtAmt": "500000000",
                            "bidNtceDtlUrl": "https://g2b.go.kr/b1",
                        }
                    ]
                }
            }
        }
    )
    items = extract_items(nj)
    check("narajangteo items 1건", len(items) == 1)
    d = parse_item(items[0])
    check("narajangteo source_type", d.source_type == "OPP_G2B_BID")
    check("narajangteo 예산 메타", d.raw_metadata["budget_amount"] == "500000000")
    check("narajangteo deadline 파싱", d.deadline_at is not None)


# ---------------------------------------------------------------------------
# Company — 벤처기업명단
# ---------------------------------------------------------------------------
def test_venture_list() -> None:
    from domain.master.hub.services.collectors.company.venture_list.venture_list_collector import (
        parse_payload,
        _normalize_bizno,
    )

    payload = json.dumps(
        {
            "data": [
                {
                    "기업명": "에이아이바이오",
                    "대표자": "홍길동",
                    "벤처확인유형": "연구개발유형",
                    "지역": "서울",
                    "주소": "서울 강남구",
                    "업종": "소프트웨어 개발",
                    "사업자등록번호": "123-45-67890",
                    "확인일자": "2026-02-28",
                },
                {"회사명": "노바셀", "대표자명": "김철수", "벤처기업확인유형": "혁신성장유형", "소재지": "경기"},
                {"대표자": "무명"},
            ]
        }
    )
    rows = parse_payload(payload, file_version="2026-02")
    check("venture 유효 2건(기업명 없는 행 제외)", len(rows) == 2)
    check("venture 사업자번호 정규화", rows[0].business_number == "1234567890")
    check("venture 인증기관 고정", rows[0].certifying_agency == "중소벤처기업부")
    check("venture 확인일자 파싱", rows[0].certification_date == date(2026, 2, 28))
    check("venture 사업자번호 없음 None", rows[1].business_number is None)
    check("venture bizno 길이검증", _normalize_bizno("12-3") is None)


# ---------------------------------------------------------------------------
# Innovation — KIAT 기술은행 수요기술 (TECH_DEMAND_SIGNAL)
# ---------------------------------------------------------------------------
def test_kiat_tech_demand() -> None:
    from domain.master.hub.services.collectors.innovation.kiat.tech_demand_collector import (
        parse_needtech_items,
        item_to_dto,
    )

    xml = (
        "<response><header><resultCode>00</resultCode></header><body><items>"
        "<item><dmdtchNo>00000000001</dmdtchNo><dmdtchNm>콩 발효기술</dmdtchNm>"
        "<hopetchSumnsfeCn>새로운 콩 발효 종균</hopetchSumnsfeCn>"
        "<buyKindNm>기술매매,기술협력</buyKindNm><keyword>콩,발효,,,</keyword>"
        "<tchlgyPccndCn>협의</tchlgyPccndCn></item>"
        "<item><dmdtchNm></dmdtchNm></item>"
        "</items></body></response>"
    )
    items = parse_needtech_items(xml)
    check("kiat items 2개 파싱", len(items) == 2)
    dto = item_to_dto(items[0])
    check("kiat source_type", dto.source_type == "INNOVATION_KIAT_TECH_DEMAND")
    check("kiat title=수요기술명", dto.title == "콩 발효기술")
    check("kiat abstract=희망기술개요", dto.abstract_text == "새로운 콩 발효 종균")
    check("kiat data_role", dto.raw_metadata["data_role"] == "TECH_DEMAND_SIGNAL")
    check("kiat keyword 콤마정리", dto.raw_metadata["keyword"] == "콩,발효")
    check("kiat source_url(dmdtchNo)", dto.source_url.endswith("00000000001"))
    check("kiat 빈 수요기술명 제외", item_to_dto(items[1]) is None)


def main() -> int:
    for fn in (
        test_goyong24_recruit,
        test_saramin,
        test_news_rss,
        test_news_rss_body_enrichment,
        test_gov_report,
        test_kstartup,
        test_narajangteo,
        test_venture_list,
        test_kiat_tech_demand,
    ):
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
