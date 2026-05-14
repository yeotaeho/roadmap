"""과기부 `mId=63` (예산 및 결산 — 사전정보공표) HWPX 자동 수집기.

흐름:
  1) 목록 페이지 `publicinfo/detailList.do?...&publictSeqNo=295&searchTxt=예산` 진입
  2) 각 행에서 `publictListSeqNo` (연도별 게시물 ID) 수집
  3) 상세 페이지 `publicinfo/view.do?referKey={295,N}&...` 진입
  4) `<ul class="down_file">` 에서 `.hwpx` 첨부 1순위 선택
  5) POST `/ssm/file/fileDown.do` 로 다운로드 (Referer = 상세 URL)
  6) Content-Disposition 의 파일명으로 임시 저장 → `_doc_parsers.parse_hwpx()`
  7) `full_text` 를 `raw_metadata.full_text` 에 보존하고 DTO 생성

설계 노트:
  - MSIT 사이트 마크업은 흔히 개편되므로 핵심 셀렉터/파라미터 추출 부분에 다중 폴백을 둔다.
  - HWPX 우선, 없으면 `.hwp` → `.pdf` 순으로 폴백 (파서가 지원하는 포맷에 한해서만 다운로드).
  - 워터마크: `last_seen_list_seq_no` (`publictListSeqNo` 정수) 이하는 스킵.
"""

from __future__ import annotations

import asyncio
import logging
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from domain.master.hub.services.collectors.economic._doc_parsers import (
    parse_document,
)
from domain.master.hub.services.collectors.economic._msit_common import (
    BASE_URL,
    DEFAULT_HEADERS,
    async_get_html,
    make_async_client,
    parse_kst_date,
)
from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto

logger = logging.getLogger(__name__)


SOURCE_TYPE = "GOVT_MSIT_RND"
BOARD_KEY = "msit_publicinfo_63"

# 예산·결산(`publictSeqNo=295`)을 사전정보공표 안에서 '예산' 키워드로 한정 검색.
PUBLICT_SEQ_NO_BUDGET = 295
LIST_URL_BUDGET = (
    f"{BASE_URL}/publicinfo/detailList.do"
    "?sCode=user&mId=63&mPid=62"
    "&formMode=L&pageIndex="
    f"&publictSeqNo={PUBLICT_SEQ_NO_BUDGET}"
    "&searchSeCd=&searchMapngCd=&searchOpt=ALL&searchTxt=%EC%98%88%EC%82%B0"
)
DOWNLOAD_URL = f"{BASE_URL}/ssm/file/fileDown.do"


_PREFERRED_EXT_ORDER = (".hwpx", ".pdf", ".xlsx", ".xls", ".hwp")


# ---------------------------------------------------------------------------
# data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ListRow:
    """목록 페이지에서 추출한 1개 행."""

    publict_list_seq_no: int          # 연도별 ID (예: 12)
    title: str
    raw_date: str                     # 게시일 표기 그대로
    view_url: str                     # 상세 페이지 URL


@dataclass(frozen=True)
class _Attachment:
    """상세 페이지에서 추출한 첨부파일 후보."""

    filename: str
    ext: str                          # ".hwpx", ".pdf", ...
    form_payload: dict[str, str]      # POST /ssm/file/fileDown.do 의 body


# ---------------------------------------------------------------------------
# collector
# ---------------------------------------------------------------------------


