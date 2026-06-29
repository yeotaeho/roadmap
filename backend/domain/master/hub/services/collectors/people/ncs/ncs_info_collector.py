# NCS 국가직무능력표준 관련 정보 OpenAPI (data.go.kr 15063879) 기반 보충 수집

from __future__ import annotations

import logging

from domain.master.models.transfer.ncs_master_dto import NcsMasterDto

logger = logging.getLogger(__name__)

# TODO: data.go.kr 15063879 API 엔드포인트 및 응답 필드명 live 검증 필요.
# 이 수집기의 목적:
#   - NcsStandardCollector 가 수집한 능력단위(L5) 및 능력단위요소(L6)에 대한
#     보충 정의(상세 수행준거·지식·기술·태도·자격 연계) 수집
#   - NCS 코드를 키로 기존 레코드를 UPSERT(description, performance_criteria,
#     knowledge_skills, linked_qualification 갱신)
# API 특성:
#   - 정적 온톨로지 → 전수 조회 후 ncs_code 기준 UPSERT
#   - 예상 응답 구조: data.go.kr 표준 XML/JSON wrapping
# 구현 준비 체크리스트:
#   1. API 활성화 대기 (승인 후 1~2시간 소요)
#   2. 실제 오퍼레이션 목록 확인 (마이페이지 → 활용신청 상세)
#   3. 샘플 응답 1건으로 필드명 매핑 확정
#   4. NotImplementedError 제거 후 _fetch_list + DTO 빌드 로직 구현


class NcsInfoCollector:
    """NCS 관련 정보 OpenAPI (data.go.kr 15063879) 보충 수집기 (스켈레톤).

    능력단위 정의·자격 연계 등 보충 정보를 수집해 NCS 마스터를 강화한다.
    live API 검증 완료 후 구현 예정.
    """

    def __init__(self, service_key: str) -> None:
        if not service_key or not service_key.strip():
            raise ValueError(
                "NCS Info API 키가 비어 있습니다. NCS_INFO_SERVICE_KEY 를 설정하세요."
            )
        self._service_key = service_key.strip()

    async def collect(self) -> tuple[list[NcsMasterDto], dict[str, int]]:
        """NCS 관련 정보 보충 수집.

        TODO: 15063879 API 응답 필드 매핑 미완성 — live 검증 후 구현.
        """
        # TODO: 아래 구현이 완료되면 NotImplementedError 를 제거하고
        #       _fetch_list → _extract_items → DTO 빌드 → (dtos, stats) 반환.
        raise NotImplementedError(
            "15063879 API 응답 필드 매핑 미완성 — live 검증 후 구현"
        )


__all__ = ["NcsInfoCollector"]
