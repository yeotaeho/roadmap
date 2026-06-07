"""정부 문서(PDF/Excel/HWPX) 파싱 공통 유틸.

수집된 첨부 파일에서 **본문 텍스트만** 안정적으로 뽑아낸다.
Bronze 단계에서는 정형화하지 않고 `raw_metadata.full_text` 에 보존,
Silver 단계에서 LLM/RAG 가 처리한다.

라이브러리 정책:
  - PDF  : pdfplumber (이미 의존성에 포함)
  - Excel: pandas + openpyxl
  - HWPX : 표준 라이브러리만 (ZIP + XML) — pyhwpx 등 외부 패키지 불필요
  - HWP(이진): 본 유틸에서는 미지원 (필요 시 별도 의존성 추가)
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)


_SUPPORTED_EXTS = (".pdf", ".xlsx", ".xls", ".hwpx")


def supports(file_path: Path | str) -> bool:
    ext = Path(file_path).suffix.lower()
    return ext in _SUPPORTED_EXTS


def parse_document(file_path: Path | str) -> dict[str, Any]:
    """확장자에 따라 적절한 파서 호출.

    확장자가 비어있거나 지원되지 않더라도 **매직 바이트(magic bytes)** 로 실제 포맷을
    재추정해서 라우팅한다. (정부 사이트 첨부가 Content-Disposition 누락으로 확장자가
    잘리는 케이스 대응 — 예: MSIT mId=63 의 일부 연도 게시물.)

    Returns:
        dict with keys:
            file_name, file_size_bytes, full_text, full_text_length,
            extraction_method, plus per-format extras
            (page_count for PDF, sheet_count for Excel, hwpx_warnings for HWPX).
        If parsing fails, returns dict with `error` key.
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext not in _SUPPORTED_EXTS:
        sniffed = _sniff_format(path)
        if sniffed:
            ext = sniffed

    if ext == ".pdf":
        return parse_pdf(path)
    if ext in (".xlsx", ".xls"):
        return parse_excel(path)
    if ext == ".hwpx":
        return parse_hwpx(path)

    return {
        "file_name": path.name,
        "file_size_bytes": path.stat().st_size if path.exists() else 0,
        "error": f"unsupported extension: {ext}",
        "extraction_method": None,
    }


# ---------------------------------------------------------------------------
# magic bytes sniffer
# ---------------------------------------------------------------------------


_PDF_MAGIC = b"%PDF-"
_ZIP_MAGIC = b"PK\x03\x04"          # XLSX / HWPX / docx 공통
_OLE2_MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"  # HWP(이진) / XLS / DOC


def _sniff_format(path: Path) -> str | None:
    """파일 첫 바이트를 보고 실제 포맷의 확장자(`.pdf` / `.xlsx` / `.hwpx`)를 반환.

    HWP(이진, OLE2)는 의도적으로 미지원으로 두어 None — 호출자가 `unsupported` 처리.
    """
    try:
        with path.open("rb") as f:
            head = f.read(8)
    except OSError:
        return None

    if head.startswith(_PDF_MAGIC):
        return ".pdf"

    if head.startswith(_ZIP_MAGIC):
        # ZIP 기반 — 내부 디렉토리 구조로 HWPX / XLSX 구분
        try:
            with zipfile.ZipFile(path, "r") as zf:
                names = [n.lower() for n in zf.namelist()[:30]]
        except zipfile.BadZipFile:
            return None
        if any(n.startswith("contents/section") and n.endswith(".xml") for n in names):
            return ".hwpx"
        if any(n.startswith("xl/") for n in names):
            return ".xlsx"
        # 알 수 없는 ZIP — 보수적으로 None
        return None

    if head.startswith(_OLE2_MAGIC):
        # HWP(구버전 이진) / XLS / DOC — 본 유틸 미지원
        return None

    return None


# ---------------------------------------------------------------------------
# PDF (pdfplumber)
# ---------------------------------------------------------------------------


def parse_pdf(pdf_path: Path) -> dict[str, Any]:
    try:
        import pdfplumber  # type: ignore[import-not-found]
    except ImportError as e:
        return _error(pdf_path, "pdfplumber", f"pdfplumber not installed: {e}")

    try:
        pages_text: list[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)

        full_text = "\n\n".join(pages_text)
        return {
            "file_name": pdf_path.name,
            "file_size_bytes": pdf_path.stat().st_size,
            "page_count": page_count,
            "full_text": full_text,
            "full_text_length": len(full_text),
            "extraction_method": "pdfplumber",
        }
    except Exception as e:
        logger.exception("PDF 파싱 실패: %s", pdf_path)
        return _error(pdf_path, "pdfplumber", str(e))


# ---------------------------------------------------------------------------
# Excel (pandas)
# ---------------------------------------------------------------------------