class MsitPublicInfo63Collector:
    def collect_sync(
        self,
        *,
        max_pages: int = 2,
        max_items: int = 20,
        last_seen_list_seq_no: int | None = None,
        sleep_between_requests: float = 0.7,
    ) -> tuple[list[EconomicCollectDto], dict[str, int]]:
        _ = sleep_between_requests
        return asyncio.run(
            self.collect(
                max_pages=max_pages,
                max_items=max_items,
                last_seen_list_seq_no=last_seen_list_seq_no,
            )
        )

    async def collect(
        self,
        *,
        max_pages: int = 2,
        max_items: int = 20,
        last_seen_list_seq_no: int | None = None,
    ) -> tuple[list[EconomicCollectDto], dict[str, int]]:
        stats = {
            "fetched_rows": 0,
            "skipped_watermark": 0,
            "no_attachment": 0,
            "download_failed": 0,
            "parsed_ok": 0,
        }
        kept_rows: list[_ListRow] = []

        async with make_async_client() as client:
            for page in range(1, max_pages + 1):
                list_url = self._build_list_url(page)
                logger.info("[%s] list page=%s url=%s", BOARD_KEY, page, list_url)
                try:
                    list_html = await async_get_html(client, list_url, timeout=30.0)
                except Exception:
                    logger.exception("[%s] list page fetch failed", BOARD_KEY)
                    break

                rows = self._parse_list_rows(list_html)
                if not rows:
                    logger.info("[%s] no rows on page=%s", BOARD_KEY, page)
                    break

                stop = False
                for row in rows:
                    stats["fetched_rows"] += 1
                    if (
                        last_seen_list_seq_no is not None
                        and row.publict_list_seq_no <= last_seen_list_seq_no
                    ):
                        stats["skipped_watermark"] += 1
                        stop = True
                        break
                    kept_rows.append(row)
                    if len(kept_rows) >= max_items:
                        stop = True
                        break
                if stop:
                    break
                await asyncio.sleep(0.35)

            tmp_dir = Path(tempfile.gettempdir()) / "msit_publicinfo_63"
            tmp_dir.mkdir(parents=True, exist_ok=True)

            sem = asyncio.Semaphore(4)

            async def process_row(
                row: _ListRow,
            ) -> tuple[EconomicCollectDto, dict[str, int]]:
                async with sem:
                    part: dict[str, int] = {}
                    try:
                        view_html = await async_get_html(client, row.view_url, timeout=30.0)
                    except Exception:
                        logger.exception(
                            "[%s] view fetch failed url=%s", BOARD_KEY, row.view_url
                        )
                        return self._to_dto(row, attach=None, parsed=None), part

                    attach = self._pick_preferred_attachment(view_html)
                    if not attach:
                        part["no_attachment"] = 1
                        return self._to_dto(row, attach=None, parsed=None), part

                    local_path = await self._download_attachment(
                        client,
                        attach=attach,
                        referer=row.view_url,
                        tmp_dir=tmp_dir,
                    )
                    if not local_path:
                        part["download_failed"] = 1
                        return self._to_dto(row, attach=attach, parsed=None), part

                    parsed = await asyncio.to_thread(parse_document, local_path)
                    if not parsed.get("error"):
                        part["parsed_ok"] = 1
                    return self._to_dto(row, attach=attach, parsed=parsed), part

            dtos: list[EconomicCollectDto] = []
            for dto, part in await asyncio.gather(
                *[process_row(r) for r in kept_rows]
            ):
                dtos.append(dto)
                for k, v in part.items():
                    stats[k] += v

        logger.info("[%s] collected dtos=%s stats=%s", BOARD_KEY, len(dtos), stats)
        return dtos, stats

    # --- list page ---------------------------------------------------------

    def _build_list_url(self, page: int) -> str:
        if page <= 1:
            return LIST_URL_BUDGET
        # pageIndex 가 일반적, page 도 함께 부여 (서버 무시 키는 안전).
        sep = "&" if "?" in LIST_URL_BUDGET else "?"
        return f"{LIST_URL_BUDGET}{sep}pageIndex={page}&page={page}"

    def _parse_list_rows(self, html: str) -> list[_ListRow]:
        """목록 파싱 — 2026 개편 마크업 대응.

        실제 row 구조 (2026-05 확인):
          <div class="board_list">
              <div class="toggle">
                  ... <a onclick="javascript:fn_goView(295, 12)"> ... </a> ...
                  텍스트 패턴: "{seq_no}{제목}첨부파일{YYYY. M. D}"
              </div>
              ... (12개)
          </div>

        클릭 핸들러 첫 인자는 `publictSeqNo`(=295 고정), 두 번째가 우리가 원하는
        `publictListSeqNo`. 정규식으로 두 번째 인자를 명시적으로 캡처한다.

        레거시 `<table>/<tbody>/<tr>` 구조도 호환 유지(첨부 폴백).
        """
        soup = BeautifulSoup(html, "html.parser")
        rows: list[_ListRow] = []
        seen_seq: set[int] = set()

        # --- 1) 신규 마크업: div.board_list > div.toggle 우선 ---
        toggles = soup.select("div.board_list > div.toggle")
        if not toggles:
            toggles = soup.select("div.board_list div.toggle")
        for tg in toggles:
            row = self._parse_toggle_row(tg)
            if row and row.publict_list_seq_no not in seen_seq:
                seen_seq.add(row.publict_list_seq_no)
                rows.append(row)
        if rows:
            return rows

        # --- 2) 레거시 <table> 폴백 ---
        for sel in (
            "table.board_list tbody tr",
            "table.board tbody tr",
            "div.board_list tbody tr",
            "table tbody tr",
        ):
            items = soup.select(sel)
            if items:
                break
        else:
            items = []

        for tr in items:
            link = (
                tr.select_one("a[href*='view.do']")
                or tr.select_one("a[onclick]")
                or tr.select_one("a")
            )
            if not link:
                continue
            title = link.get_text(strip=True)
            if not title:
                continue

            list_seq = _extract_publict_list_seq_no(link, parent=tr)
            if list_seq is None or list_seq in seen_seq:
                continue

            date_cell = (
                tr.select_one("td.date")
                or tr.select_one("td.reg_date")
                or tr.select_one("span.date")
            )
            raw_date = date_cell.get_text(strip=True) if date_cell else ""

            seen_seq.add(list_seq)
            rows.append(
                _ListRow(
                    publict_list_seq_no=list_seq,
                    title=title,
                    raw_date=raw_date,
                    view_url=self._build_view_url(list_seq),
                )
            )
        return rows

    def _parse_toggle_row(self, tg: Tag) -> _ListRow | None:
        """`<div class="toggle">` 1 개 → `_ListRow`.

        - 클릭 핸들러: `fn_goView(<publictSeqNo>, <publictListSeqNo>)` 의 **두 번째 인자** 캡처.
        - 텍스트: `{seq}{title}첨부파일{YYYY. M. D}` 형태 → seq 앞자리 / 첨부파일 / 날짜를 제거하고
          가운데를 제목으로 사용.
        """
        list_seq: int | None = None
        for a in tg.find_all(["a", "button"]):
            src = (a.get("onclick") or "") + " " + (a.get("href") or "")
            m = _FN_GOVIEW_RE.search(src)
            if m:
                try:
                    list_seq = int(m.group("list_seq"))
                except ValueError:
                    continue
                break
        if list_seq is None:
            # 영역 텍스트 fallback (script 가 attr 가 아닌 다른 곳에 있을 수도)
            m = _FN_GOVIEW_RE.search(str(tg))
            if m:
                try:
                    list_seq = int(m.group("list_seq"))
                except ValueError:
                    list_seq = None
        if list_seq is None:
            return None

        text = re.sub(r"\s+", " ", tg.get_text(" ", strip=True))

        raw_date = ""
        dm = re.search(r"(20\d{2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})", text)
        if dm:
            raw_date = f"{dm.group(1)}. {int(dm.group(2))}. {int(dm.group(3))}"
            text = text[: dm.start()] + text[dm.end():]

        text = text.replace("첨부파일", "")
        text = re.sub(r"^\s*\d+\s*", "", text)  # row 앞자리 일련번호 제거
        title = text.strip()

        if not title:
            return None

        return _ListRow(
            publict_list_seq_no=list_seq,
            title=title,
            raw_date=raw_date,
            view_url=self._build_view_url(list_seq),
        )

    def _build_view_url(self, publict_list_seq_no: int) -> str:
        qs = {
            "sCode": "user",
            "mId": "63",
            "mPid": "62",
            "pageIndex": "",
            "formMode": "R",
            "referKey": f"{PUBLICT_SEQ_NO_BUDGET},{publict_list_seq_no}",
            "publictSeqNo": str(PUBLICT_SEQ_NO_BUDGET),
            "publictListSeqNo": str(publict_list_seq_no),
            "searchMapngCd": "",
            "searchSeCd": "",
            "searchOpt": "ALL",
            "searchTxt": "예산",
            "pageIndex2": "1",
        }
        return f"{BASE_URL}/publicinfo/view.do?{urlencode(qs, encoding='utf-8')}"

    # --- detail / attachment ---------------------------------------------

    def _pick_preferred_attachment(self, view_html: str) -> _Attachment | None:
        """`<ul class="down_file">` 의 li 중 우선순위 확장자를 선택."""
        soup = BeautifulSoup(view_html, "html.parser")
        ul = soup.select_one("ul.down_file") or soup.select_one("ul.attach_list")
        if not ul:
            # 폴백: 전체 페이지에서 onclick="fnFileDown(...)" 패턴 찾기
            return _attachment_from_any_anchor(soup)

        attachments: list[_Attachment] = []
        for li in ul.select("li"):
            a = li.find("a")
            if not a:
                continue
            filename = li.get_text(separator=" ", strip=True)
            ext = _extension_of(filename)
            payload = _payload_from_anchor(a)
            if not payload:
                continue
            attachments.append(
                _Attachment(filename=filename, ext=ext, form_payload=payload)
            )

        if not attachments:
            return None

        for ext in _PREFERRED_EXT_ORDER:
            for att in attachments:
                if att.ext == ext:
                    return att
        # 알 수 없는 확장자: 첫 번째 반환
        return attachments[0]

    async def _download_attachment(
        self,
        client: httpx.AsyncClient,
        *,
        attach: _Attachment,
        referer: str,
        tmp_dir: Path,
    ) -> Path | None:
        headers = {
            **DEFAULT_HEADERS,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": referer,
            "Origin": BASE_URL,
            "Accept": "*/*",
        }
        try:
            async with client.stream(
                "POST",
                DOWNLOAD_URL,
                data=attach.form_payload,
                headers=headers,
                timeout=httpx.Timeout(60.0),
            ) as resp:
                resp.raise_for_status()
                cd_filename = _filename_from_content_disposition(
                    resp.headers.get("Content-Disposition")
                )
                filename = (
                    cd_filename
                    or attach.filename
                    or f"msit_{int(time.time())}{attach.ext or '.bin'}"
                )
                filename = _sanitize_filename(filename)
                local_path = tmp_dir / filename
                try:
                    with local_path.open("wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                            if chunk:
                                f.write(chunk)
                except Exception:
                    logger.exception("[%s] write local file failed", BOARD_KEY)
                    return None
                return local_path
        except Exception:
            logger.exception(
                "[%s] download POST failed payload=%s",
                BOARD_KEY,
                attach.form_payload,
            )
            return None

    # --- DTO ---------------------------------------------------------------

    def _to_dto(
        self,
        row: _ListRow,
        *,
        attach: _Attachment | None,
        parsed: dict[str, Any] | None,
    ) -> EconomicCollectDto:
        raw_metadata: dict[str, Any] = {
            "board_key": BOARD_KEY,
            "filter": {
                "search_text": "예산",
                "publict_seq_no": PUBLICT_SEQ_NO_BUDGET,
            },
            "publict_list_seq_no": row.publict_list_seq_no,
            "raw_date": row.raw_date,
            "is_signal": False,  # 본 보드는 '집행 팩트' 성격
            "collected_via": "msit-publicinfo-63-crawler",
        }
        if attach:
            raw_metadata["attachment"] = {
                "filename": attach.filename,
                "ext": attach.ext,
            }
        if parsed:
            # `full_text` 가 너무 크면 적재량 폭주 → 30KB 컷 (Silver 가 chunking)
            full_text = parsed.get("full_text") or ""
            raw_metadata["full_text"] = full_text[:30000]
            raw_metadata["full_text_length"] = len(full_text)
            raw_metadata["extraction_method"] = parsed.get("extraction_method")
            if parsed.get("page_count"):
                raw_metadata["page_count"] = parsed["page_count"]
            if parsed.get("section_count"):
                raw_metadata["hwpx_section_count"] = parsed["section_count"]
            if parsed.get("error"):
                raw_metadata["parse_error"] = parsed["error"]

        return EconomicCollectDto(
            source_type=SOURCE_TYPE,
            source_url=row.view_url,
            raw_title=row.title[:500],
            investor_name="과학기술정보통신부",
            target_company_or_fund=None,
            investment_amount=None,
            currency="KRW",
            raw_metadata=raw_metadata,
            published_at=parse_kst_date(row.raw_date),
        )


# ---------------------------------------------------------------------------
# helpers (module-private)
# ---------------------------------------------------------------------------


# 신규 마크업: `fn_goView(<publictSeqNo>, <publictListSeqNo>)` → **두 번째 인자**가 정답.
_FN_GOVIEW_RE = re.compile(
    r"fn_?goView\s*\(\s*(?P<seq>\d+)\s*,\s*(?P<list_seq>\d+)\s*\)"
)

_PUBLIC_LIST_SEQ_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"publictListSeqNo=(\d+)"),
    re.compile(r"publictListSeqNo['\"]?\s*[:=]\s*['\"]?(\d+)"),
    # `fn_goView(295, 12)` 형태 — 두 번째 인자(list_seq) 캡처
    re.compile(r"fn_?goView\s*\(\s*\d+\s*,\s*(\d+)\s*\)"),
    re.compile(r"fnView\(\s*['\"]?(\d+)['\"]?"),
    # 단일 인자만 받는 레거시 `goView(N)` 도 호환 (publictSeqNo 와 혼동 위험 있음)
    re.compile(r"(?<!_)goView\(\s*['\"]?(\d+)['\"]?\s*\)"),
)


