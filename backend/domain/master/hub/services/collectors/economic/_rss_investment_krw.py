"""RSS·뉴스 본문에서 투자 규모(원화) 정수 추출.

한국어 보도에서 자주 나오는 ``N억``, ``N조``, ``N만 원`` 패턴을 우선한다.
여러 금액이 나오면 **가장 큰 값**을 택한다(헤드라인 규모가 보통 최대인 경우가 많음).
"""

from __future__ import annotations

import re
from typing import Final

# 숫자 그룹: 쉼표 포함 정수
_NUM: Final[str] = r"(\d{1,4}(?:,\d{3})+|\d+)"

_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = (
    # 1조 5000억 → "조" 단독 매칭 후 "억" 매칭으로도 잡힐 수 있음 → 큰 단위 먼저 스캔
    (re.compile(_NUM + r"\s*조(?:\s*원)?"), 1_000_000_000_000),
    (re.compile(_NUM + r"\s*억(?:\s*원)?"), 100_000_000),
    (re.compile(_NUM + r"\s*만\s*원"), 10_000),
    (re.compile(_NUM + r"\s*만원"), 10_000),
    (re.compile(_NUM + r"\s*천\s*원"), 1_000),
    (re.compile(_NUM + r"\s*천원"), 1_000),
)


def extract_investment_amount_krw(text: str | None) -> int | None:
    """본문·제목 합친 문자열에서 원화 추정액(정수) 반환. 없으면 None."""
    if not text or not str(text).strip():
        return None
    s = str(text)
    best: int | None = None
    for pat, mult in _PATTERNS:
        for m in pat.finditer(s):
            raw = m.group(1).replace(",", "").strip()
            if not raw.isdigit():
                continue
            try:
                val = int(raw) * mult
            except (ValueError, OverflowError):
                continue
            if val <= 0:
                continue
            if best is None or val > best:
                best = val
    return best
