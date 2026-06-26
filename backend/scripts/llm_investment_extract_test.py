# 투자 금액 추출 파서(_parse_investment) 무네트워크 검증 — 환각 방지·abstain

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm.client import _parse_investment  # noqa: E402

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


def test_valid_krw() -> None:
    raw = json.dumps({"amount_krw": 10000000000, "currency": "KRW", "series": "Series A", "company": "토스"})
    out = _parse_investment(raw)
    check("KRW 금액 추출", out["amount_krw"] == 10000000000.0)
    check("통화 보존", out["currency"] == "KRW")
    check("단계 보존", out["series"] == "Series A")
    check("기업 보존", out["company"] == "토스")


def test_currency_default() -> None:
    out = _parse_investment(json.dumps({"amount_krw": 5000000000, "company": "A"}))
    check("통화 누락 시 KRW 기본", out["currency"] == "KRW")
    check("단계 누락 시 None", out["series"] is None)


def test_abstain_no_amount() -> None:
    # 외화만 있고 원화 환산 없음 → amount_krw null → abstain.
    check("amount null → abstain", _parse_investment(json.dumps({"amount_krw": None, "currency": "USD"}))["amount_krw"] is None)
    check("amount 0 → abstain", _parse_investment(json.dumps({"amount_krw": 0}))["amount_krw"] is None)
    check("amount 음수 → abstain", _parse_investment(json.dumps({"amount_krw": -100}))["amount_krw"] is None)
    check("amount 문자열 비수치 → abstain", _parse_investment(json.dumps({"amount_krw": "약간"}))["amount_krw"] is None)


def test_bad_input() -> None:
    check("bad json → abstain", _parse_investment("not json")["amount_krw"] is None)
    check("None → abstain", _parse_investment(None)["amount_krw"] is None)
    check("배열 → abstain", _parse_investment(json.dumps([1, 2]))["amount_krw"] is None)


def main() -> int:
    for fn in (test_valid_krw, test_currency_default, test_abstain_no_amount, test_bad_input):
        fn()
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
