# Silver — 투자 뉴스 헤드라인에서 투자 금액(자본 흐름 강도)을 LLM 추출해 적재하는 서비스

from __future__ import annotations

import hashlib
import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.llm.client import LlmClient
from domain.market_insight.hub.repositories.investment_repository import InvestmentRepository

logger = logging.getLogger(__name__)

# v2 — 제목만으로는 다이제스트류 금액 추출이 불가해(성공 1/92) 본문을 입력에 포함.
PROMPT_VERSION = "v2"
# DART CB·M&A 보강 경로 — LLM 없이 raw 금액 + 기업개황 API 업종(KSIC)→섹터 매핑.
DART_PROMPT_VERSION = "dart-v1"
ACTIVE_WINDOW_DAYS = 90
DEFAULT_LIMIT = 200
MAX_INPUT_CHARS = 1500
# LLM 추출 중간 적재·커밋 주기 — pool_recycle(5분) 초과 방지.
REFINE_CHUNK = 25

_DART_COMPANY_API = "https://opendart.fss.or.kr/api/company.json"

# KSIC(induty_code) prefix → sectors.slug. 확실한 산업만 매핑(강제 매핑 = 날조 금지, 미매핑은 무귀속).
# 긴 prefix 우선 매칭. 예: 582(SW 출판)→ai-data, 551(숙박)은 12섹터 밖이라 무귀속.
_KSIC_SECTOR_PREFIX: dict[str, str] = {
    # 정보통신·SW·데이터
    "582": "ai-data",  # 소프트웨어 개발·공급
    "62": "ai-data",   # 컴퓨터 프로그래밍·시스템 통합
    "63": "ai-data",   # 정보서비스(포털·데이터)
    # 전자·반도체
    "26": "semiconductor",  # 전자부품·컴퓨터·영상·음향·통신장비
    # 바이오·헬스
    "21": "bio-health",   # 의료용 물질·의약품
    "271": "bio-health",  # 의료용 기기
    "86": "bio-health",   # 보건업
    # 모빌리티
    "30": "mobility",  # 자동차·트레일러
    "31": "mobility",  # 기타 운송장비
    # 핀테크·금융
    "64": "fintech", "65": "fintech", "66": "fintech",
    # 식품·농업
    "01": "food-agri", "10": "food-agri", "11": "food-agri",
    # 뷰티·패션
    "2042": "beauty-fashion",  # 세제·화장품
    "13": "beauty-fashion", "14": "beauty-fashion", "15": "beauty-fashion",
    # 에너지·기후 — 35 는 가스·증기 공급 포함(에너지 인프라 전반을 이 섹터로 보는 의도적 범위).
    "35": "energy-climate", "38": "energy-climate", "39": "energy-climate",
    # 물류·유통
    "49": "logistics", "50": "logistics", "51": "logistics", "52": "logistics",
    # 콘텐츠
    "59": "content-creator", "60": "content-creator", "90": "content-creator",
    # 교육
    "85": "edutech",
    # 사회서비스·복지
    "87": "social-service",
}


def map_ksic_to_sector(induty_code: str | None) -> str | None:
    """KSIC 업종코드를 12섹터 슬러그로. 미매핑 산업은 None(무귀속)."""
    code = (induty_code or "").strip()
    if not code:
        return None
    for length in (5, 4, 3, 2):
        slug = _KSIC_SECTOR_PREFIX.get(code[:length])
        if slug:
            return slug
    return None


