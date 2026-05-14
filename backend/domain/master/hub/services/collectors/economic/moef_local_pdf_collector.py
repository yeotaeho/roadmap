"""기재부 예산안·국가재정운용계획 시드 PDF 로컬 수집기.

운영 정책 (`GOVT_DOCS_COLLECTION_STRATEGY.md` 2026-05-13):
  - 기재부 거시 예산안은 **연 1~2회** 갱신 → 자동 크롤링 비용 > 자동화 가치
  - **사람이 다운로드 후** 업로드 API 또는 본 collector 의 배치 ingest 로 적재
  - 본 모듈은 **로컬 파일 시스템 경로**만 받아 파싱 → DTO 생성 (네트워크 없음)

사용 시나리오:
  1) 통합 테스트·파서 회귀 — `backend/scripts/*.pdf` 시드 파일
  2) 운영 배치 — 사용자가 부서 공유 폴더에 떨어뜨린 파일을 cron 으로 적재
  3) 업로드 API — `BackgroundTasks` 가 임시 파일 경로를 본 컬렉터에 위임
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from domain.master.hub.services.collectors.economic._doc_parsers import (
    parse_document,
    supports,
)
from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto

logger = logging.getLogger(__name__)


SOURCE_TYPE_FISCAL = "GOVT_MOEF_FISCAL"   # 국가재정운용계획
SOURCE_TYPE_BUDGET = "GOVT_MOEF_BUDGET"   # 예산안
SOURCE_TYPE_GENERIC = "GOVT_MOEF_DOC"     # 매핑 미정 시 fallback


# 파일명에 어떤 키워드가 들어있느냐로 source_type 1차 자동 추정.
_TYPE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"국가재정운용계획|재정운용계획"), SOURCE_TYPE_FISCAL),
    (re.compile(r"예산안|국회통과|본예산|예산서"), SOURCE_TYPE_BUDGET),
)


# 텍스트 보존 한도 (DB 행당 raw_metadata.full_text)
_FULL_TEXT_HARD_CAP = 200_000  # 약 200KB — Bronze 보존 한도


class MoefLocalPdfCollector:
    """로컬 PDF/Excel 파일을 받아 DTO 로 변환.

    Public 메서드는 모두 파일 시스템 동기 I/O 라 sync — 라우터에서 BackgroundTasks 로 띄우는 것을 권장.
    """

    def collect_paths(
        self,
        paths: list[Path],
        *,
        source_type: str | None = None,
        published_at: datetime | None = None,
        source_url: str | None = None,
        raw_title: str | None = None,
        original_filename: str | None = None,
        text_cap: int = _FULL_TEXT_HARD_CAP,
    ) -> tuple[list[EconomicCollectDto], dict[str, int]]:
        """여러 파일을 순차 파싱.

        Args:
            paths: 파싱 대상 파일 경로.
            source_type: 명시적으로 source_type 강제. None 이면 파일명 규칙 기반 추정.
            published_at: 명시적으로 게시일 부여. None 이면 파일명에서 연도 추정 → 1월 1일.
            source_url: 명시적으로 출처 URL. None 이면 `local://<sha1>` 형식으로 deterministic 생성.
            raw_title: 사용자가 명시한 제목(업로드 시나리오). None 이면 `original_filename` →
                `path.name` 순으로 폴백.
            original_filename: 업로드 시 보존해야 할 원본 파일명 (단일 파일 시나리오 권장).
                다중 파일 시나리오에서 사용하면 모든 행이 동일한 제목·메타로 채워지니 주의.
            text_cap: raw_metadata.full_text 길이 컷.

        Returns:
            (dtos, stats) — stats: total / parsed_ok / parse_failed / unsupported.
        """
        stats = {
            "total": 0,
            "parsed_ok": 0,
            "parse_failed": 0,
            "unsupported": 0,
        }
        dtos: list[EconomicCollectDto] = []

        for raw_path in paths:
            path = Path(raw_path)
            stats["total"] += 1

            if not path.exists():
                logger.error("[moef-local] file not found: %s", path)
                stats["parse_failed"] += 1
                continue
            if not supports(path):
                logger.warning("[moef-local] unsupported extension: %s", path)
                stats["unsupported"] += 1
                continue

            parsed = parse_document(path)
            if parsed.get("error"):
                stats["parse_failed"] += 1
                logger.error(
                    "[moef-local] parse failed file=%s error=%s",
                    path.name,
                    parsed.get("error"),
                )
            else:
                stats["parsed_ok"] += 1

            dto = self._build_dto(
                path=path,
                parsed=parsed,
                source_type=source_type,
                published_at=published_at,
                source_url=source_url,
                raw_title=raw_title,
                original_filename=original_filename,
                text_cap=text_cap,
            )
            dtos.append(dto)

        logger.info("[moef-local] collected dtos=%s stats=%s", len(dtos), stats)
        return dtos, stats

    # ------------------------------------------------------------------

    def _build_dto(
        self,
        *,
        path: Path,
        parsed: dict[str, Any],
        source_type: str | None,
        published_at: datetime | None,
        source_url: str | None,
        raw_title: str | None,
        original_filename: str | None,
        text_cap: int,
    ) -> EconomicCollectDto:
        # 임시 파일 업로드 시나리오 대응:
        #   - 라우터가 tmp_dir 에 UUID 이름으로 저장하기 때문에 path.name 은 무의미한 해시가 됨.
        #   - 원본 파일명을 명시적으로 받아 source_type · published_at · 제목 추정에 사용한다.
        name_for_inference = original_filename or path.name

        stype = source_type or _guess_source_type(name_for_inference)
        url = source_url or _local_source_url(path)
        pubdate = published_at or _guess_published_at(name_for_inference)

        full_text = parsed.get("full_text") or ""

        raw_metadata: dict[str, Any] = {
            "board_key": "moef_local_pdf",
            "is_signal": False,                  # 거시 팩트 데이터
            "collected_via": "moef-local-pdf",
            "file_name": original_filename or parsed.get("file_name") or path.name,
            "file_size_bytes": parsed.get("file_size_bytes"),
            "extraction_method": parsed.get("extraction_method"),
            "full_text_length": len(full_text),
        }
        if parsed.get("page_count") is not None:
            raw_metadata["page_count"] = parsed["page_count"]
        if parsed.get("sheet_count") is not None:
            raw_metadata["sheet_count"] = parsed["sheet_count"]
        if parsed.get("error"):
            raw_metadata["parse_error"] = parsed["error"]
        if full_text:
            raw_metadata["full_text"] = full_text[:text_cap]

        title = (raw_title or _title_from_filename(name_for_inference)).strip()
        if not title:
            title = "기획재정부 문서"
        return EconomicCollectDto(
            source_type=stype,
            source_url=url,
            raw_title=title[:500],
            investor_name="기획재정부",
            target_company_or_fund=None,
            investment_amount=None,
            currency="KRW",
            raw_metadata=raw_metadata,
            published_at=pubdate,
        )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _guess_source_type(filename: str) -> str:
    for pat, stype in _TYPE_RULES:
        if pat.search(filename):
            return stype
    return SOURCE_TYPE_GENERIC


_YEAR_RE = re.compile(r"(20\d{2})")
_TWO_DIGIT_YEAR_RE = re.compile(r"(?:^|[^0-9])(\d{2})\s*년")


def _guess_published_at(filename: str) -> datetime | None:
    """파일명에서 연도(YYYY 또는 'NN년')를 찾아 1월 1일 UTC 로 fallback."""
    m = _YEAR_RE.search(filename)
    if m:
        try:
            return datetime(int(m.group(1)), 1, 1, tzinfo=timezone.utc)
        except ValueError:
            pass
    m2 = _TWO_DIGIT_YEAR_RE.search(filename)
    if m2:
        try:
            yy = int(m2.group(1))
            return datetime(2000 + yy, 1, 1, tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def _title_from_filename(filename: str) -> str:
    """확장자 제거 + 앞뒤 잡음 트림 → 사람이 보기 좋은 제목."""
    stem = Path(filename).stem
    stem = re.sub(r"\s+", " ", stem).strip()
    # 선행 숫자·점·하이픈 (예: `3. 2025~2029년 ...`) 도 의미 있으니 유지
    return stem or "기획재정부 문서"


def _local_source_url(path: Path) -> str:
    """동일 파일은 동일 URL — sha1(file content + size) 기반.

    네트워크가 아닌 로컬 데이터지만 `source_url` UNIQUE 제약을 활용하기 위해
    deterministic 한 가짜 URL 을 만든다. (`local://moef/<digest>/<filename>`)
    """
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    # 큰 파일에 대해 전체 해시 비용이 부담될 수 있어 size + 처음 1MB 만 해시
    digest_src = hashlib.sha1()
    digest_src.update(str(size).encode())
    try:
        with path.open("rb") as f:
            digest_src.update(f.read(1024 * 1024))
    except OSError:
        pass
    digest = digest_src.hexdigest()[:16]
    # 파일명에 한글이 들어가도 URL 로 사용 가능 (DB 는 TEXT, 검색은 UNIQUE 만 활용)
    return f"local://moef/{digest}/{path.name}"