def parse_excel(excel_path: Path) -> dict[str, Any]:
    try:
        import pandas as pd  # type: ignore[import-not-found]
    except ImportError as e:
        return _error(excel_path, "pandas", f"pandas not installed: {e}")

    try:
        sheets = pd.read_excel(excel_path, sheet_name=None, header=None)
        chunks: list[str] = []
        for sheet_name, df in sheets.items():
            chunks.append(f"[시트: {sheet_name}]")
            chunks.append(df.to_string(index=False, header=False))

        full_text = "\n\n".join(chunks)
        return {
            "file_name": excel_path.name,
            "file_size_bytes": excel_path.stat().st_size,
            "sheet_count": len(sheets),
            "full_text": full_text,
            "full_text_length": len(full_text),
            "extraction_method": "pandas",
        }
    except Exception as e:
        logger.exception("Excel 파싱 실패: %s", excel_path)
        return _error(excel_path, "pandas", str(e))


# ---------------------------------------------------------------------------
# HWPX (ZIP + XML)
# ---------------------------------------------------------------------------

# HWPX 파일은 OOXML 패키지로, 본문 텍스트는 `Contents/section*.xml` 에 들어있다.
# 그 안에서 우리가 추출할 텍스트 노드의 태그 후보:
#   - `{http://www.hancom.co.kr/hwpml/2011/paragraph}t`
#   - 또는 hp 네임스페이스의 `t` 요소
# 네임스페이스 URI 가 버전마다 살짝 다를 수 있어 **로컬 태그명 == "t"** 인 모든 요소
# 의 텍스트를 모은 뒤 줄바꿈으로 잇는 방식이 가장 안전하다.

_LOCAL_TAG_T = re.compile(r"\}t$")


def parse_hwpx(hwpx_path: Path) -> dict[str, Any]:
    warnings: list[str] = []

    try:
        with zipfile.ZipFile(hwpx_path, "r") as zf:
            section_names = [
                name for name in zf.namelist()
                if name.lower().startswith("contents/section")
                and name.lower().endswith(".xml")
            ]
            section_names.sort()  # section0.xml, section1.xml, ...

            if not section_names:
                warnings.append("Contents/section*.xml not found")

            paragraphs: list[str] = []
            for name in section_names:
                try:
                    raw = zf.read(name)
                except KeyError:
                    warnings.append(f"missing section: {name}")
                    continue
                paragraphs.extend(_extract_text_from_section_xml(raw, warnings))

        full_text = "\n".join(p for p in paragraphs if p.strip())
        # 연속 공백 정리
        full_text = re.sub(r"[ \t]+", " ", full_text)
        full_text = re.sub(r"\n{3,}", "\n\n", full_text)

        return {
            "file_name": hwpx_path.name,
            "file_size_bytes": hwpx_path.stat().st_size,
            "section_count": len(section_names),
            "paragraph_count": len(paragraphs),
            "full_text": full_text,
            "full_text_length": len(full_text),
            "extraction_method": "hwpx-zip-xml",
            "hwpx_warnings": warnings or None,
        }
    except zipfile.BadZipFile as e:
        logger.exception("HWPX ZIP 파싱 실패: %s", hwpx_path)
        return _error(hwpx_path, "hwpx-zip-xml", f"bad zip: {e}")
    except Exception as e:
        logger.exception("HWPX 파싱 실패: %s", hwpx_path)
        return _error(hwpx_path, "hwpx-zip-xml", str(e))


def _extract_text_from_section_xml(
    raw: bytes, warnings: list[str]
) -> list[str]:
    """section*.xml 1개에서 문단별 텍스트 추출.

    HWPX 의 한 문단은 보통 `<p>` 또는 `<paragraph>` 안에 여러 `<t>` 가 흩어져 있다.
    문단 경계를 보존하기 위해, `localname == "p"` 또는 `localname == "paragraph"` 가
    끝날 때마다 누적된 `t` 텍스트를 join 해서 1개 문단으로 만든다.
    """
    paragraphs: list[str] = []
    try:
        # iterparse 로 start/end 모두 받음 (문단 종료 시점에 flush)
        events = ET.iterparse(io.BytesIO(raw), events=("start", "end"))
        current_chunks: list[str] = []
        para_depth = 0

        for event, elem in events:
            local = _localname(elem.tag)
            if event == "start" and local in ("p", "paragraph"):
                para_depth += 1
                if para_depth == 1:
                    current_chunks = []
            elif event == "end":
                if local == "t":
                    if elem.text:
                        current_chunks.append(elem.text)
                elif local in ("p", "paragraph"):
                    para_depth = max(para_depth - 1, 0)
                    if para_depth == 0:
                        text = "".join(current_chunks).strip()
                        if text:
                            paragraphs.append(text)
                        current_chunks = []
                # 메모리 해제 (대용량 안전)
                elem.clear()

        # 문단 태그가 한 번도 안 잡힌 경우 → 안전 폴백: 모든 t 를 통째로 join
        if not paragraphs:
            warnings.append("no <p>/<paragraph> detected; using flat <t> fallback")
            root = ET.fromstring(raw)
            for elem in root.iter():
                if _localname(elem.tag) == "t" and elem.text:
                    paragraphs.append(elem.text)
    except ET.ParseError as e:
        warnings.append(f"xml parse error: {e}")
    return paragraphs


def _localname(tag: str) -> str:
    """`{http://...}t` → `t`, `t` → `t`."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _error(path: Path, method: str, msg: str) -> dict[str, Any]:
    return {
        "file_name": path.name,
        "file_size_bytes": path.stat().st_size if path.exists() else 0,
        "extraction_method": method,
        "error": msg,
    }
