"""PDF/Excel 파싱 테스트 스크립트.

사용법:
  1. 정부 사이트에서 브라우저로 PDF/Excel 다운로드
  2. 파일을 backend/scripts/ 폴더에 복사
  3. python scripts/test_pdf_parsing.py <파일명>

예:
  python scripts/test_pdf_parsing.py "2026년_예산안.pdf"
"""

from __future__ import annotations

import sys
from pathlib import Path

# PDF 파싱
try:
    import pdfplumber
    import pandas as pd
except ImportError as e:
    print(f"❌ 필수 패키지 미설치: {e}")
    print("   pip install pdfplumber pandas openpyxl")
    sys.exit(1)


def parse_pdf(pdf_path: Path) -> dict:
    """pdfplumber로 PDF 텍스트 추출."""
    print(f"\n[PARSE PDF] {pdf_path.name}")
    print("=" * 72)

    try:
        full_text = []

        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
            print(f"  → 총 {page_count} 페이지")

            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                if text:
                    full_text.append(text)
                    print(f"  [페이지 {i}] {len(text)} 자 추출")
                    
                    # 처음 3페이지만 샘플 출력
                    if i <= 3:
                        print(f"\n  --- 페이지 {i} 샘플 (첫 200자) ---")
                        print(f"  {text[:200]}...")
                else:
                    print(f"  [페이지 {i}] ⚠️  텍스트 없음 (스캔 이미지일 수 있음)")

        full_text_str = "\n\n".join(full_text)

        print("\n" + "=" * 72)
        print("[결과 요약]")
        print(f"  파일 크기: {pdf_path.stat().st_size / 1024:.1f} KB")
        print(f"  페이지 수: {page_count}")
        print(f"  추출 텍스트 길이: {len(full_text_str):,} 자")
        print(f"  평균 페이지당 텍스트: {len(full_text_str) // page_count if page_count > 0 else 0:,} 자")

        return {
            "file_name": pdf_path.name,
            "page_count": page_count,
            "file_size_bytes": pdf_path.stat().st_size,
            "full_text": full_text_str,
            "full_text_length": len(full_text_str),
            "extraction_method": "pdfplumber",
        }
    except Exception as e:
        print(f"\n  ❌ PDF 파싱 실패: {e}")
        return {
            "file_name": pdf_path.name,
            "error": str(e),
        }


def parse_excel(excel_path: Path) -> dict:
    """pandas로 Excel 텍스트 추출."""
    print(f"\n[PARSE EXCEL] {excel_path.name}")
    print("=" * 72)

    try:
        sheets = pd.read_excel(excel_path, sheet_name=None, header=None)
        print(f"  → 총 {len(sheets)} 시트")

        full_text_parts = []
        for sheet_name, df in sheets.items():
            print(f"  [시트: {sheet_name}] {df.shape[0]} 행 x {df.shape[1]} 열")
            full_text_parts.append(f"[시트: {sheet_name}]")
            sheet_text = df.to_string(index=False, header=False)
            full_text_parts.append(sheet_text)
            
            # 첫 번째 시트만 샘플 출력
            if len(full_text_parts) <= 2:
                print(f"\n  --- 시트 '{sheet_name}' 샘플 (첫 500자) ---")
                print(f"  {sheet_text[:500]}...")

        full_text_str = "\n\n".join(full_text_parts)

        print("\n" + "=" * 72)
        print("[결과 요약]")
        print(f"  파일 크기: {excel_path.stat().st_size / 1024:.1f} KB")
        print(f"  시트 수: {len(sheets)}")
        print(f"  추출 텍스트 길이: {len(full_text_str):,} 자")

        return {
            "file_name": excel_path.name,
            "sheet_count": len(sheets),
            "file_size_bytes": excel_path.stat().st_size,
            "full_text": full_text_str,
            "full_text_length": len(full_text_str),
            "extraction_method": "pandas",
        }
    except Exception as e:
        print(f"\n  ❌ Excel 파싱 실패: {e}")
        return {
            "file_name": excel_path.name,
            "error": str(e),
        }


def main() -> int:
    if len(sys.argv) < 2:
        print("사용법: python test_pdf_parsing.py <파일경로>")
        print("\n예:")
        print('  python test_pdf_parsing.py "2026년_예산안.pdf"')
        print('  python test_pdf_parsing.py "예산세부계획.xlsx"')
        return 1

    file_path = Path(sys.argv[1])

    if not file_path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {file_path}")
        return 1

    print("=" * 72)
    print("정부 문서 파싱 테스트")
    print("=" * 72)

    if file_path.suffix.lower() == ".pdf":
        parsed = parse_pdf(file_path)
    elif file_path.suffix.lower() in [".xlsx", ".xls"]:
        parsed = parse_excel(file_path)
    else:
        print(f"❌ 지원하지 않는 파일 형식: {file_path.suffix}")
        print("   지원 형식: .pdf, .xlsx, .xls")
        return 1

    if "error" in parsed:
        return 1

    print("\n" + "=" * 72)
    print("✅ 파싱 성공!")
    print("=" * 72)
    print(f"\n[다음 단계]")
    print("  1. 이 파일의 텍스트가 `raw_metadata.full_text`에 저장됩니다.")
    print("  2. Silver 단계에서 LangChain으로 Chunk 분할 → pgvector 임베딩")
    print("  3. RAG 기반 에이전트가 \"2026년 탄소 중립 예산\"같은 쿼리로 금액 추출")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
