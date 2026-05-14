"""SMES Collector 4대 함정 방어 로직 단위 테스트 (실제 API 호출 X).

가짜 XML/JSON 응답을 입력해 _extract_items / _parse_item / fallback 동작을 검증한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from domain.master.hub.services.collectors.opportunity.smes_collector import (
    SmesOpenAPICollector,
)


def line(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def test_trap1_single_item_dict() -> None:
    """함정 1: item 이 단일 dict 일 때 list 로 정규화되는가."""
    line("[함정 1] 단일 item 응답 (Dict → List 정규화)")
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>00</resultCode><resultMsg>NORMAL</resultMsg></header>
  <body>
    <items>
      <item>
        <pblancId>20260001</pblancId>
        <pblancNm>2026년 예비창업패키지</pblancNm>
        <insttNm>중소벤처기업진흥공단</insttNm>
        <regDt>20260428</regDt>
        <bltnBgn>20260501</bltnBgn>
        <rcptEnd>20260525</rcptEnd>
        <pblancUrl>https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId=20260001</pblancUrl>
        <pblancCn><![CDATA[<p><b>지원자격</b>: 예비창업자</p><table border="1"><tr><td>최대 1억원</td></tr></table>]]></pblancCn>
      </item>
    </items>
  </body>
</response>"""
    collector = SmesOpenAPICollector("dummy-key")
    items = collector._extract_items(xml)
    print(f"  추출된 items 개수: {len(items)} (기대: 1)")
    assert len(items) == 1, f"단일 item 정규화 실패: {len(items)}개"
    print(f"  pblancId: {items[0].get('pblancId')}")
    print("  [PASS]")


def test_trap1_multiple_items() -> None:
    """함정 1: item 이 복수 list 일 때 그대로 list 유지되는가."""
    line("[함정 1] 복수 item 응답 (List 유지)")
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>00</resultCode></header>
  <body>
    <items>
      <item><pblancId>A</pblancId><pblancNm>창업지원</pblancNm></item>
      <item><pblancId>B</pblancId><pblancNm>R&amp;D 기술개발</pblancNm></item>
      <item><pblancId>C</pblancId><pblancNm>수출 지원</pblancNm></item>
    </items>
  </body>
</response>"""
    collector = SmesOpenAPICollector("dummy-key")
    items = collector._extract_items(xml)
    print(f"  추출된 items 개수: {len(items)} (기대: 3)")
    assert len(items) == 3
    print("  [PASS]")


def test_trap1_empty_response() -> None:
    """함정 1: items 가 비어있을 때 빈 리스트 반환."""
    line("[함정 1] 빈 응답 / 0건 응답")
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>00</resultCode></header>
  <body><items></items><totalCount>0</totalCount></body>
</response>"""
    collector = SmesOpenAPICollector("dummy-key")
    items = collector._extract_items(xml)
    print(f"  추출된 items 개수: {len(items)} (기대: 0)")
    assert len(items) == 0
    print("  [PASS]")


def test_trap2_published_at_priority() -> None:
    """함정 2: published_at 이 regDt 우선, 모집시작일은 사용 안함."""
    line("[함정 2] published_at 우선순위 (regDt > bltnBgn, 모집시작일은 metadata로)")
    collector = SmesOpenAPICollector("dummy-key")
    item = {
        "pblancId": "X1",
        "pblancNm": "테스트 공고",
        "regDt": "20260428",  # 등록일 (이게 published_at 이 되어야 함)
        "bltnBgn": "20260501",  # 게시 시작일 (2순위)
        "rcritStrtDt": "20260510",  # 모집 시작일 (사용 X)
        "rcptEnd": "20260525",
        "pblancUrl": "https://www.bizinfo.go.kr/test",
    }
    dto = collector._parse_item(item)
    print(f"  published_at (regDt 기반): {dto.published_at}")
    print(f"  deadline_at (rcptEnd 기반): {dto.deadline_at}")
    print(
        f"  application_period (모집 일정): {dto.raw_metadata['application_period']}"
    )
    assert dto.published_at is not None
    assert str(dto.published_at.date()) == "2026-04-28", "regDt 가 우선되지 않음"
    assert dto.raw_metadata.get("published_at_source") == "regDt"
    assert (
        dto.raw_metadata["application_period"]["start"] == "20260510"
    ), "rcritStrtDt 가 metadata 로 이동되지 않음"
    print("  [PASS]")


