"""혁신·사람 수요 컬렉터의 파싱과 DTO 변환을 무네트워크로 검증한다."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from domain.master.hub.services.collectors.innovation.arxiv.arxiv_papers_collector import (  # noqa: E402
    parse_arxiv_feed,
)
from domain.master.hub.services.collectors.innovation.github.github_trending_collector import (  # noqa: E402
    github_item_to_dto,
)
from domain.master.hub.services.collectors.people.hrdnet.hrdnet_training_collector import (  # noqa: E402
    aggregate_hrdnet_sector,
    parse_hrdnet_payload,
)
from domain.master.hub.services.collectors.people.worknet.worknet_job_info_collector import (  # noqa: E402
    parse_worknet_payload,
    worknet_item_to_dto,
)
from domain.master.hub.services.collectors.innovation.customs.customs_export_collector import (  # noqa: E402
    _is_total_row,
    _parse_amount,
    _parse_xml_items,
    _target_yearmonth,
)
from domain.master.hub.services.collectors.innovation.kistep.kistep_report_collector import (  # noqa: E402
    kistep_item_to_dto,
    parse_kistep_payload,
)
from domain.master.hub.services.collectors.people.careernet.careernet_collector import (  # noqa: E402
    _JOB_SPEC,
    _MAJOR_SPEC,
    careernet_item_to_dto,
    parse_careernet_payload,
)

_passed = 0
_failed = 0


def check(name: str, condition: bool) -> None:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"[OK] {name}")
    else:
        _failed += 1
        print(f"[FAIL] {name}")


def test_arxiv() -> None:
    xml = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2606.01234v1</id>
        <title>  Useful   Research </title>
        <summary>  Abstract text. </summary>
        <published>2026-06-07T01:02:03Z</published>
        <author><name>Alice</name></author>
        <author><name>Bob</name></author>
      </entry>
    </feed>"""
    rows = parse_arxiv_feed(xml, "AI_CS", "cs.AI")
    check("arxiv row count", len(rows) == 1)
    check("arxiv canonical url", rows[0].source_url == "https://arxiv.org/abs/2606.01234v1")
    check("arxiv whitespace normalized", rows[0].title == "Useful Research")
    check("arxiv metadata", (rows[0].raw_metadata or {}).get("category") == "cs.AI")


def test_github() -> None:
    dto = github_item_to_dto(
        {
            "full_name": "roadmap/example",
            "html_url": "https://github.com/roadmap/example",
            "owner": {"login": "roadmap"},
            "created_at": "2026-06-07T01:02:03Z",
            "stargazers_count": 120,
            "forks_count": 8,
            "language": "Python",
            "topics": ["education"],
            "description": "sample",
        },
        "EDUTECH",
        "20260601",
    )
    check("github dto exists", dto is not None)
    check("github weekly idempotency url", dto is not None and dto.source_url.endswith("?week=20260601"))
    check("github stars metadata", dto is not None and (dto.raw_metadata or {}).get("stars") == 120)


def test_worknet() -> None:
    payload = '{"jobs":{"job":[{"jobNm":"소프트웨어 개발자","totalCnt":"42"}]}}'
    items = parse_worknet_payload(payload)
    dto = worknet_item_to_dto(items[0], date(2026, 6, 8))
    check("worknet JSON parsed", len(items) == 1)
    check("worknet count absent", dto is not None and dto.search_volume_or_count is None)
    check("worknet reference date", dto is not None and dto.reference_date == date(2026, 6, 8))

    xml = "<root><jobList><jobNm>사회복지사</jobNm><totalCnt>7</totalCnt></jobList></root>"
    check("worknet XML parsed", parse_worknet_payload(xml)[0]["jobNm"] == "사회복지사")


def test_hrdnet() -> None:
    payload = (
        '{"returnJSON":{"srchList":['
        '{"trprNm":"AI 과정","courseMan":"1000000","yardMan":"20"},'
        '{"trprNm":"데이터 과정","courseMan":"2000000","yardMan":"30"}]}}'
    )
    items = parse_hrdnet_payload(payload)
    dto = aggregate_hrdnet_sector(items, "ICT_SW", "20", date(2026, 6, 8))
    check("hrdnet JSON parsed", len(items) == 2)
    check("hrdnet course count", dto.search_volume_or_count == 2)
    check("hrdnet cost sum", (dto.raw_metadata or {}).get("total_training_cost") == 3_000_000)
    check("hrdnet capacity sum", (dto.raw_metadata or {}).get("trainee_capacity") == 50)


def test_customs() -> None:
    # 실제 응답: 필드명은 hsCode(10자리), 총계행은 hsCode·statKor 모두 '-'
    xml = (
        '<response><header><resultCode>00</resultCode></header><body><items>'
        '<item><statKor>모노리식 집적회로</statKor><hsCode>8542311000</hsCode><expDlr>3000000</expDlr><impDlr>500000</impDlr><expWgt>120</expWgt></item>'
        '<item><statKor>디램</statKor><hsCode>8542321010</hsCode><expDlr>2000000</expDlr><impDlr>500000</impDlr><expWgt>80</expWgt></item>'
        '<item><statKor>-</statKor><hsCode>-</hsCode><expDlr>5000000</expDlr><impDlr>1000000</impDlr><expWgt>200</expWgt></item>'
        '</items></body></response>'
    )
    items, code = _parse_xml_items(xml)
    check("customs resultCode", code == "00")
    check("customs item count", len(items) == 3)
    detail = [it for it in items if not _is_total_row(it)]
    check("customs total row excluded ('-' sentinel)", len(detail) == 2)
    exp = sum(_parse_amount(it.get("expDlr")) for it in detail)
    check("customs detail expDlr sum (총계 2배 중복 제외)", exp == 5_000_000)
    check("customs yearmonth 2-month lag", _target_yearmonth(date(2026, 6, 9)) == "202604")
    check("customs yearmonth rollover", _target_yearmonth(date(2026, 1, 15)) == "202511")


