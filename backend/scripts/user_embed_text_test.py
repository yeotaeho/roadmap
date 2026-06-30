# 사용자 임베딩 텍스트 헬퍼(성향·스펙 직렬화) 무네트워크 결정론 테스트

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.market_insight.hub.services.user_embed_text import (  # noqa: E402
    build_user_embed_text,
    disposition_spec_terms,
)

PASS = 0
FAIL = 0


def check(name: str, cond: bool, extra: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} {extra}")


def run() -> int:
    # 하위호환: 직무+관심만 -> 기존 _user_text 와 동일 출력
    check("직무+관심 결합", build_user_embed_text("데이터 분석가", ["AI", "핀테크"]) == "데이터 분석가 AI 핀테크")
    check("관심만", build_user_embed_text(None, ["AI"]) == "AI")
    check("빈 입력 -> 플레이스홀더", build_user_embed_text(None, []) == "_")
    check("비-리스트 관심 무시", build_user_embed_text("기획자", None) == "기획자")

    # 성향 라벨 매핑
    terms = disposition_spec_terms(
        work_style="challenge", company_size_pref="startup",
        work_type_pref="hybrid", work_values=["growth", "autonomy"],
    )
    check("work_style 라벨", "도전 지향" in terms, str(terms))
    check("company_size 라벨", "스타트업" in terms)
    check("work_type 라벨", "하이브리드 근무" in terms)
    check("work_values 라벨 2개", "성장" in terms and "자율성" in terms)
    check("미지의 enum 무시", disposition_spec_terms(work_style="bogus") == [])

    # 스펙 추출
    spec = disposition_spec_terms(
        skills=[{"name": "Python", "level": "중급"}, {"name": "SQL"}],
        certifications=[{"name": "정보처리기사", "issuer": "큐넷"}],
        languages=[{"language": "영어", "test": "TOEIC"}],
        projects=[{"title": "추천엔진", "tech_stack": ["FastAPI", "pgvector"]}],
    )
    check("skill 이름", "Python" in spec and "SQL" in spec)
    check("자격증 이름", "정보처리기사" in spec)
    check("어학 언어", "영어" in spec)
    check("프로젝트 제목", "추천엔진" in spec)
    check("tech_stack 전개", "FastAPI" in spec and "pgvector" in spec)

    # 통합 직렬화
    full = build_user_embed_text(
        "백엔드", ["AI"], work_style="challenge", work_values=["growth"],
        skills=[{"name": "Python"}],
    )
    check("통합 텍스트 포함", all(w in full for w in ("백엔드", "AI", "도전 지향", "성장", "Python")), full)
    check("None/빈 dict 견고", disposition_spec_terms(skills=[None, {}, {"name": ""}]) == [])

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
