"""정부 부처 PDF/Excel 문서 수집 Probe.

목적:
  1) 기재부·과기부 게시판 HTML 구조 파악
  2) 첨부파일 다운로드 가능 여부 확인
  3) pdfplumber/pandas로 텍스트 추출 품질 검증

사전 조건:
  pip install aiohttp beautifulsoup4 pdfplumber pandas openpyxl lxml

실행 (backend 디렉터리에서):

  python scripts/govt_docs_probe.py

환경변수:
  GOVT_PROBE_DEPT     기재부(moef) 또는 과기부(msit), 기본 moef
  GOVT_PROBE_PAGES    크롤링할 게시판 페이지 수, 기본 1
  GOVT_PROBE_DOWNLOAD 파일 다운로드 여부 (1=예, 0=아니오), 기본 1
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def _safe_import() -> tuple[Any, ...]:
    """선택적 import (설치 안 된 경우 경고)."""
    try:
        import aiohttp
        from bs4 import BeautifulSoup
        import pdfplumber
        import pandas as pd

        return aiohttp, BeautifulSoup, pdfplumber, pd
    except ImportError as e:
        print(f"❌ 필수 패키지 미설치: {e}")
        print("   pip install aiohttp beautifulsoup4 pdfplumber pandas openpyxl lxml")
        sys.exit(1)


aiohttp, BeautifulSoup, pdfplumber, pd = _safe_import()


# ============================================================================
# 게시판 URL 및 키워드 정의
# ============================================================================

MOEF_BOARD_URL = (
    "https://www.moef.go.kr/nw/nes/detailNesDtaView.do"
    "?searchBbsId1=MOSFBBS_000000000028&currentPage={page}"
)
MOEF_KEYWORDS = ["예산안", "재정운용계획", "경제정책방향", "세법개정안"]

MSIT_BOARD_URL = "https://www.msit.go.kr/bbs/list.do?sCode=user&mId=113&mPid=112&page={page}"
MSIT_KEYWORDS = ["R&D 예산", "과학기술", "연구개발", "ICT 예산", "시행계획"]


# ============================================================================
# 게시판 크롤링
# ============================================================================


async def fetch_moef_board(page: int = 1) -> list[dict]:
    """기재부 보도자료 게시판 크롤링."""
    url = MOEF_BOARD_URL.format(page=page)
    print(f"\n[MOEF] 게시판 URL: {url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                print(f"  ❌ HTTP {resp.status}")
                return []
            html = await resp.text()

    soup = BeautifulSoup(html, "html.parser")

    # 게시판 구조 분석 (기재부는 table.board_list 사용)
    items = soup.select("table.board_list tbody tr")
    print(f"  → 게시물 {len(items)}건 발견")

    posts = []
    for item in items:
        title_tag = item.select_one("td.title a") or item.select_one("td a")
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        link_href = title_tag.get("href", "")

        # 상대 경로 처리
        if link_href.startswith("/"):
            link = "https://www.moef.go.kr" + link_href
        elif link_href.startswith("http"):
            link = link_href
        else:
            link = "https://www.moef.go.kr/" + link_href

        date_tag = item.select_one("td.date")
        date = date_tag.get_text(strip=True) if date_tag else ""

        # 키워드 필터링
        if not any(kw in title for kw in MOEF_KEYWORDS):
            continue

        posts.append(
            {
                "title": title,
                "url": link,
                "published_at": date,
                "dept": "기획재정부",
            }
        )

    return posts


async def fetch_msit_board(page: int = 1) -> list[dict]:
    """과기부 보도자료 게시판 크롤링."""
    url = MSIT_BOARD_URL.format(page=page)
    print(f"\n[MSIT] 게시판 URL: {url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                print(f"  ❌ HTTP {resp.status}")
                return []
            html = await resp.text()

    soup = BeautifulSoup(html, "html.parser")

    # 과기부는 div.board_list > ul > li 구조
    items = soup.select("div.board_list ul li") or soup.select("table tbody tr")
    print(f"  → 게시물 {len(items)}건 발견")

    posts = []
    for item in items:
        title_tag = item.select_one("a")
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        link_href = title_tag.get("href", "")

        if link_href.startswith("/"):
            link = "https://www.msit.go.kr" + link_href
        elif link_href.startswith("http"):
            link = link_href
        else:
            link = "https://www.msit.go.kr/" + link_href

        date_tag = item.select_one("span.date") or item.select_one("td.date")
        date = date_tag.get_text(strip=True) if date_tag else ""

        # 키워드 필터링
        if not any(kw in title for kw in MSIT_KEYWORDS):
            continue

        posts.append(
            {
                "title": title,
                "url": link,
                "published_at": date,
                "dept": "과학기술정보통신부",
            }
        )

    return posts


# ============================================================================
# 첨부파일 다운로드
# ============================================================================


async def download_attachments(post_url: str, dept: str) -> list[Path]:
    """게시물 상세 페이지에서 첨부파일 다운로드."""
    print(f"\n[DOWNLOAD] {post_url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(post_url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                print(f"  ❌ HTTP {resp.status}")
                return []
            html = await resp.text()

    soup = BeautifulSoup(html, "html.parser")

    # 첨부파일 링크 찾기 (부처별로 셀렉터가 다를 수 있음)
    file_links = (
        soup.select("div.attach a")
        or soup.select("div.file_list a")
        or soup.select("ul.file a")
    )

    if not file_links:
        print("  ⚠️  첨부파일 링크를 찾을 수 없음")
        return []

    print(f"  → 첨부파일 {len(file_links)}개 발견")

    downloaded_files = []
    tmp_dir = Path(tempfile.gettempdir()) / "govt_docs_probe"
    tmp_dir.mkdir(exist_ok=True)

    for link in file_links[:3]:  # 최대 3개만 다운로드 (Probe 용도)
        file_url_raw = link.get("href", "")

        # 상대 경로 처리
        if file_url_raw.startswith("/"):
            if dept == "기획재정부":
                file_url = "https://www.moef.go.kr" + file_url_raw
            else:
                file_url = "https://www.msit.go.kr" + file_url_raw
        elif file_url_raw.startswith("http"):
            file_url = file_url_raw
        else:
            print(f"  ⚠️  알 수 없는 URL 형식: {file_url_raw}")
            continue

        file_name = link.get_text(strip=True) or Path(file_url).name

        # 확장자 필터링
        if not any(file_name.endswith(ext) for ext in [".pdf", ".xlsx", ".xls", ".hwp"]):
            print(f"  ⏭️  스킵 (비대상 파일): {file_name}")
            continue

        # 파일명 정리 (특수문자 제거)
        safe_file_name = re.sub(r'[<>:"/\\|?*]', "_", file_name)
        local_path = tmp_dir / safe_file_name

        # 다운로드
        try:
            async with aiohttp.ClientSession() as dl_session:
                async with dl_session.get(
                    file_url, headers=headers, timeout=aiohttp.ClientTimeout(total=60)
                ) as file_resp:
                    if file_resp.status == 200:
                        local_path.write_bytes(await file_resp.read())
                        print(
                            f"  ✅ 다운로드: {file_name} ({local_path.stat().st_size / 1024:.1f} KB)"
                        )
                        downloaded_files.append(local_path)
                    else:
                        print(f"  ❌ 다운로드 실패 (HTTP {file_resp.status}): {file_name}")
        except Exception as e:
            print(f"  ❌ 다운로드 예외: {file_name} — {e}")

    return downloaded_files


# ============================================================================
# 파일 파싱
# ============================================================================


def parse_pdf(pdf_path: Path) -> dict:
    """pdfplumber로 PDF 텍스트 추출."""
    print(f"\n[PARSE PDF] {pdf_path.name}")

    try:
        full_text = []

        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
            print(f"  → 총 {page_count} 페이지")

            for i, page in enumerate(pdf.pages[:5], start=1):  # 최대 5페이지만 (Probe)
                text = page.extract_text()
                if text:
                    full_text.append(text)
                    print(f"  [페이지 {i}] {len(text)} 자 추출")
                else:
                    print(f"  [페이지 {i}] ⚠️  텍스트 없음 (스캔 이미지일 수 있음)")

        full_text_str = "\n\n".join(full_text)

        return {
            "file_name": pdf_path.name,
            "page_count": page_count,
            "file_size_bytes": pdf_path.stat().st_size,
            "full_text": full_text_str,
            "full_text_length": len(full_text_str),
            "extraction_method": "pdfplumber",
            "preview": full_text_str[:500] + "..." if len(full_text_str) > 500 else full_text_str,
        }
    except Exception as e:
        print(f"  ❌ PDF 파싱 실패: {e}")
        return {
            "file_name": pdf_path.name,
            "error": str(e),
        }


def parse_excel(excel_path: Path) -> dict:
    """pandas로 Excel 텍스트 추출."""
    print(f"\n[PARSE EXCEL] {excel_path.name}")

    try:
        sheets = pd.read_excel(excel_path, sheet_name=None, header=None)
        print(f"  → 총 {len(sheets)} 시트")

        full_text_parts = []
        for sheet_name, df in sheets.items():
            print(f"  [시트: {sheet_name}] {df.shape[0]} 행 x {df.shape[1]} 열")
            full_text_parts.append(f"[시트: {sheet_name}]")
            full_text_parts.append(df.to_string(index=False, header=False))

        full_text_str = "\n\n".join(full_text_parts)

        return {
            "file_name": excel_path.name,
            "sheet_count": len(sheets),
            "file_size_bytes": excel_path.stat().st_size,
            "full_text": full_text_str,
            "full_text_length": len(full_text_str),
            "extraction_method": "pandas",
            "preview": full_text_str[:500] + "..." if len(full_text_str) > 500 else full_text_str,
        }
    except Exception as e:
        print(f"  ❌ Excel 파싱 실패: {e}")
        return {
            "file_name": excel_path.name,
            "error": str(e),
        }


# ============================================================================
# 메인
# ============================================================================


async def main() -> int:
    dept = os.environ.get("GOVT_PROBE_DEPT", "moef").lower()
    pages = int(os.environ.get("GOVT_PROBE_PAGES", "1"))
    do_download = os.environ.get("GOVT_PROBE_DOWNLOAD", "1") == "1"

    print("=" * 72)
    print("정부 부처 PDF/Excel 문서 수집 Probe")
    print("=" * 72)
    print(f"타겟 부처: {dept.upper()}")
    print(f"크롤링 페이지: {pages}개")
    print(f"파일 다운로드: {'예' if do_download else '아니오'}")
    print()

    # 1단계: 게시판 크롤링
    all_posts = []
    for page in range(1, pages + 1):
        if dept == "moef":
            posts = await fetch_moef_board(page)
        elif dept == "msit":
            posts = await fetch_msit_board(page)
        else:
            print(f"❌ 알 수 없는 부처: {dept}")
            return 1

        all_posts.extend(posts)

    if not all_posts:
        print("\n⚠️  키워드 필터링 후 게시물이 없습니다.")
        return 0

    print("\n" + "=" * 72)
    print(f"키워드 필터링 후 게시물: {len(all_posts)}건")
    print("=" * 72)
    for i, post in enumerate(all_posts, start=1):
        print(f"{i}. [{post['published_at']}] {post['title']}")
        print(f"   {post['url']}")

    if not do_download:
        print("\n[INFO] 다운로드 비활성화 (GOVT_PROBE_DOWNLOAD=0), Probe 종료.")
        return 0

    # 2단계: 첫 번째 게시물의 첨부파일 다운로드 (Probe용)
    first_post = all_posts[0]
    print("\n" + "=" * 72)
    print(f"[PROBE] 첫 번째 게시물 파일 다운로드 테스트")
    print("=" * 72)
    print(f"제목: {first_post['title']}")
    print(f"URL: {first_post['url']}")

    downloaded_files = await download_attachments(first_post["url"], first_post["dept"])

    if not downloaded_files:
        print("\n⚠️  다운로드된 파일이 없습니다.")
        return 0

    # 3단계: 파일 파싱
    print("\n" + "=" * 72)
    print("[PARSE] 파일 텍스트 추출 테스트")
    print("=" * 72)

    for file_path in downloaded_files:
        if file_path.suffix.lower() == ".pdf":
            parsed = parse_pdf(file_path)
        elif file_path.suffix.lower() in [".xlsx", ".xls"]:
            parsed = parse_excel(file_path)
        else:
            print(f"\n⏭️  스킵 (파서 미구현): {file_path.name}")
            continue

        print(f"\n[결과] {file_path.name}")
        print(f"  파일 크기: {parsed.get('file_size_bytes', 0) / 1024:.1f} KB")
        print(f"  추출 텍스트 길이: {parsed.get('full_text_length', 0):,} 자")
        if "page_count" in parsed:
            print(f"  페이지 수: {parsed['page_count']}")
        if "sheet_count" in parsed:
            print(f"  시트 수: {parsed['sheet_count']}")
        print(f"\n[미리보기]")
        print(parsed.get("preview", "(미리보기 없음)")[:800])

    print("\n" + "=" * 72)
    print("Probe 완료.")
    print("=" * 72)
    print(f"다운로드된 파일: {Path(tempfile.gettempdir()) / 'govt_docs_probe'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
