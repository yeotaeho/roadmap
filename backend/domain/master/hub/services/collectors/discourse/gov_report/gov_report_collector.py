# 정부 부처 보도자료(정책 담론, REPORT 계열) 수집 — 골격(차기 구현)

from __future__ import annotations

import logging
from dataclasses import dataclass

from domain.master.models.transfer.discourse_collect_dto import DiscourseCollectDto

logger = logging.getLogger(__name__)

_SOURCE_TYPE = "DISCOURSE_GOV_REPORT"


@dataclass(frozen=True)
class GovBoard:
    agency: str
    url: str


# 골격: 차기 태스크에서 부처별 게시판 BS4 파서를 추가한다.
# economic 계열의 `_msit_common.py` 게시판 파서를 재사용 후보로 둔다.
_BOARDS: tuple[GovBoard, ...] = (
    GovBoard("한국은행", "https://www.bok.or.kr/portal/bbs/B0000338/list.do?menuNo=200690"),
    GovBoard("산업통상자원부", "https://www.motie.go.kr/kor/article/ATCL3f49a5a8c"),
)


class GovReportCollector:
    """정부 보도자료 담론 수집 — 현재는 골격(미구현). 항상 빈 결과를 안전 반환."""

    async def collect(self, *, max_items: int = 50) -> tuple[list[DiscourseCollectDto], dict[str, int]]:
        logger.info("[gov-report] 골격 수집기 — 미구현. boards=%s", [b.agency for b in _BOARDS])
        return [], {"boards_total": len(_BOARDS), "fetched": 0, "not_implemented": 1}


__all__ = ["GovReportCollector", "GovBoard"]