class InvestmentFlowRefineService:
    """투자/펀딩/M&A 뉴스 → 금액 추출(refined_investment_flows) 적재. 멱등."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = InvestmentRepository(session)
        settings = get_settings()
        self._model = settings.llm_classify_model
        self._llm = LlmClient(api_key=settings.openai_api_key, model=self._model)

    async def refine_and_serve(
        self, window_days: int = ACTIVE_WINDOW_DAYS, limit: int = DEFAULT_LIMIT
    ) -> dict:
        """미처리 투자뉴스에서 금액을 추출·적재한다. 멱등.

        반환: {"scanned", "extracted"} (extracted = 금액이 잡힌 행 수).
        """
        rows = await self.repo.fetch_unprocessed(PROMPT_VERSION, window_days, limit)
        extracted = 0
        for i, r in enumerate(rows, start=1):
            base = (r.title or "").strip()
            if r.company_hint:
                base = f"{base} ({r.company_hint})"
            body = (r.body or "").strip()
            if body:
                base = f"{base}\n{body}"
            input_text = base[:MAX_INPUT_CHARS]
            result = await self._llm.extract_investment(input_text)
            await self.repo.upsert_silver(
                {
                    "sector_slug": None,
                    "amount_krw": result["amount_krw"],
                    "currency": result["currency"],
                    "series": result["series"],
                    "company": result["company"] or (r.company_hint or None),
                    "ref_date": r.ref_date,
                    "raw_id": r.raw_id,
                    "model_name": self._model,
                    "prompt_version": PROMPT_VERSION,
                    "input_hash": hashlib.sha256(input_text.encode("utf-8")).hexdigest(),
                }
            )
            if result["amount_krw"] is not None:
                extracted += 1
            if i % REFINE_CHUNK == 0:
                await self.session.commit()
        await self.session.commit()
        dart = await self.enrich_dart_flows()
        return {"scanned": len(rows), "extracted": extracted, **dart}

    async def enrich_dart_flows(self, limit: int = DEFAULT_LIMIT) -> dict:
        """DART CB·M&A(금액 직접 기입) 행을 기업개황 API 업종으로 섹터 귀속해 적재. 멱등.

        반환: {"dart_scanned", "dart_enriched"} (enriched = 섹터가 잡힌 행 수).
        DART 키가 없으면 스킵. API 오류 행은 미저장 → 다음 실행에서 재시도.
        """
        key = (get_settings().dart_api_key or "").strip()
        if not key:
            return {"dart_scanned": 0, "dart_enriched": 0}
        rows = await self.repo.fetch_dart_unenriched(DART_PROMPT_VERSION, limit)
        enriched = 0
        async with httpx.AsyncClient(timeout=15) as client:
            for i, r in enumerate(rows, start=1):
                try:
                    resp = await client.get(
                        _DART_COMPANY_API,
                        params={"crtfc_key": key, "corp_code": r.corp_code},
                    )
                    data = resp.json()
                except Exception:
                    logger.warning("DART 기업개황 조회 실패 corp_code=%s", r.corp_code, exc_info=False)
                    continue
                status = data.get("status")
                if status != "000":
                    logger.warning(
                        "DART 기업개황 비정상 status=%s corp_code=%s", status, r.corp_code
                    )
                    # 영구 실패(013 데이터 없음·100 잘못된 요청)는 tombstone 적재로 일일 재호출 누수 차단.
                    # 키·쿼터·점검 등 일시 오류는 미저장 → 다음 실행 재시도.
                    if status in ("013", "100"):
                        await self.repo.upsert_silver(
                            {
                                "sector_slug": None,
                                "amount_krw": None,
                                "currency": None,
                                "series": None,
                                "company": None,
                                "ref_date": r.ref_date,
                                "raw_id": r.raw_id,
                                "model_name": "dart_company_api",
                                "prompt_version": DART_PROMPT_VERSION,
                                "input_hash": hashlib.sha256(
                                    f"{r.corp_code}|{r.raw_id}".encode("utf-8")
                                ).hexdigest(),
                            }
                        )
                    continue
                sector = map_ksic_to_sector(data.get("induty_code"))
                # KRW 외 통화 가드 — 현재 DART CB·M&A 수집기는 currency 를 채우지 않아(항상 NULL=KRW)
                # 실질 항상 통과하는 방어적 가드다(향후 외화 공시 대비).
                krw_ok = (r.currency or "KRW").upper() == "KRW"
                await self.repo.upsert_silver(
                    {
                        "sector_slug": sector,
                        "amount_krw": r.investment_amount if krw_ok else None,
                        "currency": r.currency or "KRW",
                        "series": "CB발행" if r.source_type == "DART_CONVERTIBLE_BOND" else "M&A",
                        "company": r.target_company_or_fund or r.investor_name,
                        "ref_date": r.ref_date,
                        "raw_id": r.raw_id,
                        "model_name": "dart_company_api",
                        "prompt_version": DART_PROMPT_VERSION,
                        # dedup 은 (raw_table_ref, raw_id, prompt_version) 자연키 담당 — 해시는 입력 식별용.
                        "input_hash": hashlib.sha256(
                            f"{r.corp_code}|{r.raw_id}".encode("utf-8")
                        ).hexdigest(),
                    }
                )
                if sector is not None and krw_ok:
                    enriched += 1
                if i % REFINE_CHUNK == 0:
                    await self.session.commit()
        await self.session.commit()
        return {"dart_scanned": len(rows), "dart_enriched": enriched}