def test_trap2_fallback_to_bltnBgn() -> None:
    """함정 2: regDt 없을 때 bltnBgn 으로 fallback."""
    line("[함정 2] regDt 없으면 bltnBgn 으로 Fallback")
    collector = SmesOpenAPICollector("dummy-key")
    item = {
        "pblancId": "X2",
        "pblancNm": "Fallback 테스트",
        # regDt 없음
        "bltnBgn": "20260501",
        "pblancUrl": "https://www.bizinfo.go.kr/test2",
    }
    dto = collector._parse_item(item)
    print(f"  published_at (bltnBgn 으로 fallback): {dto.published_at}")
    assert str(dto.published_at.date()) == "2026-05-01"
    assert dto.raw_metadata.get("published_at_source") == "bltnBgn"
    print("  [PASS]")


def test_trap3_html_content_preserved() -> None:
    """함정 3: pblancCn HTML/CDATA 원형 그대로 보존."""
    line("[함정 3] pblancCn HTML 원형 보존 (정제 X)")
    collector = SmesOpenAPICollector("dummy-key")
    html_content = '<p><b>지원자격</b>: 예비창업자</p><table border="1"><tr><td>최대 1억원</td></tr></table>'
    item = {
        "pblancId": "X3",
        "pblancNm": "HTML 보존 테스트",
        "pblancCn": html_content,
        "pblancUrl": "https://www.bizinfo.go.kr/test3",
    }
    dto = collector._parse_item(item)
    print(f"  raw_content 길이: {len(dto.raw_content)}")
    print(f"  raw_content 일부: {dto.raw_content[:80]}...")
    assert "<table" in dto.raw_content, "HTML 태그가 제거됨 (Bronze 원칙 위반!)"
    assert "<b>" in dto.raw_content
    print("  [PASS]")


def test_trap4_source_url_fallback_no_url() -> None:
    """함정 4: pblancUrl 이 없을 때 공고 ID 로 URL 조합."""
    line("[함정 4] pblancUrl 누락 → bizinfo 상세 페이지 URL 조합")
    collector = SmesOpenAPICollector("dummy-key")
    item = {
        "pblancId": "12345678",
        "pblancNm": "URL 없는 공고",
        # pblancUrl 누락
    }
    dto = collector._parse_item(item)
    print(f"  source_url: {dto.source_url}")
    assert (
        dto.source_url
        == "https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId=12345678"
    )
    print("  [PASS]")


def test_trap4_source_url_fallback_internal_url() -> None:
    """함정 4: 내부 관리자용 URL 이 와도 정상 URL 로 교체."""
    line("[함정 4] 내부 admin URL → 안전한 URL 로 Fallback")
    collector = SmesOpenAPICollector("dummy-key")
    item = {
        "pblancId": "98765",
        "pblancNm": "내부 URL 공고",
        "pblancUrl": "https://admin.internal.local/bbs/view/98765",  # 잘못된 URL
    }
    dto = collector._parse_item(item)
    print(f"  source_url (admin URL 교체됨): {dto.source_url}")
    assert "admin.internal" not in dto.source_url
    assert "bizinfo.go.kr" in dto.source_url
    print("  [PASS]")


def test_trap4_source_url_fallback_no_id() -> None:
    """함정 4: pblancUrl 도 pblancId 도 없을 때 기업마당 메인."""
    line("[함정 4] URL/ID 모두 없음 → 기업마당 메인 URL")
    collector = SmesOpenAPICollector("dummy-key")
    item = {"pblancNm": "URL ID 둘 다 없는 공고"}
    dto = collector._parse_item(item)
    print(f"  source_url (메인 fallback): {dto.source_url}")
    assert dto.source_url == "https://www.bizinfo.go.kr"
    print("  [PASS]")