def _extract_publict_list_seq_no(tag: Tag, *, parent: Tag) -> int | None:
    """앵커/부모 행에서 `publictListSeqNo` 정수 추출."""
    # 1) href / onclick
    candidates: list[str] = []
    for src in (tag.get("href"), tag.get("onclick")):
        if src:
            candidates.append(str(src))
    # 2) data-*
    for attr_key, attr_val in tag.attrs.items():
        if attr_key.startswith("data-") and attr_val:
            candidates.append(str(attr_val))

    # 3) 부모 tr 의 onclick / hidden input (서버 측 폼)
    for inp in parent.select("input[type='hidden']"):
        name = (inp.get("name") or "").lower()
        if "publictlistseqno" in name.replace("_", ""):
            val = inp.get("value")
            if val and val.isdigit():
                return int(val)

    for text in candidates:
        for pat in _PUBLIC_LIST_SEQ_PATTERNS:
            m = pat.search(text)
            if m:
                try:
                    return int(m.group(1))
                except ValueError:
                    pass
    return None


def _payload_from_anchor(a: Tag) -> dict[str, str] | None:
    """첨부 `<a>` → POST `/ssm/file/fileDown.do` 폼 payload.

    2026 개편 마크업 기준 — `<form id="fileForm">` 의 hidden 이름이 표준:
      - `atchFileNo` : 첨부 파일 그룹 ID (예: 52418)
      - `fileOrd`   : 동일 그룹 내 순번 (예: 1=hwp, 2=hwpx)
      - `fileBtn`   : 폼 hidden (빈 값)

    실제 다운로드 트리거 onclick:
      - `fn_download('52418','1')`            ← 본 다운로드 함수
      - `getExtension_path('52418', '1')`     ← 확장자 체크 후 동일 키로 다운로드
    """
    src = (a.get("onclick") or "") + " " + (a.get("href") or "")

    # 후보 1) fn_download / getExtension_path 두 인자 (현행)
    m = re.search(
        r"(?:fn_?download|getExtension_path)\s*\(\s*['\"]?(\d+)['\"]?\s*,\s*['\"]?(\d+)['\"]?\s*\)",
        src,
    )
    if m:
        return {
            "atchFileNo": m.group(1),
            "fileOrd": m.group(2),
            "fileBtn": "",
        }

    # 후보 2) 두 개 따옴표 인자 (레거시 fnFileDown 등 — 첫 인자가 숫자 아닌 ID 일 수도)
    m = re.search(
        r"\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]?(\d+)['\"]?\s*\)", src
    )
    if m:
        first = m.group(1)
        # 첫 인자가 순수 숫자면 신규 키 매핑, 아니면 레거시 키 매핑
        if first.isdigit():
            return {"atchFileNo": first, "fileOrd": m.group(2), "fileBtn": ""}
        return {"attachFileId": first, "attachFileSeq": m.group(2)}

    # 후보 3) href 쿼리스트링 직접 노출
    href = a.get("href") or ""
    if "attachFileId" in href or "atchFileNo" in href:
        from urllib.parse import parse_qs, urlparse

        qs = parse_qs(urlparse(href).query)
        afid = (
            (qs.get("atchFileNo") or [""])[0]
            or (qs.get("attachFileId") or [""])[0]
        )
        afseq = (
            (qs.get("fileOrd") or [""])[0]
            or (qs.get("attachFileSeq") or [""])[0]
            or (qs.get("fileSeq") or [""])[0]
        )
        if afid:
            return {"atchFileNo": afid, "fileOrd": afseq or "1", "fileBtn": ""}

    # 후보 4) data-* 속성
    afid = a.get("data-file-id") or a.get("data-attach-id") or a.get("data-atch-file-no")
    afseq = a.get("data-file-seq") or a.get("data-seq") or a.get("data-file-ord")
    if afid:
        return {
            "atchFileNo": str(afid),
            "fileOrd": str(afseq or "1"),
            "fileBtn": "",
        }
    return None


