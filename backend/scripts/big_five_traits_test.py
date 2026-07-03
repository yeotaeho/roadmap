# Big Five 점수→강점·중립 서술어(뚜렷한 축만·정서안정성 프레이밍) 순수 테스트

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.market_insight.hub.services.recommend_explain_service import TRAIT_MARGIN, big_five_traits

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
    check("TRAIT_MARGIN 12", TRAIT_MARGIN == 12)

    # 뚜렷한 축만 — C 높음·E 낮음, 나머지 중립(50)은 스킵
    t = big_five_traits({"scores": {"O": 50, "C": 85, "E": 30, "A": 55, "N": 50}})
    check("C 높음 서술", "체계적이고 성실함" in t, str(t))
    check("E 낮음 서술", "혼자 깊이 집중하는 걸 선호" in t, str(t))
    check("중립 O·A 스킵", all("개방" not in x and "협력" not in x and "독립" not in x for x in t), str(t))
    check("중립 N 스킵(안정성 문구 없음)", all("안정" not in x and "위험을 살핌" not in x for x in t), str(t))

    # 정서안정성 — N 낮음(안정성 높음) → 차분·안정
    t2 = big_five_traits({"scores": {"O": 50, "C": 50, "E": 50, "A": 50, "N": 20}})
    check("N 낮음 → 안정 서술", "차분하고 정서적으로 안정적" in t2, str(t2))
    # N 높음(안정성 낮음) → 신중 서술(병리 아님)
    t3 = big_five_traits({"scores": {"O": 50, "C": 50, "E": 50, "A": 50, "N": 80}})
    check("N 높음 → 신중 서술", "신중하게 위험을 살핌" in t3, str(t3))
    check("N 높음도 병리 단정 없음", all("불안" not in x and "예민함" not in x for x in t3), str(t3))

    # 낮은 쪽 서술어 커버(O·A)
    t4 = big_five_traits({"scores": {"O": 30, "C": 50, "E": 50, "A": 30, "N": 50}})
    check("O 낮음 서술", "익숙함·실용을 선호" in t4, str(t4))
    check("A 낮음 서술", "독립적이고 솔직함" in t4, str(t4))

    # 빈/누락 입력 → 빈 리스트
    check("None 빈 리스트", big_five_traits(None) == [])
    check("scores 없음 빈 리스트", big_five_traits({"raw": {}}) == [])

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