def test_kistep() -> None:
    payload = (
        '{"response": {"result": ['
        '{"contentId": "12345", "subject": "2026 미래유망기술", "publishOrg": "KISTEP",'
        ' "contentsPurps": "유망기술 도출", "originUrl": "https://kistep.re.kr/r/12345",'
        ' "regDate": "2026-03-01"},'
        '{"contentId": "12346", "subject": "양자기술 동향", "publishOrg": "KISTEP", "originUrl": ""}'
        ']}}'
    )
    items = parse_kistep_payload(payload)
    check("kistep item count", len(items) == 2)
    d1 = kistep_item_to_dto(items[0], "미래예측")
    d2 = kistep_item_to_dto(items[1], "미래예측")
    check("kistep originUrl as source_url", d1 is not None and d1.source_url == "https://kistep.re.kr/r/12345")
    check("kistep fallback contentId url", d2 is not None and "contentId=12346" in d2.source_url)
    check("kistep data_role", d1 is not None and (d1.raw_metadata or {}).get("data_role") == "FUTURE_TECH_SIGNAL")

    # 실제 API 포맷: 본문이 JSON 문자열로 이중 인코딩 + result 배열 내부는
    # 따옴표·중괄호 없는 평면 key=value. 레코드 내부는 ", "(공백 有), 레코드 경계는
    # ","(공백 無). subject에 쉼표를 넣어 경계 슬라이스가 값을 오염시키지 않는지 검증.
    _F = (
        "resultCode", "resultMsg", "contentId", "policyType", "useYn",
        "brmCode", "brmTrans", "subject", "publishOrg", "contentsKor",
        "contentsPurps", "contentsCnclsn", "contentsRmk", "originUrl",
        "atchfileUrl", "atchfileNm", "viewCnt", "regDate", "deptMng",
    )

    def _rec(subject: str, content_id: str, dept: str) -> str:
        vals = {f: "null" for f in _F}
        vals["resultCode"] = "1"
        vals["contentId"] = content_id
        vals["subject"] = subject
        vals["publishOrg"] = "KISTEP"
        vals["originUrl"] = f"https://kistep.re.kr/r/{content_id}"
        vals["regDate"] = "2026-02-27 00:00:00"
        vals["deptMng"] = dept
        return ", ".join(f"{f}={vals[f]}" for f in _F)

    # 레코드 경계는 공백 없는 콤마(deptMng=홍길동,resultCode=1)
    flat = _rec("미래기술, 양자컴퓨팅 전망", "RES001", "홍길동")
    flat += "," + _rec("탄소중립 기술혁신, 2050 로드맵", "RES002", "김철수")
    inner = '{"response":{"result":[' + flat + '],"resultCode":"1","resultMsg":""}}'
    real_payload = json.dumps(inner, ensure_ascii=False)  # 본문 = JSON 문자열 (이중 인코딩)

    real_items = parse_kistep_payload(real_payload)
    check("kistep 평면포맷 레코드 수", len(real_items) == 2)
    check(
        "kistep 평면포맷 subject 쉼표 보존(경계 오염 없음)",
        len(real_items) == 2 and real_items[0].get("subject") == "미래기술, 양자컴퓨팅 전망",
    )
    check(
        "kistep 평면포맷 null→None",
        len(real_items) == 2 and real_items[0].get("contentsRmk") is None,
    )
    rd = [kistep_item_to_dto(it, "미래예측") for it in real_items]
    urls = [d.source_url for d in rd if d]
    check("kistep 평면포맷 source_url 유니크", len(set(urls)) == 2)


def test_careernet() -> None:
    # prospect는 API 미제공(항상 빈 값), possibility(발전가능성)가 실제 신호
    job_payload = (
        '{"dataSearch": {"content": ['
        '{"jobdicSeq": "100", "job": "데이터분석가", "possibility": "매우좋음", "salery": "5000"},'
        '{"jobdicSeq": "101", "job": "AI엔지니어", "possibility": "좋음"}'
        '], "totalCount": "2"}}'
    )
    items, total = parse_careernet_payload(job_payload)
    check("careernet job parsed", len(items) == 2 and total == 2)
    jd = careernet_item_to_dto(items[0], _JOB_SPEC, date(2026, 6, 9))
    check("careernet job name", jd is not None and jd.keyword_or_job == "데이터분석가")
    check("careernet possibility(발전가능성) preserved", jd is not None and (jd.raw_metadata or {}).get("possibility") == "매우좋음")
    check("careernet job source_type", jd is not None and jd.source_type == "PEOPLE_CAREERNET_JOB")

    major_payload = '{"dataSearch": {"content": [{"majorSeq": "50", "major": "컴퓨터공학과"}], "totalCount": "1"}}'
    mitems, _ = parse_careernet_payload(major_payload)
    md = careernet_item_to_dto(mitems[0], _MAJOR_SPEC, date(2026, 6, 9))
    check("careernet major source_type", md is not None and md.source_type == "PEOPLE_CAREERNET_MAJOR")


def main() -> int:
    test_arxiv()
    test_github()
    test_worknet()
    test_hrdnet()
    test_customs()
    test_kistep()
    test_careernet()
    print(f"PASS={_passed} FAIL={_failed}")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