def _attachment_from_any_anchor(soup: BeautifulSoup) -> _Attachment | None:
    """`down_file` ul 이 없을 때 다운로드 핸들을 가진 임의 a 태그 폴백."""
    _DOWNLOAD_HINTS = ("fn_download", "fileDown", "attachFileId", "atchFileNo", "getExtension_path")
    for a in soup.select("a"):
        src = (a.get("onclick") or "") + " " + (a.get("href") or "")
        if not any(k in src for k in _DOWNLOAD_HINTS):
            continue
        payload = _payload_from_anchor(a)
        if not payload:
            continue
        filename = a.get_text(separator=" ", strip=True) or ""
        return _Attachment(
            filename=filename,
            ext=_extension_of(filename),
            form_payload=payload,
        )
    return None


_EXT_RE = re.compile(r"\.([A-Za-z0-9]{1,5})(?:\W|$)")
# 정규식으로 못 잡는 경우(파일명에 마침표가 없거나, 확장자가 토큰 형태로 분리된 경우)
# 의 폴백 — 'HWPX', '한글', 'PDF', '엑셀' 등의 한국어/약어 힌트.
_EXT_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("hwpx", ".hwpx"),
    ("pdf", ".pdf"),
    ("xlsx", ".xlsx"),
    (".xls", ".xls"),
    ("hwp", ".hwp"),  # 구버전 — 본 파서는 미지원이지만 분류만 정확히.
    ("한글", ".hwpx"),
    ("엑셀", ".xlsx"),
)


