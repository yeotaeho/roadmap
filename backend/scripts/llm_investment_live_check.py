# 투자 금액 추출 LLM 실 호출 검증(실데이터·실API) — 배포 전 추출 품질 점검용

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config.settings import get_settings  # noqa: E402
from core.llm.client import LlmClient  # noqa: E402

# (헤드라인, 기대 동작) — amount=금액 잡혀야, abstain=금액 None 이어야.
_CASES: list[tuple[str, str]] = [
    ("토스, 시리즈G 1조원 규모 투자 유치", "amount"),
    ("당근마켓, 1789억원 규모 시리즈D 투자 유치 완료", "amount"),
    ("AI 헬스케어 스타트업 ○○, 50억원 시드 투자 유치", "amount"),
    ("△△로보틱스, 100억원 프리A 라운드 마무리", "amount"),
    ("□□테크, 미국서 $20M 시리즈B 유치(원화 환산 미공개)", "abstain(외화전용)"),
    ("정부, AI 분야 R&D 예산 대폭 확대 발표", "abstain(투자아님)"),
    ("◇◇ 부트캠프 5기 수강생 모집 시작", "abstain(공고)"),
    ("◎◎바이오, 시리즈C 300억원 투자 유치", "amount"),
]


async def main() -> int:
    settings = get_settings()
    if not settings.openai_api_key:
        print("OPENAI_API_KEY 미설정 — 실 호출 불가. .env 설정 후 재실행.")
        return 1
    llm = LlmClient(api_key=settings.openai_api_key, model=settings.llm_classify_model)

    print(f"모델: {settings.llm_classify_model}\n")
    ok = 0
    for headline, expect in _CASES:
        try:
            r = await llm.extract_investment(headline)
        except Exception as e:  # 네트워크/인증/쿼터 등
            print(f"[ERROR] 실 호출 실패: {type(e).__name__}: {e}")
            print("→ 네트워크/키/쿼터 확인 필요. 추출 로직(파서)은 단위 테스트로 검증됨.")
            return 2
        amt = r["amount_krw"]
        got = "amount" if amt is not None else "abstain"
        want = "amount" if expect == "amount" else "abstain"
        mark = "OK " if got == want else "CHK"
        amt_str = f"{int(amt):,}원" if amt is not None else "—"
        print(f"[{mark}] 기대={expect:18s} | 금액={amt_str:>18s} | series={r['series']} | company={r['company']}")
        print(f"      └ {headline}")
        if got == want:
            ok += 1
    print(f"\n기대 일치: {ok}/{len(_CASES)} (CHK 는 사람이 눈으로 확인)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
