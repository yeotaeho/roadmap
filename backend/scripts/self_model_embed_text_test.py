# 자기모델 직렬화(RIASEC 라벨·서사·근거·1000자 캡) 순수 테스트.

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.market_insight.hub.services.user_embed_text import (
    MAX_EMBED_TEXT_CHARS,
    RIASEC_LABEL,
    build_user_embed_text,
    self_model_terms,
)

PASS = 0
FAIL = 0


def check(n: str, c: bool, e: str = "") -> None:
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"[PASS] {n}")
    else:
        FAIL += 1
        print(f"[FAIL] {n} {e}")


def run() -> int:
    # RIASEC 라벨 — 유효 코드만 한국어 라벨로, 닫힌집합 외 무시
    terms = self_model_terms(riasec={"top_codes": ["I", "A", "X"]})
    check("RIASEC 라벨 변환", terms == [RIASEC_LABEL["I"], RIASEC_LABEL["A"]], str(terms))

    # 비dict riasec·비list top_codes 는 무시
    check("riasec 비정형 무시", self_model_terms(riasec="I") == [], str(self_model_terms(riasec="I")))
    check("top_codes 비정형 무시", self_model_terms(riasec={"top_codes": "I"}) == [])

    # narrative·근거 이어붙임 순서(RIASEC → 서사 → 근거)
    terms = self_model_terms(
        riasec={"top_codes": ["S"]},
        narrative_summary=" 성장을 중시함 ",
        evidence_contents=["발표를 좋아함", "", None],
    )
    check("순서·공백정리", terms == [RIASEC_LABEL["S"], "성장을 중시함", "발표를 좋아함"], str(terms))

    # build_user_embed_text — 기존 프로필 파츠 뒤에 자기모델 파츠
    t = build_user_embed_text(
        target_job="데이터 분석가",
        interest_keywords=["AI"],
        riasec={"top_codes": ["I"]},
        narrative_summary="탐구 지향",
        evidence_contents=["문제 해결을 좋아함"],
    )
    check("직렬화 결합", t == f"데이터 분석가 AI {RIASEC_LABEL['I']} 탐구 지향 문제 해결을 좋아함", t)

    # 기존 호출(자기모델 인자 없음) 하위호환
    check("하위호환", build_user_embed_text(target_job="개발자") == "개발자")

    # 1000자 캡 — 캡 결과가 결정론(해시 안정 전제)
    long_evidence = ["가" * 300, "나" * 300, "다" * 300, "라" * 300]
    t = build_user_embed_text(target_job="개발자", evidence_contents=long_evidence)
    check("1000자 캡", len(t) <= MAX_EMBED_TEXT_CHARS, str(len(t)))
    t2 = build_user_embed_text(target_job="개발자", evidence_contents=long_evidence)
    check("캡 결정론", t == t2)

    # 전부 빈 입력은 기존과 동일하게 "_"
    check("빈 입력 언더스코어", build_user_embed_text() == "_")

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