def _extension_of(filename: str) -> str:
    if not filename:
        return ""
    m = _EXT_RE.search(filename)
    if m:
        return f".{m.group(1).lower()}"
    # 마침표 없이 확장자 키워드만 있는 케이스(파일명 잘림 등) 폴백.
    low = filename.lower()
    for needle, ext in _EXT_KEYWORDS:
        if needle in low:
            return ext
    return ""


_DISPOSITION_RE = re.compile(
    r"filename\*=UTF-8''(?P<q>[^;]+)|filename=\"?(?P<u>[^\";]+)\"?",
    re.IGNORECASE,
)


def _filename_from_content_disposition(value: str | None) -> str | None:
    if not value:
        return None
    m = _DISPOSITION_RE.search(value)
    if not m:
        return None
    quoted = m.group("q")
    if quoted:
        from urllib.parse import unquote

        return unquote(quoted)
    return m.group("u")


_BAD_FILENAME_RE = re.compile(r"[\\/:*?\"<>|\r\n\t]")


def _sanitize_filename(name: str) -> str:
    name = _BAD_FILENAME_RE.sub("_", name).strip()
    return name[:200] or f"download_{int(time.time())}.bin"


# 외부 노출용
__all__ = [
    "MsitPublicInfo63Collector",
    "SOURCE_TYPE",
    "BOARD_KEY",
]

# Make sure urljoin is referenced (silence flake8 if used later)
_ = urljoin