def test_option_b_v2_realistic_xml() -> None:
    """옵션 B: v2 응답(등록일 없음)에서 published_at = applicationStartDate + 출처 메타."""
    line("[옵션 B] mssBizService_v2 실제 XML 스니펫")
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>00</resultCode><resultMsg>NORMAL_CODE</resultMsg></header>
  <body>
    <numOfRows>1</numOfRows><pageNo>1</pageNo><totalCount>2103</totalCount>
    <items>
      <item>
        <itemId>1068107</itemId>
        <title><![CDATA[「2026년 브랜드 소상공인 점프업」 소상공인 모집공고]]></title>
        <dataContents><![CDATA[<div id="hwpEditorBoardContent">본문</div>]]></dataContents>
        <applicationStartDate>2026-05-11</applicationStartDate>
        <applicationEndDate>2026-05-29</applicationEndDate>
        <writerName>김태연</writerName>
        <writerPosition>디지털소상공인과</writerPosition>
        <writerPhone>044-204-7876</writerPhone>
        <writerEmail>xodus0923@mail.go.kr</writerEmail>
        <viewUrl><![CDATA[https://www.mss.go.kr/site/smba/ex/bbs/View.do?cbIdx=310&bcIdx=1068107]]></viewUrl>
        <fileName><![CDATA[a.hwpx]]></fileName>
        <fileUrl><![CDATA[https://www.mss.go.kr/a.hwpx]]></fileUrl>
        <fileName><![CDATA[b.pdf]]></fileName>
        <fileUrl><![CDATA[https://www.mss.go.kr/b.pdf]]></fileUrl>
      </item>
    </items>
  </body>
</response>"""
    collector = SmesOpenAPICollector("dummy-key")
    items = collector._extract_items(xml)
    assert len(items) == 1
    dto = collector._parse_item(items[0])
    assert dto.source_url.startswith("https://www.mss.go.kr/")
    assert str(dto.published_at.date()) == "2026-05-11"
    assert dto.raw_metadata.get("published_at_source") == "applicationStartDate"
    assert str(dto.deadline_at.date()) == "2026-05-29"
    assert dto.host_name == "중소벤처기업부 디지털소상공인과"
    assert dto.raw_metadata.get("contact", {}).get("name") == "김태연"
    assert len(dto.raw_metadata.get("attachments", [])) == 2
    print(f"  source_url: {dto.source_url[:60]}...")
    print(f"  published_at: {dto.published_at} (source={dto.raw_metadata.get('published_at_source')})")
    print(f"  host_name: {dto.host_name}")
    print("  [PASS]")


def test_mss_view_url_accepted() -> None:
    """viewUrl 이 mss.go.kr 이면 그대로 source_url 로 사용."""
    line("[함정 4] mss.go.kr viewUrl 정상 수용")
    collector = SmesOpenAPICollector("dummy-key")
    item = {
        "itemId": "1",
        "title": "테스트",
        "viewUrl": "https://www.mss.go.kr/site/smba/ex/bbs/View.do?cbIdx=1&bcIdx=2",
        "applicationStartDate": "2026-01-01",
    }
    dto = collector._parse_item(item)
    assert dto.source_url.startswith("https://www.mss.go.kr/")
    print("  [PASS]")


def test_classification() -> None:
    """source_type 분류가 키워드 기반으로 동작."""
    line("[BONUS] source_type 자동 분류")
    from domain.master.hub.services.collectors.opportunity.smes_collector import (
        _classify_source_type,
    )

    cases = [
        ("2026년 예비창업패키지", "SMES_STARTUP"),
        ("AI 기술개발 R&D 지원사업", "SMES_RND"),
        ("중소기업 글로벌 수출지원", "SMES_EXPORT"),
        ("스케일업 도약 프로그램", "SMES_SCALE_UP"),
        ("기타 일반 지원", "SMES_GRANT"),
    ]
    for title, expected in cases:
        result = _classify_source_type(title)
        flag = "OK" if result == expected else "FAIL"
        print(f"  [{flag}] '{title}' → {result} (기대: {expected})")
        assert result == expected
    print("  [PASS]")


if __name__ == "__main__":
    test_trap1_single_item_dict()
    test_trap1_multiple_items()
    test_trap1_empty_response()
    test_trap2_published_at_priority()
    test_trap2_fallback_to_bltnBgn()
    test_trap3_html_content_preserved()
    test_trap4_source_url_fallback_no_url()
    test_trap4_source_url_fallback_internal_url()
    test_trap4_source_url_fallback_no_id()
    test_option_b_v2_realistic_xml()
    test_mss_view_url_accepted()
    test_classification()
    print("\n" + "=" * 80)
    print("[SUCCESS] 모든 단위 테스트 통과! 4대 함정 방어 정상 동작.")
    print("=" * 80)
