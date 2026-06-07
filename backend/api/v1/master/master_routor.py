"""Master / Bronze 수집 API."""

from __future__ import annotations

import logging
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.database import AsyncSessionLocal, get_db
from core.scheduler import list_jobs as scheduler_list_jobs
from core.scheduler import run_job_now as scheduler_run_job_now
from domain.master.hub.services.bronze_economic_ingest_service import BronzeEconomicIngestService
from domain.master.hub.services.bronze_market_timeseries_ingest_service import (
    BronzeMarketTimeseriesIngestService,
)
from domain.master.hub.services.bronze_opportunity_ingest_service import (
    BronzeOpportunityIngestService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/master", tags=["master"])


class DartBronzeIngestRequest(BaseModel):
    """YYYYMMDD. 미입력 시 Collector 기본값(최근 7일·금일)."""

    bgn_de: str | None = Field(default=None, description="시작일 YYYYMMDD")
    end_de: str | None = Field(default=None, description="종료일 YYYYMMDD")
    include_ownership_disclosure: bool = Field(
        default=False,
        description="지분공시(pblntf_ty=D) 대량보유·의결권 대량보유 등 병행 수집 여부",
    )


@router.post("/bronze/economic/dart")
async def run_dart_economic_bronze(
    body: DartBronzeIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Open DART 주요사항보고(B)·지분공시(D) 중 자본 흐름 관련 공시를 `raw_economic_data`에 적재."""
    settings = get_settings()
    svc = BronzeEconomicIngestService(db, settings.dart_api_key)
    try:
        return await svc.ingest_dart(
            bgn_de=body.bgn_de,
            end_de=body.end_de,
            include_ownership_disclosure=body.include_ownership_disclosure,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        logger.exception("DART Bronze ingest 실패")
        raise HTTPException(status_code=502, detail="DART 수집 중 오류가 발생했습니다.") from None


@router.post("/bronze/economic/wowtale")
async def run_wowtale_economic_bronze(
    max_items: int = Query(50, ge=1, le=100, description="최대 수집 건수"),
    fetch_article_if_short: bool = Query(
        True,
        description="RSS 본문이 짧으면 기사 permalink 를 GET 해 보완",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Wowtale RSS 피드 기반 스타트업 투자 뉴스를 `raw_economic_data`에 적재."""
    svc = BronzeEconomicIngestService(db, None)
    try:
        return await svc.ingest_wowtale(
            max_items=max_items,
            fetch_article_if_short=fetch_article_if_short,
        )
    except Exception:
        logger.exception("Wowtale Bronze ingest 실패")
        raise HTTPException(status_code=502, detail="Wowtale RSS 수집 중 오류가 발생했습니다.") from None


class WowtaleArchiveRequest(BaseModel):
    """Wowtale 아카이브 Backfill 요청 파라미터."""

    max_pages: int = Field(
        default=50,
        ge=1,
        le=200,
        description="카테고리당 최대 페이지 수 (페이지당 ~20건, 기본 50 → ~1,000건)",
    )
    from_date: str | None = Field(
        default=None,
        description="이 날짜 이전 기사 수집 중단 (YYYY-MM-DD). 미입력 시 max_pages까지 전부 수집",
    )
    fetch_article_body: bool = Field(
        default=True,
        description="기사 상세 페이지 본문 크롤링 여부 (False면 제목·날짜만 수집, 빠름)",
    )
    categories: list[str] | None = Field(
        default=None,
        description=(
            "크롤링 카테고리 slug 목록. 미입력 시 기본값: "
            "['funding', 'venture-capital', 'Global-news']"
        ),
    )


_ARCHIVE_INVESTMENT_FILTER_SLUGS: frozenset[str] = frozenset({"Global-news"})


@router.post(
    "/bronze/economic/wowtale-archive",
    status_code=202,
    summary="Wowtale 아카이브 Backfill (비동기)",
)
async def run_wowtale_archive_bronze(
    body: WowtaleArchiveRequest,
    background_tasks: BackgroundTasks,
):
    """Wowtale 카테고리 아카이브를 순회해 과거 기사를 `raw_economic_data`에 적재 (Backfill 전용).

    RSS 수집기의 최근 50건 한계를 보완한다.
    수집량에 따라 수십 분 소요될 수 있으므로 **202 Accepted** 로 즉시 응답하고
    BackgroundTask에서 실행한다.
    """
    from datetime import timedelta, timezone

    _KST = timezone(timedelta(hours=9))

    from_date: datetime | None = None
    if body.from_date:
        try:
            from_date = datetime.strptime(body.from_date, "%Y-%m-%d").replace(tzinfo=_KST)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="from_date 형식은 YYYY-MM-DD 입니다. 예: 2025-01-01",
            ) from None

    # (slug, apply_investment_filter) 변환
    categories: list[tuple[str, bool]] | None = None
    if body.categories:
        categories = [
            (slug, slug in _ARCHIVE_INVESTMENT_FILTER_SLUGS)
            for slug in body.categories
        ]

    async def _run_backfill() -> None:
        async with AsyncSessionLocal() as bg_session:
            svc = BronzeEconomicIngestService(bg_session, None)
            result = await svc.ingest_wowtale_archive(
                max_pages=body.max_pages,
                from_date=from_date,
                fetch_article_body=body.fetch_article_body,
                categories=categories,
            )
        logger.info("Wowtale archive backfill 완료: %s", result)

    background_tasks.add_task(_run_backfill)

    return {
        "status": "accepted",
        "message": (
            f"Wowtale 아카이브 Backfill이 백그라운드에서 시작되었습니다. "
            f"max_pages={body.max_pages}, from_date={body.from_date}, "
            f"fetch_article_body={body.fetch_article_body}"
        ),
    }


@router.post("/bronze/economic/platum")
async def run_platum_economic_bronze(
    max_items: int = Query(50, ge=1, le=100, description="최대 수집 건수"),
    fetch_article_if_short: bool = Query(
        True,
        description="RSS 본문이 짧으면 기사 permalink 를 GET 해 보완",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Platum 펀딩 RSS 기반 스타트업 투자 뉴스를 `raw_economic_data`에 적재."""
    svc = BronzeEconomicIngestService(db, None)
    try:
        return await svc.ingest_platum(
            max_items=max_items,
            fetch_article_if_short=fetch_article_if_short,
        )
    except Exception:
        logger.exception("Platum Bronze ingest 실패")
        raise HTTPException(status_code=502, detail="Platum RSS 수집 중 오류가 발생했습니다.") from None


@router.post("/bronze/economic/startup-recipe")
async def run_startup_recipe_economic_bronze(
    max_items: int = Query(50, ge=1, le=100, description="최대 수집 건수"),
    db: AsyncSession = Depends(get_db),
):
    """스타트업레시피 RSS 피드 기반 스타트업 투자 뉴스를 `raw_economic_data`에 적재."""
    svc = BronzeEconomicIngestService(db, None)
    try:
        return await svc.ingest_startup_recipe(max_items=max_items)
    except Exception:
        logger.exception("StartupRecipe Bronze ingest 실패")
        raise HTTPException(
            status_code=502,
            detail="StartupRecipe RSS 수집 중 오류가 발생했습니다.",
        ) from None


@router.post("/bronze/economic/yahoo-finance")
async def run_yahoo_finance_economic_bronze(
    backfill: bool = Query(
        False,
        description="True면 기간 내 모든 거래일을 스캔(과거 급증 누적, yfinance 호출 다수·느림)",
    ),
    period: str | None = Query(
        None,
        description="yfinance history(period=…). 예: 1y, 6mo. 생략 시 컬렉터 기본(1y)",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Yahoo Finance 거래량 급증(Volume Surge) 신호를 `raw_economic_data`에 적재.

    대상 (총 16종):
      - 한국 테마 ETF 5종    (`YAHOO_ETF_*`)
      - 한국 대형주 5종      (`YAHOO_STOCK_KR_*`)
      - 글로벌 ETF 6종       (`YAHOO_GLOBAL_*`)  ← 한국 시장 선행 지표

    자산별 멀티 레벨 임계값 (1.5~2.5배), VWAP 근사로 유입 금액 산출.
    """
    svc = BronzeEconomicIngestService(db, None)
    try:
        return await svc.ingest_yahoo_finance(backfill=backfill, period=period)
    except Exception:
        logger.exception("Yahoo Finance Bronze ingest 실패")
        raise HTTPException(
            status_code=502,
            detail="Yahoo Finance 수집 중 오류가 발생했습니다.",
        ) from None


@router.post("/bronze/market-timeseries/yahoo")
async def run_yahoo_market_timeseries_bronze(
    period: str | None = Query(
        None,
        description="yfinance history period (예: 1mo, 1y). 생략 시 incremental 기본",
    ),
    incremental: bool = Query(
        True,
        description="True=1mo(일일), False=1y(초기 backfill)",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Yahoo Finance 16티커 일별 OHLCV → `raw_market_timeseries` upsert.

    급증 신호(`raw_economic_data`)와 분리된 **연속 시계열** Bronze.
    Silver에서 거래대금 추세·20일 평균 대비 비율·섹터 모멘텀 산출에 사용.
    """
    svc = BronzeMarketTimeseriesIngestService(db)
    try:
        return await svc.ingest_yahoo_timeseries(
            period=period,
            incremental=incremental,
        )
    except Exception:
        logger.exception("Yahoo market timeseries Bronze ingest 실패")
        raise HTTPException(
            status_code=502,
            detail="Yahoo 시장 시계열 수집 중 오류가 발생했습니다.",
        ) from None


@router.post("/bronze/economic/yahoo-macro")
async def run_yahoo_macro_economic_bronze(
    db: AsyncSession = Depends(get_db),
):
    """Yahoo Macro 가격 변동(Price Surge) Z-score 기반 수집 → `raw_economic_data`.

    대상 (총 8종):
      - FX 3종       (USDKRW / EURKRW / JPYKRW)
      - 미 국채금리 2종 (^TNX / ^IRX)
      - 원자재 2종    (금 / WTI 원유)
      - 가상자산 1종  (BTC-USD)

    알고리즘: `|일간수익률| / 20일 표준편차 ≥ 자산별 Z 임계값(2.0~2.5)`.
    `investment_amount` 은 가격 변동 특성상 `None`, 정량 데이터는 `raw_metadata` 에 보존.
    """
    svc = BronzeEconomicIngestService(db, None)
    try:
        return await svc.ingest_yahoo_macro()
    except Exception:
        logger.exception("Yahoo Macro Bronze ingest 실패")
        raise HTTPException(
            status_code=502,
            detail="Yahoo Macro 수집 중 오류가 발생했습니다.",
        ) from None


@router.post("/bronze/economic/yahoo-macro-backfill", status_code=202)
async def run_yahoo_macro_backfill_bronze(
    background_tasks: BackgroundTasks,
    period: str | None = Query(
        None,
        description="yfinance history period (예: 1y, 6mo). 생략 시 기본(1y)",
    ),
):
    """Yahoo Macro 거시 지표 과거 급변동 이력 Backfill (비동기).

    슬라이딩 윈도우로 `period` 기간 내 모든 거래일을 스캔해
    Z-score 임계값 초과 일자를 누적 적재한다.
    티커당 ~250일 × 8개 자산 = 최대 2,000건 예상.
    **202 Accepted** 로 즉시 응답하고 BackgroundTask에서 실행한다.
    """
    async def _run_macro_backfill() -> None:
        async with AsyncSessionLocal() as bg_session:
            svc = BronzeEconomicIngestService(bg_session, None)
            result = await svc.ingest_yahoo_macro_backfill(period=period)
        logger.info("Yahoo Macro backfill 완료: %s", result)

    background_tasks.add_task(_run_macro_backfill)

    return {
        "status": "accepted",
        "message": (
            f"Yahoo Macro Backfill이 백그라운드에서 시작되었습니다. "
            f"period={period or 'default(1y)'}"
        ),
    }


@router.post("/bronze/economic/venturesquare")
async def run_venturesquare_economic_bronze(
    max_items: int = Query(50, ge=1, le=100, description="최대 수집 건수"),
    fetch_article_if_short: bool = Query(
        True,
        description="RSS 본문이 짧으면 기사 permalink 를 GET 해 보완",
    ),
    db: AsyncSession = Depends(get_db),
):
    """벤처스퀘어 펀딩 RSS 기반 스타트업 투자 뉴스를 `raw_economic_data`에 적재."""
    svc = BronzeEconomicIngestService(db, None)
    try:
        return await svc.ingest_venturesquare(
            max_items=max_items,
            fetch_article_if_short=fetch_article_if_short,
        )
    except Exception:
        logger.exception("Venturesquare Bronze ingest 실패")
        raise HTTPException(
            status_code=502,
            detail="Venturesquare RSS 수집 중 오류가 발생했습니다.",
        ) from None


# ---------------------------------------------------------------------------
# 정부 문서 (전략 A·B) — GOVT_DOCS_COLLECTION_STRATEGY.md 구현
# ---------------------------------------------------------------------------


@router.post("/bronze/economic/msit-press")
async def run_msit_press_bronze(
    max_pages: int = Query(6, ge=1, le=20, description="크롤링할 목록 페이지 수"),
    max_items: int = Query(100, ge=1, le=500, description="최대 적재 건수"),
    fetch_body: bool = Query(True, description="상세 본문 텍스트도 수집할지 여부"),
    target_year: int | None = Query(
        None, description="등록일 연도 필터(기본 2026, 매년 1월 1회 갱신)"
    ),
    db: AsyncSession = Depends(get_db),
):
    """과기부 `mId=307` 보도자료 (연도 + 제목 "시행") 자동 수집 → `raw_economic_data`."""
    svc = BronzeEconomicIngestService(db, None)
    try:
        return await svc.ingest_msit_press(
            max_pages=max_pages,
            max_items=max_items,
            fetch_body=fetch_body,
            target_year=target_year,
        )
    except Exception:
        logger.exception("MSIT 보도자료(mId=307) Bronze ingest 실패")
        raise HTTPException(
            status_code=502,
            detail="MSIT 보도자료 수집 중 오류가 발생했습니다.",
        ) from None


@router.post("/bronze/economic/msit-biz")
async def run_msit_biz_bronze(
    max_pages: int = Query(6, ge=1, le=20, description="크롤링할 목록 페이지 수"),
    max_items: int = Query(100, ge=1, le=500, description="최대 적재 건수"),
    fetch_body: bool = Query(True, description="상세 본문 텍스트도 수집할지 여부"),
    target_year: int | None = Query(
        None, description="등록일 연도 필터(기본 2026)"
    ),
    db: AsyncSession = Depends(get_db),
):
    """과기부 `mId=311` 사업공고 (연도 + 제목 "모집") 자동 수집 → `raw_economic_data`."""
    svc = BronzeEconomicIngestService(db, None)
    try:
        return await svc.ingest_msit_biz(
            max_pages=max_pages,
            max_items=max_items,
            fetch_body=fetch_body,
            target_year=target_year,
        )
    except Exception:
        logger.exception("MSIT 사업공고(mId=311) Bronze ingest 실패")
        raise HTTPException(
            status_code=502,
            detail="MSIT 사업공고 수집 중 오류가 발생했습니다.",
        ) from None


@router.post("/bronze/economic/msit-rnd-budget")
async def run_msit_rnd_budget_bronze(
    max_pages: int = Query(2, ge=1, le=10, description="크롤링할 목록 페이지 수"),
    max_items: int = Query(20, ge=1, le=100, description="최대 적재 건수"),
    db: AsyncSession = Depends(get_db),
):
    """과기부 `mId=63` 예산 및 결산 HWPX 자동 다운로드·파싱 → `raw_economic_data`.

    절차: 목록(publictSeqNo=295) → 연도별 view.do → `.hwpx` POST 다운로드 → ZIP+XML 파싱.
    """
    svc = BronzeEconomicIngestService(db, None)
    try:
        return await svc.ingest_msit_rnd_budget(
            max_pages=max_pages,
            max_items=max_items,
        )
    except Exception:
        logger.exception("MSIT R&D 예산(mId=63) Bronze ingest 실패")
        raise HTTPException(
            status_code=502,
            detail="MSIT R&D 예산 HWPX 수집 중 오류가 발생했습니다.",
        ) from None


@router.post("/bronze/economic/mfds-press")
async def run_mfds_press_bronze(
    max_pages: int = Query(5, ge=1, le=20, description="크롤링할 목록 페이지 수"),
    max_items: int = Query(100, ge=1, le=500, description="최대 적재 건수"),
    fetch_body: bool = Query(True, description="상세 본문 텍스트도 수집할지 여부"),
    target_year: int | None = Query(
        None, description="등록일 연도 필터(기본 2026). null 전달 시 컬렉터 기본"
    ),
    db: AsyncSession = Depends(get_db),
):
    """식약처 보도자료 (연도 + 허가/신약/임상 키워드) 자동 수집 → `raw_economic_data`.

    바이오/헬스 선행 신호(GOVT_MFDS_APPROVAL). 키 불필요(공개 웹 정적 HTML).
    """
    svc = BronzeEconomicIngestService(db, None)
    try:
        return await svc.ingest_mfds_press(
            max_pages=max_pages,
            max_items=max_items,
            fetch_body=fetch_body,
            target_year=target_year,
        )
    except Exception:
        logger.exception("MFDS 보도자료 Bronze ingest 실패")
        raise HTTPException(
            status_code=502,
            detail="MFDS 보도자료 수집 중 오류가 발생했습니다.",
        ) from None


@router.post("/bronze/economic/bok-ecos")
async def run_bok_ecos_bronze(
    start: str = Query(..., description="조회 시작(주기별): 월 YYYYMM / 연 YYYY / 일 YYYYMMDD"),
    end: str = Query(..., description="조회 종료(주기별): start 와 동일 포맷"),
    max_rows: int = Query(10000, ge=1, le=100000, description="통계표당 최대 행 수"),
    db: AsyncSession = Depends(get_db),
):
    """한국은행 ECOS 거시 시계열(FDI·통화량·기준금리) → `raw_economic_data`.

    `BOK_ECOS_API_KEY` 필요. 통계표/항목 코드는 컬렉터 `_ECOS_TARGETS` 에서 관리(Probe 검증).
    """
    settings = get_settings()
    svc = BronzeEconomicIngestService(db, None, bok_ecos_api_key=settings.bok_ecos_api_key)
    try:
        return await svc.ingest_bok_ecos(start=start, end=end, max_rows=max_rows)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        logger.exception("BOK ECOS Bronze ingest 실패")
        raise HTTPException(
            status_code=502,
            detail="BOK ECOS 수집 중 오류가 발생했습니다.",
        ) from None


@router.post("/bronze/economic/alio")
async def run_alio_economic_bronze(
    max_items: int = Query(
        200, ge=1, le=2000, description="최대 수집 건수"
    ),
    inst_filter: list[str] | None = Query(
        None,
        description="기관명 화이트리스트(부분일치). 생략 시 기본 9개 기관만 수집합니다.",
    ),
    biz_year: int | None = Query(
        None, ge=2020, le=2030, description="사업 연도 필터(옵션)"
    ),
    disable_keyword_filter: bool = Query(
        False,
        description="True면 제목·목적 키워드 필터를 끕니다(전체 탐색·디버그용).",
    ),
    db: AsyncSession = Depends(get_db),
):
    """ALIO(data.go.kr 15125286) 공공기관 사업 메타를 `raw_economic_data`에 적재."""
    settings = get_settings()
    svc = BronzeEconomicIngestService(db, None, settings.alio_service_key)
    try:
        return await svc.ingest_alio_projects(
            max_items=max_items,
            inst_filter=inst_filter,
            biz_year=biz_year,
            disable_keyword_filter=disable_keyword_filter,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        logger.exception("ALIO Economic Bronze ingest 실패")
        raise HTTPException(
            status_code=502,
            detail="ALIO 공공기관 사업정보 수집 중 오류가 발생했습니다.",
        ) from None


# ---------------------------------------------------------------------------
# 기재부 — 로컬 시드 PDF 배치 + 파일 업로드 API
# ---------------------------------------------------------------------------


class MoefBatchIngestRequest(BaseModel):
    """`backend/scripts/*.pdf` 등 **서버 측 로컬 파일 경로** 배치 적재 요청.

    운영 시: 부서 공유 폴더(또는 컨테이너 mounted volume) 경로를 적재 큐로 활용.
    """

    paths: list[str] = Field(
        ..., min_length=1, description="서버에서 접근 가능한 로컬 파일 경로 리스트"
    )
    source_type: str | None = Field(
        default=None,
        description="명시 시 모든 파일을 동일 source_type 으로 적재 (예: GOVT_MOEF_BUDGET)",
    )


@router.post("/bronze/economic/moef-local-pdfs")
async def run_moef_local_pdfs_bronze(
    body: MoefBatchIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """기재부 시드 PDF 배치 적재 — 동기 처리.

    대용량 파일을 다수 동시에 보낼 경우 504 위험이 있으므로,
    **사용자가 직접 업로드하는 시나리오는 `/bronze/economic/moef-upload` 사용 권장.**
    """
    svc = BronzeEconomicIngestService(db, None)
    try:
        return await svc.ingest_moef_local_pdfs(
            paths=body.paths,
            source_type=body.source_type,
        )
    except Exception:
        logger.exception("MOEF 로컬 PDF Bronze ingest 실패")
        raise HTTPException(
            status_code=500,
            detail="MOEF 로컬 PDF 적재 중 오류가 발생했습니다.",
        ) from None


@router.post("/bronze/economic/moef-upload", status_code=202)
async def upload_moef_budget_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="기재부 예산안/재정운용계획 PDF·Excel·HWPX 파일"),
    source_type: str | None = Form(
        None, description="GOVT_MOEF_BUDGET | GOVT_MOEF_FISCAL (미지정 시 파일명 추정)"
    ),
    raw_title: str | None = Form(None, description="사용자 제공 제목(미지정 시 파일명)"),
    source_url: str | None = Form(None, description="원본 게시판 URL(있다면 권장)"),
    published_at: datetime | None = Form(None, description="원본 게시일(ISO8601)"),
):
    """파일 업로드 + 비동기 백그라운드 파싱 (504 Gateway Timeout 방지).

    **응답**: `202 Accepted` — 업로드 즉시 수락, 실제 파싱·적재는 `BackgroundTasks` 가 수행.
    """
    # 임시 저장 (파일 크기에 비례한 디스크 사용)
    safe_suffix = Path(file.filename or "upload").suffix.lower() or ".bin"
    tmp_dir = Path(tempfile.gettempdir()) / "moef_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex
    tmp_path = tmp_dir / f"{job_id}{safe_suffix}"

    # 청크 단위 저장 — 대용량(수십 MB) 안전
    try:
        with tmp_path.open("wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
    finally:
        await file.close()

    original_filename = file.filename or tmp_path.name
    # 파일명에 잡음(공백·괄호·기호) 가능 — Path.stem 으로 확장자만 정리한 기본 제목.
    fallback_title = Path(original_filename).stem
    background_tasks.add_task(
        _run_moef_upload_job,
        tmp_path=str(tmp_path),
        original_filename=original_filename,
        source_type=source_type,
        raw_title=raw_title or fallback_title,
        source_url=source_url,
        published_at=published_at,
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "tmp_path": str(tmp_path),
        "original_filename": file.filename,
        "received_size_bytes": tmp_path.stat().st_size,
    }


async def _run_moef_upload_job(
    *,
    tmp_path: str,
    original_filename: str,
    source_type: str | None,
    raw_title: str | None,
    source_url: str | None,
    published_at: datetime | None,
) -> None:
    """`BackgroundTasks` 에서 호출되는 적재 잡 — 독립 세션·예외 격리."""
    path = Path(tmp_path)
    try:
        # raw_title 가 들어왔다면 deterministic URL 보존 위해 source_url 우선 사용
        async with AsyncSessionLocal() as session:
            svc = BronzeEconomicIngestService(session, None)
            try:
                result = await svc.ingest_moef_local_pdfs(
                    paths=[path],
                    source_type=source_type,
                    source_url=source_url,
                    published_at=published_at,
                    raw_title=raw_title,
                    original_filename=original_filename,
                )
                logger.info(
                    "MOEF upload job done file=%s result=%s",
                    original_filename,
                    result,
                )
            finally:
                await session.close()
    except Exception:
        logger.exception(
            "MOEF upload job 실패 file=%s tmp=%s", original_filename, tmp_path
        )
    finally:
        # 디스크 정리 (실패해도 무시)
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


@router.delete("/bronze/economic/by-source-type/{source_type}")
async def purge_bronze_economic_by_source_type(
    source_type: str,
    db: AsyncSession = Depends(get_db),
):
    """잘못 적재된 Bronze 데이터를 source_type 단위로 일괄 삭제 (운영용 정리 도구)."""
    if not source_type or len(source_type) > 50:
        raise HTTPException(status_code=400, detail="source_type 길이가 잘못되었습니다.")
    svc = BronzeEconomicIngestService(db, get_settings().dart_api_key)
    return await svc.purge_by_source_type(source_type)


# ---------------------------------------------------------------------------
# Opportunity Bronze (raw_opportunity_data)
# ---------------------------------------------------------------------------


@router.post("/bronze/opportunity/smes")
async def run_smes_opportunity_bronze(
    max_items: int = Query(100, ge=1, le=500, description="최대 수집 건수"),
    start_date: str | None = Query(
        default=None, description="조회 시작일 YYYYMMDD (옵션)"
    ),
    end_date: str | None = Query(
        default=None, description="조회 종료일 YYYYMMDD (옵션)"
    ),
    db: AsyncSession = Depends(get_db),
):
    """중소벤처기업부 사업공고 OpenAPI를 호출하여 `raw_opportunity_data`에 적재."""
    settings = get_settings()
    svc = BronzeOpportunityIngestService(db, settings.smes_service_key)
    try:
        return await svc.ingest_smes(
            max_items=max_items,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        logger.exception("SMES Opportunity Bronze ingest 실패")
        raise HTTPException(
            status_code=502, detail="SMES 사업공고 수집 중 오류가 발생했습니다."
        ) from None


@router.post("/bronze/economic/subsidy24")
async def run_subsidy24_bronze(
    max_items: int = Query(500, ge=1, le=2000, description="최대 수집 건수"),
    db: AsyncSession = Depends(get_db),
):
    """보조금24(gov24) 정부 지원 서비스 목록을 `raw_economic_data`에 적재.

    증분: DB 최신 수정일시 이후 변경된 서비스만 수집 (최초 실행 시 전체).
    """
    settings = get_settings()
    svc = BronzeEconomicIngestService(
        db, None, subsidy24_service_key=settings.subsidy24_service_key
    )
    try:
        return await svc.ingest_subsidy24(max_items=max_items)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        logger.exception("보조금24 Bronze ingest 실패")
        raise HTTPException(
            status_code=502, detail="보조금24 수집 중 오류가 발생했습니다."
        ) from None


@router.post("/bronze/economic/dart-periodic")
async def run_dart_periodic_bronze(
    bgn_de: str | None = Query(None, description="시작일 YYYYMMDD (미입력 시 최근 30일)"),
    end_de: str | None = Query(None, description="종료일 YYYYMMDD"),
    enrich_financials: bool = Query(True, description="R&D/CAPEX 재무 보강 여부 (KOSPI/KOSDAQ)"),
    max_enrich: int = Query(200, ge=1, le=500, description="재무 보강 최대 건수"),
    db: AsyncSession = Depends(get_db),
):
    """DART 정기공시(A) 사업보고서·반기보고서를 `raw_economic_data`에 적재.

    DART_API_KEY 필요. KOSPI/KOSDAQ 법인의 R&D·CAPEX 금액 보강 포함.
    """
    settings = get_settings()
    svc = BronzeEconomicIngestService(db, settings.dart_api_key)
    try:
        return await svc.ingest_dart_periodic(
            bgn_de=bgn_de,
            end_de=end_de,
            enrich_financials=enrich_financials,
            max_enrich=max_enrich,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        logger.exception("DART 정기공시 Bronze ingest 실패")
        raise HTTPException(
            status_code=502, detail="DART 정기공시 수집 중 오류가 발생했습니다."
        ) from None


@router.post("/bronze/economic/mss-press")
async def run_mss_press_bronze(
    max_items: int = Query(200, ge=1, le=1000, description="최대 수집 건수"),
    db: AsyncSession = Depends(get_db),
):
    """중소벤처기업부(MSS) 보도자료를 `raw_economic_data`에 적재.

    API 키 불필요. 증분 수집 (bcIdx 워터마크).
    """
    svc = BronzeEconomicIngestService(db, None)
    try:
        return await svc.ingest_mss_press(max_items=max_items)
    except Exception:
        logger.exception("중기부 보도자료 Bronze ingest 실패")
        raise HTTPException(
            status_code=502, detail="중기부 보도자료 수집 중 오류가 발생했습니다."
        ) from None


@router.post("/bronze/economic/dart-ipo")
async def run_dart_ipo_bronze(
    bgn_de: str | None = Query(None, description="시작일 YYYYMMDD (기본: 오늘-7일, 최대 14일 범위 권장)"),
    end_de: str | None = Query(None, description="종료일 YYYYMMDD (기본: 오늘)"),
    db: AsyncSession = Depends(get_db),
):
    """DART 발행공시(C)에서 증권신고서(주식) 등 IPO 선행 신호 → raw_economic_data 적재."""
    settings = get_settings()
    if not settings.dart_api_key:
        raise HTTPException(status_code=422, detail="dart_api_key가 설정되지 않았습니다.")
    svc = BronzeEconomicIngestService(db, settings.dart_api_key)
    try:
        return await svc.ingest_dart_ipo(bgn_de=bgn_de, end_de=end_de)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        logger.exception("DART IPO 발행공시 Bronze ingest 실패")
        raise HTTPException(status_code=502, detail="DART IPO 발행공시 수집 중 오류가 발생했습니다.") from None


@router.post("/bronze/economic/nps-portfolio")
async def run_nps_portfolio_bronze(
    bgn_de: str | None = Query(None, description="시작일 YYYYMMDD (기본: 오늘-14일)"),
    end_de: str | None = Query(None, description="종료일 YYYYMMDD (기본: 오늘)"),
    max_pages: int = Query(30, ge=1, le=100, description="DART API 최대 페이지 수"),
    db: AsyncSession = Depends(get_db),
):
    """DART 지분공시(D)에서 국민연금공단 대량보유 변동 이력 → raw_economic_data 적재."""
    settings = get_settings()
    if not settings.dart_api_key:
        raise HTTPException(status_code=422, detail="dart_api_key가 설정되지 않았습니다.")
    svc = BronzeEconomicIngestService(db, settings.dart_api_key)
    try:
        return await svc.ingest_nps_portfolio(bgn_de=bgn_de, end_de=end_de, max_pages=max_pages)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        logger.exception("국민연금 포트폴리오 Bronze ingest 실패")
        raise HTTPException(status_code=502, detail="국민연금 포트폴리오 수집 중 오류가 발생했습니다.") from None


@router.post("/bronze/economic/naver-datalab")
async def run_naver_datalab_bronze(
    start_date: str | None = Query(
        None,
        description="조회 시작일 YYYYMMDD (기본: 오늘-28일). 과거 날짜 지정 시 backfill.",
    ),
    end_date: str | None = Query(None, description="조회 종료일 YYYYMMDD (기본: 오늘)"),
    db: AsyncSession = Depends(get_db),
):
    """네이버 DataLab API로 분야별 주간 검색량 비율(0~100) 수집 → raw_economic_data 적재.

    5개 핵심 경제 분야(AI·스타트업·바이오·에너지·핀테크) 검색 트렌드.
    start_date를 과거로 지정하면 최대 1년치 backfill 가능.
    """
    settings = get_settings()
    if not settings.naver_client_id or not settings.naver_client_secret:
        raise HTTPException(
            status_code=422,
            detail="naver_client_id / naver_client_secret가 설정되지 않았습니다.",
        )
    svc = BronzeEconomicIngestService(
        db, None,
        naver_client_id=settings.naver_client_id,
        naver_client_secret=settings.naver_client_secret,
    )
    try:
        return await svc.ingest_naver_datalab(start_date=start_date, end_date=end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        logger.exception("Naver DataLab Bronze ingest 실패")
        raise HTTPException(status_code=502, detail="Naver DataLab 수집 중 오류가 발생했습니다.") from None


@router.post("/bronze/economic/naver-search")
async def run_naver_search_bronze(
    target_date: str | None = Query(
        None,
        description="수집 날짜 YYYYMMDD (기본: 어제). 과거 날짜 지정 시 backfill.",
    ),
    db: AsyncSession = Depends(get_db),
):
    """네이버 뉴스 API로 키워드별 일별 기사 수 수집 → raw_economic_data 적재.

    7그룹 24개 키워드(AI·스타트업·이직·바이오·에너지·핀테크·정부지원) 각각의
    당일 뉴스 기사 총 건수(total)를 수집하는 언론 공급(supply) 신호.
    DataLab 주간 검색 수요와 교차 분석 시 "뉴스 급증→검색 급증" 패턴 포착 가능.
    """
    settings = get_settings()
    if not settings.naver_client_id or not settings.naver_client_secret:
        raise HTTPException(
            status_code=422,
            detail="naver_client_id / naver_client_secret가 설정되지 않았습니다.",
        )
    svc = BronzeEconomicIngestService(
        db, None,
        naver_client_id=settings.naver_client_id,
        naver_client_secret=settings.naver_client_secret,
    )
    try:
        return await svc.ingest_naver_search(target_date=target_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        logger.exception("Naver News Search Bronze ingest 실패")
        raise HTTPException(status_code=502, detail="Naver 뉴스 검색 수집 중 오류가 발생했습니다.") from None


@router.post("/bronze/economic/kipris-patents")
async def run_kipris_patents_bronze(
    db: AsyncSession = Depends(get_db),
):
    """KIPRIS PLUS API로 기술 분야별 주간 특허 출원 건수 수집 → raw_economic_data 적재.

    인증: KIPRIS_API_KEY 필요 (ServiceKey 파라미터).
    수집 주기: 주 1회 (이번 주 이미 수집됐으면 skip).
    대상 기술 키워드: AI·바이오·에너지·반도체·모빌리티·핀테크 (총 20개).
    """
    settings = get_settings()
    kipris_key = getattr(settings, "kipris_api_key", None)
    if not kipris_key:
        raise HTTPException(status_code=422, detail="KIPRIS_API_KEY가 설정되지 않았습니다.")
    svc = BronzeEconomicIngestService(db, None, kipris_api_key=kipris_key)
    try:
        return await svc.ingest_kipris_patents()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        logger.exception("KIPRIS 특허 트렌드 Bronze ingest 실패")
        raise HTTPException(status_code=502, detail="KIPRIS 특허 수집 중 오류가 발생했습니다.") from None


@router.delete("/bronze/opportunity/by-source-type/{source_type}")
async def purge_bronze_opportunity_by_source_type(
    source_type: str,
    db: AsyncSession = Depends(get_db),
):
    """잘못 적재된 Opportunity Bronze 데이터를 source_type 단위로 일괄 삭제."""
    if not source_type or len(source_type) > 50:
        raise HTTPException(status_code=400, detail="source_type 길이가 잘못되었습니다.")
    s = get_settings()
    svc = BronzeOpportunityIngestService(db, s.smes_service_key)
    return await svc.purge_by_source_type(source_type)


# ---------------------------------------------------------------------------
# Bronze 자동 수집 스케줄러 운영 API
# ---------------------------------------------------------------------------


@router.get("/scheduler/jobs")
async def list_scheduler_jobs():
    """현재 등록된 스케줄 잡과 다음 트리거 시각 조회.

    SCHEDULER_ENABLED=false 인 경우 빈 배열 반환.
    """
    settings = get_settings()
    return {
        "enabled": settings.scheduler_enabled,
        "timezone": settings.scheduler_timezone,
        "daily_at": settings.scheduler_daily_at,
        "weekly": {
            "day_of_week": settings.scheduler_weekly_dow,
            "at": settings.scheduler_weekly_at,
        },
        "jobs": scheduler_list_jobs(),
    }


@router.post("/scheduler/jobs/{job_id}/run")
async def run_scheduler_job_now(job_id: str):
    """등록된 잡을 지금 1회 즉시 실행 (수동 트리거).

    ``daily_dart`` / ``dart`` 어느 쪽으로도 호출 가능.
    """
    try:
        return await scheduler_run_job_now(job_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
