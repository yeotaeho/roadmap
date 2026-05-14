"""과기부(MSIT) 공통 HTTP/파싱 유틸 — `mId=63`, `mId=307`, `mId=311` 공용.

의도:
  - `requests.Session` 으로 동기 GET (`get_html`) — 레거시·스크립트 호환.
  - `httpx.AsyncClient` + `async_get_html` — MSIT 비동기 컬렉터용 동일 재시도 정책.
  - 브라우저 와 동일한 User-Agent / Accept-Language 헤더.
  - 게시판 HTML 셀렉터가 살짝 다를 수 있어 **다중 셀렉터**를 시도하는 헬퍼 제공.
  - 날짜 파서는 `2026.05.13` / `2026-05-13` / `2026/05/13` 등 흔한 한국 표기 모두 지원.

본 모듈은 **수집기(collector) 내부 전용**이며 외부 노출은 하지 않는다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import httpx
import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


BASE_URL = "https://www.msit.go.kr"
_KST = timezone(timedelta(hours=9))

# 브라우저로 위장 — 정부 사이트 일부는 표준 UA(Python/aiohttp 등)를 차단함.
DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


def make_session() -> requests.Session:
    """`Referer`/`Origin`/`Cookie` 유지가 필요한 multi-step 흐름용 세션."""
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    return s


def get_html(
    session: requests.Session,
    url: str,
    *,
    timeout: int = 30,
    retries: int = 3,
    backoff_base: float = 0.6,
) -> str:
    """`raise_for_status` 가 활성화된 GET. 본문 인코딩 보정 + **재시도 + 지수 백오프**.

    MSIT 사이트는 TLS 핸드셰이크 중 간헐적으로 ConnectionReset(10054)을 던지므로
    네트워크 계열 예외에 한해 짧은 백오프 후 최대 `retries` 회 재시도한다.
    HTTP 4xx/5xx (raise_for_status) 는 의미 있는 응답이므로 그대로 전파.
    """
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = session.get(url, timeout=timeout, allow_redirects=True)
            resp.raise_for_status()
            if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
                resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except (requests.ConnectionError, requests.Timeout) as e:
            last_exc = e
            if attempt >= retries:
                break
            wait = backoff_base * (2 ** attempt)
            logger.warning(
                "MSIT GET 재시도 attempt=%s/%s wait=%.2fs url=%s err=%s",
                attempt + 1,
                retries,
                wait,
                url,
                e.__class__.__name__,
            )
            import time as _t

            _t.sleep(wait)
    assert last_exc is not None
    raise last_exc


def make_async_client(**kwargs: Any) -> httpx.AsyncClient:
    """MSIT 비동기 수집용 `httpx.AsyncClient` — 기본 헤더·리다이렉트."""
    kw: dict[str, Any] = {
        "headers": dict(DEFAULT_HEADERS),
        "follow_redirects": True,
        "timeout": httpx.Timeout(30.0),
    }
    kw.update(kwargs)
    return httpx.AsyncClient(**kw)


async def async_get_html(
    client: httpx.AsyncClient,
    url: str,
    *,
    timeout: float = 30.0,
    retries: int = 3,
    backoff_base: float = 0.6,
) -> str:
    """비동기 GET — `get_html` 과 동일한 재시도·지수 백오프(HTTPX 네트워크 예외)."""
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = await client.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except (httpx.ConnectError, httpx.ReadError, httpx.WriteError, httpx.TimeoutException) as e:
            last_exc = e
            if attempt >= retries:
                break
            wait = backoff_base * (2**attempt)
            logger.warning(
                "MSIT async GET 재시도 attempt=%s/%s wait=%.2fs url=%s err=%s",
                attempt + 1,
                retries,
                wait,
                url,
                e.__class__.__name__,
            )
            await asyncio.sleep(wait)
    assert last_exc is not None
    raise last_exc


# ---------------------------------------------------------------------------
# date helpers
# ---------------------------------------------------------------------------


_DATE_RE = re.compile(
    r"(?P<y>20\d{2})\s*[.\-/년]\s*(?P<m>\d{1,2})\s*[.\-/월]\s*(?P<d>\d{1,2})"
)


def parse_kst_date(text: str) -> datetime | None:
    """`2026.05.13` / `2026-05-13` / `2026년 5월 13일` 등을 KST datetime 으로."""
    if not text:
        return None
    m = _DATE_RE.search(text)
    if not m:
        return None
    try:
        return datetime(
            int(m.group("y")),
            int(m.group("m")),
            int(m.group("d")),
            tzinfo=_KST,
        )
    except ValueError:
        return None


def extract_year(text: str) -> int | None:
    dt = parse_kst_date(text)
    return dt.year if dt else None


# ---------------------------------------------------------------------------
# BBS list page helpers (mId=307, mId=311)
# ---------------------------------------------------------------------------


# 게시판 페이지는 표(<table>) 구조가 일반적. 부서/페이지 개편에 견디기 위해
# 가능성 있는 셀렉터를 순차 시도.
_LIST_ROW_SELECTORS: tuple[str, ...] = (
    # MSIT 일부 페이지는 <tbody> 없이 <tr> 만 두는 경우가 있어 tbody 없는 셀렉터를 먼저 둔다.
    "table.board_list tr",
    "table.board_list tbody tr",
    "table.board tbody tr",
    "div.board_list table tr",
    "div.board_list table tbody tr",
    "table tbody tr",  # 최후 폴백 — 헤더 행도 포함될 수 있어 link 유무로 후처리 필터
)

_TITLE_LINK_SELECTORS: tuple[str, ...] = (
    "td.title a",
    "td.subject a",
    "td.tit a",
    "a.title",
    "a",
)

_DATE_CELL_SELECTORS: tuple[str, ...] = (
    "td.date",
    "td.reg_date",
    "span.date",
    "td.day",
)


def _first_match(root: Tag, selectors: tuple[str, ...]) -> Tag | None:
    for sel in selectors:
        found = root.select_one(sel)
        if found:
            return found
    return None


def parse_bbs_list_rows(html: str) -> list[dict[str, Any]]:
    """`/bbs/list.do` 결과 페이지 → 게시물 dict 리스트.

    Returns:
        list of {title, url, published_at(datetime|None), published_year(int|None), raw_date}.
        제목 링크가 없는 행(헤더 등)은 자동 제외.
    """
    soup = BeautifulSoup(html, "html.parser")
    rows: list[Tag] = []
    for sel in _LIST_ROW_SELECTORS:
        rows = soup.select(sel)
        if rows:
            break

    out: list[dict[str, Any]] = []
    for tr in rows:
        if tr.find_parent("thead"):
            continue
        link = _first_match(tr, _TITLE_LINK_SELECTORS)
        if not link:
            continue
        title = link.get_text(strip=True)
        href = link.get("href", "")
        # 자바스크립트 href("javascript:fnView('123')") 처리
        post_url = _normalize_post_url(href, title_tag=link, base=BASE_URL)
        if not title or not post_url:
            continue

        date_cell = _first_match(tr, _DATE_CELL_SELECTORS)
        raw_date = date_cell.get_text(strip=True) if date_cell else ""

        published_at = parse_kst_date(raw_date)
        ntt_vals = parse_qs(urlparse(post_url).query).get("nttSeqNo")
        ntt_seq_no: int | None = None
        if ntt_vals and str(ntt_vals[0]).isdigit():
            ntt_seq_no = int(ntt_vals[0])
        out.append({
            "title": title,
            "url": post_url,
            "published_at": published_at,
            "published_year": published_at.year if published_at else None,
            "raw_date": raw_date,
            "ntt_seq_no": ntt_seq_no,
        })
    return out


def _normalize_post_url(href: str, *, title_tag: Tag, base: str) -> str | None:
    """게시판 a[href] 정규화.

    1) 일반 링크: `/bbs/view.do?...` → 절대 URL 변환.
    2) JS 링크 : `javascript:fnView('1234')` → data-* / onclick 에서 ID 추출 후 URL 재구성.
    3) 그 외   : None (스킵).
    """
    href = (href or "").strip()
    if href and not href.lower().startswith("javascript"):
        return urljoin(base, href)

    # JavaScript 링크: data 속성 또는 onclick 에서 ID 추출
    for attr in ("data-nttid", "data-ntt-id", "data-id", "data-seq", "data-no"):
        nid = title_tag.get(attr)
        if nid:
            return _build_view_url_from_id(title_tag, base, nid)

    onclick = title_tag.get("onclick") or href
    m = re.search(r"\(\s*['\"]?(\d+)['\"]?", onclick)
    if m:
        return _build_view_url_from_id(title_tag, base, m.group(1))

    return None


def _build_view_url_from_id(title_tag: Tag, base: str, ntt_id: str) -> str:
    """JS 기반 게시판의 상세 URL 재구성.

    MSIT bbs 는 일반적으로 `/bbs/view.do?sCode=user&mId=...&mPid=...&bbsSeqNo=...&nttSeqNo=...`
    형식. 페이지 메타에서 `mId`/`mPid` 추정이 어려우니, 상위 form/script 에서 hidden 값을
    가져오는 게 가장 안전 → 본 함수는 최소한의 baseline URL 만 반환하고,
    실제 mId/mPid 결합은 collector 가 알고 있는 board_base_url 의 쿼리스트링을 우선 사용.
    """
    return f"{base}/bbs/view.do?nttSeqNo={ntt_id}"


def find_pagination_anchor(html: str) -> int | None:
    """페이지네이션에서 `마지막 페이지` 번호를 추출 (가능한 경우)."""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a"):
        href = a.get("href", "")
        m = re.search(r"page(?:Index)?=(\d+)", href)
        if m:
            try:
                last = int(m.group(1))
                # 마지막 페이지로 가는 링크가 여러 개라 가장 큰 값을 채택
                return max(last, 1)
            except ValueError:
                continue
    return None


def query_param(url: str, key: str) -> str | None:
    qs = parse_qs(urlparse(url).query)
    vals = qs.get(key)
    return vals[0] if vals else None


def today_kst() -> date:
    return datetime.now(tz=_KST).date()


# ---------------------------------------------------------------------------
# MSIT 신규 게시판 (div + JS 하이드레이션 목록) — fn_detail ID + view.do 상세
# ---------------------------------------------------------------------------

# 첨부파일명 앞의 관보/보도 일자(YYMMDD) — 예: "260514 조간 ... .hwpx"
_ATTACH_YYMMDD_BEFORE_FILE_RE = re.compile(
    r"(?<![0-9])(?P<yymmdd>[0-9]{6})\s+[^\n]{0,40}\.(?:hwpx|hwp|pdf|zip)\b",
    re.IGNORECASE,
)


def extract_action_form_params(html: str) -> dict[str, str]:
    """`form[name=actionForm]` hidden 값 — `view.do` GET 쿼리 재구성용."""
    soup = BeautifulSoup(html, "html.parser")
    form = soup.select_one("form[name=actionForm]")
    out: dict[str, str] = {}
    if not form:
        return out
    for inp in form.select("input"):
        name = inp.get("name")
        if not name:
            continue
        out[name] = inp.get("value") or ""
    return out


def extract_fn_detail_ntt_ids(html: str, *, max_ids: int = 500) -> list[int]:
    """`#result .board_list` 영역의 `fn_detail(숫자)` 를 **문서 순서대로** 중복 제거 추출."""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("#result .board_list") or soup
    chunk = str(root)
    seen: set[int] = set()
    out: list[int] = []
    for m in re.finditer(r"fn_detail\(\s*(\d+)\s*\)", chunk):
        n = int(m.group(1))
        if n in seen:
            continue
        seen.add(n)
        out.append(n)
        if len(out) >= max_ids:
            break
    return out


def build_msit_bbs_view_url(form_params: dict[str, str], ntt_seq_no: int) -> str:
    """`/bbs/view.do` 절대 URL (GET). `form_params` 에 `bbsSeqNo`·`mId` 등이 포함되어야 함."""
    params = {**form_params, "nttSeqNo": str(ntt_seq_no)}
    return f"{BASE_URL}/bbs/view.do?{urlencode(params)}"


def parse_msit_bbs_view_summary(html: str) -> tuple[str, datetime | None, str]:
    """상세 `view.do` HTML 에서 제목·등록일(추정)·raw_date 문자열.

    등록일 메타가 없는 경우가 많아 **첨부파일명 선두 YYMMDD** 로 KST 자정 근사치를 만든다.
    """
    soup = BeautifulSoup(html, "html.parser")
    bv = soup.select_one("div.board_view")

    title = ""
    h2 = soup.select_one("div.board_view h2")
    if h2:
        title = h2.get_text(strip=True)
    elif bv:
        first_line = bv.get_text("\n", strip=True).split("\n")[0].strip()
        title = first_line[:500]

    hay = bv.get_text("\n", strip=True) if bv else ""
    raw_date = ""
    published_at: datetime | None = None

    m = _ATTACH_YYMMDD_BEFORE_FILE_RE.search(hay)
    if m:
        six = m.group("yymmdd")
        yy, mm, dd = int(six[:2]), int(six[2:4]), int(six[4:6])
        year = 2000 + yy if yy < 85 else 1900 + yy
        try:
            published_at = datetime(year, mm, dd, tzinfo=_KST)
            raw_date = f"{year:04d}.{mm:02d}.{dd:02d}"
        except ValueError:
            published_at = None

    if published_at is None:
        published_at = parse_kst_date(hay[:3000])
        if published_at:
            raw_date = published_at.strftime("%Y.%m.%d")

    return title, published_at, raw_date


# ---------------------------------------------------------------------------
# Inline 검색 JSON (mId=307 보도자료) — `getSerachData()` 본문 안에 그대로 박혀 옴
# ---------------------------------------------------------------------------

# /bbs/list.do?searchOpt=NTT_SJ&searchTxt=... 응답 HTML 안:
#   function getSerachData() {
#       let data = {"result":{"total_count":N,"rows":[ {fields:{ntt_sj,url,pstg_bgng_dt,...}} ]}};
#       ...
#   }
# 검색어가 없으면 `let data = "";` 로 비어옴.
_INLINE_SEARCH_DATA_RE = re.compile(
    r"function\s+getSerachData\s*\(\s*\)\s*\{\s*let\s+data\s*=\s*(?P<payload>\{.*?\}|\"\"|'');",
    re.DOTALL,
)

_HIGHLIGHT_TAG_RE = re.compile(r"<(b|strong|em)>(.*?)</\1>", re.IGNORECASE | re.DOTALL)
_INLINE_DT_RE = re.compile(
    r"^(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})(?:\s+(?P<H>\d{2}):(?P<M>\d{2})(?::(?P<S>\d{2}))?)?$"
)


def strip_highlight(text: str | None) -> str:
    """검색 결과 강조 태그(`<b>...</b>` 등)를 제거하고 공백을 정리."""
    if not text:
        return ""
    cleaned = _HIGHLIGHT_TAG_RE.sub(r"\2", text)
    cleaned = cleaned.replace("&amp;", "&").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_inline_search_result(html: str) -> dict[str, Any] | None:
    """`/bbs/list.do?searchOpt=...&searchTxt=...` 응답에서 인라인 검색 JSON 추출.

    Returns:
        `{"total_count": int, "rows": [...]}` 또는 None (인라인 블록이 없거나 파싱 실패).
        검색어 없이 호출되어 `let data = ""` 인 경우 `{"total_count":0, "rows":[]}` 반환.
    """
    m = _INLINE_SEARCH_DATA_RE.search(html)
    if not m:
        return None
    raw = m.group("payload")
    if raw in ('""', "''"):
        return {"total_count": 0, "rows": []}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.debug("MSIT inline JSON 파싱 실패")
        return None
    if isinstance(data, dict) and "result" in data and isinstance(data["result"], dict):
        return data["result"]
    if isinstance(data, dict) and "rows" in data:
        return data
    return None


def parse_inline_published_at(raw: str | None) -> datetime | None:
    """`pstg_bgng_dt` ("YYYY-MM-DD" / "YYYY-MM-DD HH:MM:SS") → KST datetime."""
    if not raw:
        return None
    m = _INLINE_DT_RE.match(raw.strip())
    if not m:
        return parse_kst_date(raw)
    y, mo, d = int(m.group("y")), int(m.group("m")), int(m.group("d"))
    H = int(m.group("H") or 0)
    M = int(m.group("M") or 0)
    S = int(m.group("S") or 0)
    try:
        return datetime(y, mo, d, H, M, S, tzinfo=_KST)
    except ValueError:
        return None


def normalize_inline_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """인라인 JSON row → 우리가 다룰 게시물 dict 로 정규화.

    Returns:
        {title, url, published_at, published_year, raw_date,
         department, telno, author, has_attach, snippet, sort_date, location}
    """
    if not isinstance(row, dict):
        return None
    fields = row.get("fields") or {}
    title = strip_highlight(fields.get("ntt_sj"))
    url = strip_highlight(fields.get("url"))
    if not title or not url:
        return None
    abs_url = urljoin(BASE_URL, url)

    pstg = (fields.get("pstg_bgng_dt") or "").strip()
    published_at = parse_inline_published_at(pstg)

    # sortkey 가 더 정확한 등록일을 줄 때가 있어 보조로 사용
    sort_date = None
    sk = row.get("sortkey")
    if isinstance(sk, list) and sk:
        sort_date = strip_highlight(str(sk[0]))

    if published_at is None and sort_date:
        published_at = parse_inline_published_at(sort_date)

    ntt_vals = parse_qs(urlparse(abs_url).query).get("nttSeqNo")
    ntt_seq_no: int | None = None
    if ntt_vals and str(ntt_vals[0]).isdigit():
        ntt_seq_no = int(ntt_vals[0])

    return {
        "title": title,
        "url": abs_url,
        "published_at": published_at,
        "published_year": published_at.year if published_at else None,
        "raw_date": pstg or sort_date or "",
        "ntt_seq_no": ntt_seq_no,
        "department": strip_highlight(fields.get("chrg_dept_nm")),
        "telno": strip_highlight(fields.get("telno")),
        "author": strip_highlight(fields.get("ntcr")),
        "has_attach": (fields.get("atch_file_yn") or "").upper() == "Y",
        "snippet": strip_highlight(fields.get("ntt_cn")),
        "sort_date": sort_date,
        "menu_path": strip_highlight(fields.get("menu_path")),
    }


def parse_inline_search_rows(html: str) -> tuple[list[dict[str, Any]], int | None]:
    """인라인 JSON 으로부터 정규화된 row 목록과 total_count 를 반환."""
    payload = extract_inline_search_result(html)
    if not payload:
        return [], None
    rows = payload.get("rows") or []
    out: list[dict[str, Any]] = []
    for r in rows:
        norm = normalize_inline_row(r)
        if norm:
            out.append(norm)
    return out, payload.get("total_count")
