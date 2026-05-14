# 정부 부처 PDF/Excel 데이터 수집 전략

> **작성일**: 2026-05-12  
> **최종 갱신**: 2026-05-13 (과기부 3개 게시판 보드별 크롤링 기준·HWPX 다운로드 절차 확정)  
> **목적**: 기획재정부·과학기술정보통신부 등 정부 부처의 PDF/Excel/HWP 비정형 문서를 수집하여 Bronze Layer에 원형 보존, Silver 단계에서 AI 에이전트를 통한 구조화 수행

---

## 🎯 2026-05-13 최종 결정 — 보드별 자동 크롤링 + 키워드 기준 (ROI 최적화)

**결정**: 정부 문서는 **갱신 빈도·필요 정밀도**에 따라 **수동 업로드(기재부)** 와 **보드별 자동 크롤링(과기부 3종)** 을 분리하고, 과기부는 **3개 보드 모두 자동 수집**합니다 (mId=63 포함, 알림 의존 ❌).

| 구분 | 전략 | 핵심 필터 |
|------|------|---------|
| **기재부 거시 예산안** | **수동 다운로드 + 업로드 API** (연 1~2회) | 게시판 UI 변화 대응 비용이 자동화 가치 초과 → 사람이 1년에 몇 번만 업로드 |
| **과기부 `mId=63` — 예산 및 결산 (사전정보공표)** | **자동: 연도 상세 페이지 진입 → `ul.down_file`의 `.hwpx` 첨부 POST 다운로드** (주 1회) | `publictSeqNo=295` 검색 "예산" 목록(`div.board_list > div.toggle` row, `fn_goView(295, N)` 핸들러 → `publictListSeqNo`) → 각 연도 row → `view.do?referKey=295,N&publictSeqNo=295&publictListSeqNo=N` → `.hwpx` 우선; **POST `/ssm/file/fileDown.do` body 키는 `atchFileNo`/`fileOrd`/`fileBtn`** (`fn_download(<atchFileNo>, <fileOrd>)` onclick 에서 추출) |
| **과기부 `mId=307` — 보도자료** (외부 페이지 실명) | **자동 (인라인 JSON 직파싱)** — `?searchOpt=NTT_SJ&searchTxt=시행` GET 응답 HTML 내 `getSerachData()` 함수에 검색 결과 JSON 인라인 주입됨 → 별도 AJAX 호출 없이 정규식+`json.loads` 로 row 추출 (일 1회, 증분) | **등록일 2026년** AND **제목에 "시행" 포함** (시행계획·종합시행계획 등) |
| **과기부 `mId=311` — 사업공고** (외부 페이지 실명) | **자동 BeautifulSoup** (일 1회, 증분) | **등록일 2026년** AND **제목에 "모집" 포함** (모집공고·신규모집 등) |
| **NTIS R&D 과제 API** | **공식 Open API** (상시) | 위 보드에서 포착한 신호의 집행 내역 팩트 체크 |

**용어 메모**: 과기부 사이트 실제 페이지 타이틀 기준으로 `mId=307`이 **보도자료**, `mId=311`이 **사업공고**입니다. 본 문서는 외부 페이지 명칭을 따릅니다. 사용자가 별칭(공지사항·보도자료)으로 부르더라도 **URL의 `mId` 값이 단일 진실원(SoT)** 입니다.

**핵심 철학**: "자동화가 무조건 정답은 아니다. 단, **필터를 명확히 좁히면** 자동화 유지비가 급격히 낮아져 자동이 유리해진다 — 보드별 키워드·연도 필터를 단일 진입점으로 박는다."

---

## 📊 개요

### 타겟 부처 및 데이터 (하이브리드 전략)

| 부처 | 공식 목록·게시판 URL | 수집 방법 | 주요 데이터 | 갱신 빈도 |
|------|----------------------|-----------|----------|---------|
| **기획재정부** | 정책자료 등: https://www.moef.go.kr/nw/nes/detailNesDtaView.do?searchBbsId1=MOSFBBS_000000000035 | **수동 다운로드 + 파일 업로드 API** (비동기 파싱) | 예산안, 국가재정운용계획 (대용량 PDF) | 연 1~2회 (9월·12월) |
| **기재부 — 시드 PDF (저장소)** | *(웹 URL 아님)* `backend/scripts/` 아래 두 파일 | **로컬 파일 → 업로드 API 또는 배치 ingest** | 파이프라인·파서 검증용 고정 입력 | 버전 갱신 시 교체 |
| **과기부 `mId=63` — 예산 및 결산 (사전정보공표)** | 목록: https://www.msit.go.kr/publicinfo/detailList.do?sCode=user&mId=63&mPid=62&formMode=L&pageIndex=&publictSeqNo=295&searchSeCd=&searchMapngCd=&searchOpt=ALL&searchTxt=%EC%98%88%EC%82%B0 | **자동 크롤링: 연도 상세 진입 → `.hwpx` POST 다운로드 → 파싱** | "20XX년 예산 및 기금운용계획 개요" HWPX 본문 | 주 1회 (보드 자체는 연 1회 갱신) |
| **과기부 `mId=307` — 보도자료** | https://www.msit.go.kr/bbs/list.do?sCode=user&mPid=208&mId=307 | **BeautifulSoup** (일 1회, 증분) — 등록일 2026 + 제목 "시행" | 종합시행계획·R&D 시행 보도 본문 | 매일 |
| **과기부 `mId=311` — 사업공고** | https://www.msit.go.kr/bbs/list.do?sCode=user&mPid=121&mId=311 | **BeautifulSoup** (일 1회, 증분) — 등록일 2026 + 제목 "모집" | R&D 사업 모집공고 본문·첨부 | 매일 |
| **NTIS (R&D 통합)** | https://www.ntis.go.kr/ | **공식 Open API** | 실제 R&D 과제 집행 내역 (팩트 체크용) | 상시 (API 호출) |
| **산업통상자원부** (선택) | https://www.motie.go.kr/ | PDF/Excel 수동 | 산업 정책, 에너지 전환 예산 | 분기별 |
| **환경부** (선택) | https://me.go.kr/ | PDF/Excel 수동 | 탄소 중립 예산, 환경 정책 | 분기별 |

#### 기재부 예산안·국가재정운용계획 — 저장소 시드 PDF (크롤링 대체 입력)

운영에서는 **기재부 게시판에서 수동 다운로드** 후 업로드 API로 넣되, **개발·통합 테스트·파서 회귀 테스트**에는 아래 **저장소에 고정된 PDF**를 1차 데이터로 사용합니다 (웹 크롤 없이 재현 가능).

| 파일 경로 (repo 기준) | 매핑 `source_type` (권장) | 내용 |
|------------------------|--------------------------|------|
| `backend/scripts/3. 2025~2029년 국가재정운용계획 주요내용 (1).pdf` | `GOVT_MOEF_FISCAL` | 2025~2029년 **국가재정운용계획** 주요 내용 |
| `backend/scripts/251202 26년 예산안 국회통과★ (1).pdf` | `GOVT_MOEF_BUDGET` | **26년 예산안** 국회 통과 본 |

검증 명령 예시:

```bash
cd backend
python scripts/test_pdf_parsing.py "scripts/3. 2025~2029년 국가재정운용계획 주요내용 (1).pdf"
python scripts/test_pdf_parsing.py "scripts/251202 26년 예산안 국회통과★ (1).pdf"
```

### The VC 보류 결정 이후의 방향 전환 + 하이브리드 전략 확정

| 항목 | The VC (보류) | 정부 문서 (채택) |
|------|--------------|----------------|
| **법적 근거** | ❌ ToS 13조 4항·18조 3항 위반 위험 | ✅ 공공저작물 자유이용 (저작권법 24조의2) |
| **robots.txt** | ❌ `/api/*` 직접 호출 금지 | ✅ 제약 없음 |
| **데이터 구조** | 구조화된 JSON (투자 금액·VC명 명확) | 비정형 대용량 텍스트 (PDF/Excel 수십 페이지) |
| **갱신 빈도** | 실시간 (투자 발표 즉시) | **연 1~2회 (예산안) / 매일 (보도자료)** |
| **수집 전략** | 자동 크롤링 (불가) | **하이브리드**: 수동 다운로드(예산안) + 자동 크롤링(보도자료) |
| **파싱 전략** | DOM/Network Interception → 바로 DTO | Bronze 원형 보존 → Silver AI 에이전트 구조화 |

**핵심 인사이트**: 정부 문서는 **갱신 빈도가 낮고**(예산안 연 1회), **법적으로 안전**하며, **자동화 유지보수 비용**을 고려하면 "수동 다운로드 + 파일 업로드 API"가 오히려 ROI가 높다.

---

## 🛡️ 법적 근거 확인

### 1) 공공저작물 자유이용 (저작권법 제24조의2)

> "국가 또는 지방자치단체가 업무상 작성하여 공표한 저작물이나 계약에 따라 저작재산권의 전부를 보유한 저작물은 **허락 없이 이용**할 수 있다."

**적용**: 기재부·과기부가 공표한 예산안·정책 문서는 **공공저작물**로서 크롤링·다운로드·재가공·상업적 이용 모두 허용.

### 2) 공공데이터의 제공 및 이용 활성화에 관한 법률

정부 부처 홈페이지는 공공데이터포털(data.go.kr)에 등록되지 않더라도, **정보공개법** 및 **공공데이터법** 취지에 따라 국민 누구나 접근·활용 가능.

### 3) robots.txt 확인 (2026-05-12)

기재부·과기부 모두 `robots.txt`에서 `/bbs/` (게시판) 경로를 명시적으로 차단하지 않음. PDF 첨부파일 다운로드는 제약 없음.

**판정**: ✅ **법적으로 완전히 안전**. The VC와 달리 ToS 위반 리스크 Zero.

---

## 🚨 기술적 난관 (The VC와는 다른 종류)

### 난관 1. 🗂️ 비정형 파일 포맷 혼재

**현상**:
- 정부 부처는 여전히 **HWP(한글 2014)** 를 메인 파일 형식으로 사용하는 경우가 많음.
- PDF로 변환해 올려도, 스캔 이미지 PDF(텍스트 추출 불가)인 경우 발생.
- Excel은 **병합 셀·다단 편집·각주·상단 타이틀** 이 난무해 `pandas`로 바로 읽기 어려움.

**방어 전략**:

| 파일 형식 | 파이썬 라이브러리 | 비고 |
|----------|-----------------|------|
| **PDF (텍스트형)** | `pdfplumber` (권장) 또는 `PyMuPDF` | 표 구조 보존하며 텍스트 추출 |
| **PDF (스캔형)** | `pytesseract` + `pdf2image` | OCR 필요, 정확도 낮음 → Bronze에 "OCR 경고" 플래그 |
| **Excel** | `pandas.read_excel()` | `skiprows`로 헤더 위치 찾기, 병합 셀은 `ffill()` |
| **HWP** | `olefile` + `zlib` 직접 파싱 또는 `pyhwp` | HWP 5.0+ 구조 복잡, 가급적 PDF 우선 |

**Bronze 철학**: 파싱이 완벽하지 않아도 **원문 텍스트 전체를 `raw_metadata.full_text`에 보존**. Silver 단계에서 LLM이 재처리.

---

### 난관 2. 📑 게시판 구조의 비표준화

**현상**:
- 부처마다 게시판 HTML 구조가 제각각 (일부는 iframe, 일부는 ASP.NET 동적 렌더링).
- 페이지네이션이 POST 방식이거나, JavaScript로만 로드되는 경우.
- 첨부파일 다운로드 링크가 **세션 토큰** 또는 **일회용 URL**인 경우.

**방어 전략**:

1. **Playwright 우선 사용** (The VC Probe에서 검증된 패턴):
   - JavaScript 렌더링 게시판도 완벽 처리.
   - 첨부파일 다운로드는 `page.on("download", ...)` 이벤트로 가로채기.

2. **정적 HTML 우선 시도** (`BeautifulSoup` + `aiohttp`):
   - 간단한 게시판(예: 과기부 보도자료)은 정적 HTML 크롤링으로 충분.
   - 빠르고 리소스 효율적.

3. **부처별 Collector 분리**:
   - `moef_collector.py` (기재부 전용)
   - `msit_collector.py` (과기부 전용)
   - 각 부처의 게시판 구조에 맞춰 셀렉터·로직 개별 작성.

---

### 난관 3. 🔍 키워드 필터링의 정확도

**현상**:
- 정부 부처 게시판은 일 평균 10~50건의 글이 올라옴.
- "2026년 예산안"만 필요한데, "2025년 결산", "국회 제출 자료", "보도 참고 자료" 등 노이즈가 많음.

**방어 전략**:

**1단계 필터링** (게시물 제목 키워드):
```python
MOEF_KEYWORDS = ["예산안", "재정운용계획", "경제정책방향", "세법개정안"]
MSIT_KEYWORDS = ["R&D 예산", "과학기술 시행계획", "연구개발", "ICT 예산"]

def _is_target_post(title: str, keywords: list[str]) -> bool:
    """제목에 키워드가 하나라도 포함되면 True."""
    return any(kw in title for kw in keywords)
```

**2단계 필터링** (파일명 확인):
```python
# 첨부파일명에 "별첨", "붙임", "세부계획" 등이 있으면 우선 다운로드
TARGET_FILE_PATTERNS = [".pdf", ".xlsx", ".xls", ".hwp"]
```

**3단계 검증** (Bronze 적재 후):
- `raw_metadata.file_size_bytes`가 100KB 미만이면 "요약본"일 가능성 → 경고 플래그.
- `page_count < 5` 인 PDF는 표지일 가능성 → 본문이 있는 다른 첨부파일 우선.

---

### 난관 4. 🗓️ 갱신 주기 불규칙

**현상**:
- 예산안은 **연 1회** (보통 8~9월), R&D 시행계획은 **분기별** 발표.
- 실시간 스크래핑이 아니라 **배치 수집**(예: 월 1회 크론잡)으로 충분.

**방어 전략**:
- collector에 `--date-range` 옵션 추가:
  ```bash
  python moef_collector.py --start-date 2026-08-01 --end-date 2026-09-30
  ```
- 중복 방지: `raw_economic_data.source_url` UNIQUE 제약으로 이미 수집한 문서는 자동 스킵.
- **일 단위 크롤**(과기부 보도자료 등): 전략 B **「증분 수집」** — 매일 첫 페이지만 무작정 긁지 말고, 워터마크 이후 글만 처리 (아래 참고).

---

## 🔍 데이터 수집 방법 (하이브리드: 수동 + 자동)

### 전략 A: 수동 다운로드 + 파일 업로드 API (예산안 등 저빈도 대용량 문서)

**적용 대상**:
- 기재부 예산안 및 국가재정운용계획 (연 1~2회)
- 과기부 사전정보공표 - 예산 및 결산 (분기별)

**수집 프로세스**:

1. **수동 다운로드** (사람이 직접):
   - 기재부 정책자료 게시판: https://www.moef.go.kr/nw/nes/detailNesDtaView.do?searchBbsId1=MOSFBBS_000000000035
   - 과기부 **사전정보공표·R&D 예산 세부** 목록: https://www.msit.go.kr/publicinfo/list.do?sCode=user&mPid=62&mId=63  
     → 목록에서 해당 공고 상세 진입 후 첨부 PDF/Excel 다운로드 (또는 collector가 동일 URL에서 목록→첨부까지 자동화)
   - **로컬 시드(검증용)**: `backend/scripts/` 아래 예산안·국가재정운용계획 PDF (상단 표 참고)

2. **파일 업로드 API** (백엔드):
   ```
   POST /api/master/admin/upload/budget
   Content-Type: multipart/form-data
   
   Fields:
     - file: <PDF/Excel 파일>
     - source_type: GOVT_MOEF_BUDGET 또는 GOVT_MSIT_RND
     - source_url: <게시물 URL>
     - raw_title: <게시물 제목>
     - published_at: <발표일자>
   ```

3. **백엔드 자동 처리** (아래 **「타임아웃 방어」** 참고 — 요청 스레드에서 동기 파싱 금지):
   - pdfplumber / pandas로 텍스트 추출
   - `raw_metadata.full_text`에 전체 텍스트 저장
   - `raw_economic_data` 테이블에 적재

#### 타임아웃·504 Gateway Timeout 방어 (대용량 PDF/Excel)

**예상 문제**: 기재부 예산안 PDF는 **수백 페이지**에 달할 수 있습니다. 업로드 직후 **동기식(Synchronous)** 으로 전 페이지를 `pdfplumber`로 파싱하면 HTTP 응답이 수 분 이상 지연되어 **리버스 프록시·로드밸런서의 타임아웃(504)** 이 발생하기 쉽습니다.

**운영 원칙**:

| 단계 | 내용 |
|------|------|
| **동기 구간 (짧게)** | multipart 수신 → 파일 크기·MIME·확장자 검증 → 임시 디스크 저장(또는 객체 스토리지 업로드) → **DB에 작업 행 생성** (`status=queued`, `source_url`, `raw_title` 등 메타만 기록) |
| **비동기 구간 (길게)** | **FastAPI `BackgroundTasks`** 로 1차 구현하거나, 재시도·우선순위·다중 워커가 필요하면 **Celery(또는 RQ)** 큐에 넣어 워커가 pdfplumber/pandas 파싱 수행 |
| **HTTP 응답** | **즉시** `202 Accepted` 또는 `200` + `{ "job_id": "...", "status": "queued" }` 만 반환 — 클라이언트는 타임아웃에 걸리지 않음 |
| **완료 알림** (선택) | 작업 완료 시 `status=succeeded` / `failed` + 에러 메시지 저장, 필요 시 웹훅·이메일·관리자 UI에서 조회 |
| **진행 조회** (선택) | `GET .../admin/upload/budget/jobs/{job_id}` 로 `status`, `error_message`, 적재된 `raw_economic_data.id` 반환 |

**구현 스케치** (FastAPI):

```python
from fastapi import BackgroundTasks, UploadFile

@router.post("/admin/upload/budget")
async def upload_budget_file(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    source_type: str,
    source_url: str,
    raw_title: str,
    published_at: str,
) -> dict:
    # 1) 동기: 검증 + 임시 저장 + DB job row (queued)
    job = await create_parse_job(file, source_type, source_url, raw_title, published_at)
    # 2) 비동기: 무거운 파싱은 요청 종료 후 실행
    background_tasks.add_task(run_budget_parse_job, job.id)
    return {"job_id": job.id, "status": "queued"}
```

**Celery로 넘기는 기준**: 파싱이 **수 분 이상** 걸리거나, 동시에 여러 대용량 업로드가 들어올 수 있거나, **프로세스 재시작 시 작업 유실**을 막아야 할 때 — `BackgroundTasks`는 프로세스 크래시 시 큐가 사라지므로 운영 단계에서는 Celery 권장.

**ROI 분석**: 연 1~2회 수동 다운로드(5분) vs 게시판 UI 변화 대응 자동화 유지보수(수십 시간) → **수동이 압도적으로 효율적**

---

### 전략 B: 과기부 3개 보드 자동 크롤링 (보드별 필터 고정)

**적용 대상 & 보드별 단일 진실원(SoT) 필터**:

| 보드 | URL (운영 기준, `sCode`·`mPid` 포함) | 필터 (단일 진입점) | 워터마크 키 |
|------|-----|-----|-----|
| **`mId=63` 예산 및 결산 (사전정보공표)** | https://www.msit.go.kr/publicinfo/detailList.do?sCode=user&mId=63&mPid=62&formMode=L&pageIndex=&publictSeqNo=295&searchSeCd=&searchMapngCd=&searchOpt=ALL&searchTxt=%EC%98%88%EC%82%B0 | "예산" 검색 결과의 **각 연도 row**(`publictListSeqNo=1..12`) 모두 → 상세 진입 → `.hwpx` 첨부 다운로드 | `msit_publicinfo_63` (값: `publictSeqNo,publictListSeqNo` 쌍 또는 게시연도) |
| **`mId=307` 보도자료** | https://www.msit.go.kr/bbs/list.do?sCode=user&mPid=208&mId=307 | **등록일 2026년** AND **제목 "시행" 포함** (시행계획·종합시행계획 등) | `msit_bbs_307` |
| **`mId=311` 사업공고** | https://www.msit.go.kr/bbs/list.do?sCode=user&mPid=121&mId=311 | **등록일 2026년** AND **제목 "모집" 포함** (모집공고·신규모집 등) | `msit_bbs_311` |

> **메모**: 외부 페이지 실명 기준 `mId=307`이 **보도자료**, `mId=311`이 **사업공고** 입니다(메뉴 상위 mPid에서도 확인). 본 문서는 `mId` 값을 SoT로 사용하므로 사용자 별칭과 무관하게 동일한 보드를 가리킵니다.

---

#### B-1. `mId=63` — 예산/결산 HWPX 자동 다운로드 절차

**왜 자동?** 알림 → 사람 다운로드 의존을 제거하고, 새 연도 row가 추가되는 순간 워터마크가 자동 진행되도록 합니다 (연 1회 갱신이라 비용은 매우 낮음, 보드 자체 셀렉터만 안정적).

**1단계 — 목록 페이지 파싱** (`publicinfo/detailList.do`, `publictSeqNo=295` "예산" 묶음, 검색어 `searchTxt=예산`):

- 각 row에서 다음을 추출:
  - 연도/제목 (예: "2026년 예산 및 기금운용계획 개요")
  - `publictListSeqNo` (row 번호; 외부 검색 결과 상 12 → 1까지 존재)
  - 게시일 (예: `Feb 3, 2026`)
- **증분 비교**: 워터마크에 저장된 마지막 `publictListSeqNo`보다 큰 row만 후속 처리.

**2단계 — 상세 페이지 진입** (`publicinfo/view.do`):

URL 패턴:
```
https://www.msit.go.kr/publicinfo/view.do
    ?sCode=user
    &mId=63
    &mPid=62
    &pageIndex=
    &formMode=R
    &referKey=<publictSeqNo>,<publictListSeqNo>
    &publictSeqNo=<publictSeqNo>
    &publictListSeqNo=<publictListSeqNo>
    &searchMapngCd=
    &searchSeCd=
    &searchOpt=ALL
    &searchTxt=%EC%98%88%EC%82%B0
    &pageIndex2=1
```

여기서 `<publictSeqNo>=295` 고정, `<publictListSeqNo>` 는 1~12 등 row마다 변동. `referKey`는 두 값을 콤마로 이어 붙이는 형태 (예: `295,12`).

**3단계 — 첨부 파일 식별** (`<ul class="down_file">` 안의 `<li>`):

- 각 `li`에는 파일명 + 확장자 + 다운로드 버튼이 노출됩니다.
- **우선순위**: `.hwpx` → (없으면) `.hwp` → (그래도 없으면) `.pdf` / `.xlsx`.
- 파일명에 "예산", "기금운용계획", "개요"가 들어가는 항목을 1순위로 채택.

**4단계 — POST 다운로드** (`/ssm/file/fileDown.do`):

DevTools(스크린샷) 기준 요청:

- Method: `POST`
- URL: `https://www.msit.go.kr/ssm/file/fileDown.do`
- Headers (반드시):
  - `Content-Type: application/x-www-form-urlencoded`
  - `Referer: <위 view.do URL 그대로>` — **없으면 401/302 가능성**
  - `Origin: https://www.msit.go.kr`
  - `User-Agent: Mozilla/5.0 ... Chrome/120 ...`
  - `Cookie: JSESSIONID=...; clientId=...` — **이전 GET 응답에서 받은 세션 그대로 전달**
- Body: 다운로드 버튼이 사용하는 form 필드(예: `attachFileId=...&attachFileSeq=...` 또는 `fileId=...&fileSn=...`) — **상세 페이지 HTML에서 `<form>` 또는 `<a onclick="...">` 인자를 파싱해 동적 추출** (필드명·길이 36바이트 수준의 짧은 쌍)
- 응답: `Content-Disposition: attachment;filename="2026년...개요.hwpx"` + `Content-Type: application/octet-stream` (chunked)

**5단계 — 저장 + 비동기 파싱**:

- 다운로드한 `.hwpx` 를 임시 저장.
- 위 「타임아웃·504 방어」 절을 따라 **`parse_job` queued 행 생성 → `BackgroundTasks`/Celery 워커가 hwpx→텍스트 변환** (`hwp_to_text()` 유틸리티; `olefile`/`pyhwpx`/`pyhwp` 등 환경에 맞춰 채택).
- 적재: `source_type="GOVT_MSIT_RND"`, `source_url=<view.do URL>`, `raw_title=<연도 제목>`, `raw_metadata.full_text`/`hwp_warnings`/`publict_list_seq_no` 등.
- `source_url` UNIQUE 로 멱등 보장.

**구현 스케치**:

```python
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode

BASE = "https://www.msit.go.kr"
MSIT_PUBLICINFO_LIST_BUDGET = (
    f"{BASE}/publicinfo/detailList.do?sCode=user&mId=63&mPid=62&formMode=L"
    f"&pageIndex=&publictSeqNo=295&searchSeCd=&searchMapngCd="
    f"&searchOpt=ALL&searchTxt=%EC%98%88%EC%82%B0"
)

HEADERS_BROWSER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko,en;q=0.9,en-US;q=0.8",
}

def build_view_url(publict_seq_no: int, publict_list_seq_no: int) -> str:
    qs = {
        "sCode": "user", "mId": "63", "mPid": "62",
        "pageIndex": "", "formMode": "R",
        "referKey": f"{publict_seq_no},{publict_list_seq_no}",
        "publictSeqNo": publict_seq_no,
        "publictListSeqNo": publict_list_seq_no,
        "searchMapngCd": "", "searchSeCd": "", "searchOpt": "ALL",
        "searchTxt": "예산",  # urlencode가 알아서 인코딩
        "pageIndex2": "1",
    }
    return f"{BASE}/publicinfo/view.do?{urlencode(qs)}"

def crawl_msit_publicinfo_63(last_seen: int | None = None) -> list[dict]:
    """공시목록 → 각 row(연도) → view.do → ul.down_file → .hwpx 다운로드."""
    session = requests.Session()
    list_html = session.get(MSIT_PUBLICINFO_LIST_BUDGET, headers=HEADERS_BROWSER, timeout=30).text
    soup = BeautifulSoup(list_html, "html.parser")

    # 1) 목록에서 publictListSeqNo + 게시 연도/제목 추출 (셀렉터는 Probe 후 확정)
    rows = []  # [{publict_seq_no, publict_list_seq_no, title, posted_at}, ...]

    downloaded = []
    for row in rows:
        if last_seen and row["publict_list_seq_no"] <= last_seen:
            continue  # 워터마크 이전 → 중단(또는 skip)

        view_url = build_view_url(row["publict_seq_no"], row["publict_list_seq_no"])
        view_html = session.get(view_url, headers=HEADERS_BROWSER, timeout=30).text
        view_soup = BeautifulSoup(view_html, "html.parser")

        # 2) <ul class="down_file"> 내 li 중 .hwpx 우선 선택
        attach = pick_hwpx_attachment(view_soup)  # 파일명·attachFileId·attachFileSeq 파싱
        if not attach:
            continue

        # 3) POST /ssm/file/fileDown.do (Referer = view_url, Origin = BASE)
        dl_headers = {
            **HEADERS_BROWSER,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": view_url,
            "Origin": BASE,
        }
        resp = session.post(
            f"{BASE}/ssm/file/fileDown.do",
            headers=dl_headers,
            data=attach["form_payload"],   # 예: {"attachFileId": "...", "attachFileSeq": "..."}
            timeout=60,
            stream=True,
        )
        resp.raise_for_status()

        # 4) Content-Disposition에서 filename 추출 + tmp 저장
        local_path = save_binary_with_disposition(resp, default_ext=".hwpx")
        downloaded.append({
            "row": row,
            "view_url": view_url,
            "local_path": str(local_path),
            "filename": local_path.name,
        })

    return downloaded
```

> **HWPX 파싱**: HWPX = HWP의 OOXML 패키지(=ZIP) — `zipfile`로 풀고 `Contents/section*.xml`을 XML 파서로 읽으면 텍스트를 안정적으로 추출할 수 있어 구버전 `.hwp`(이진 포맷)보다 다루기 쉽습니다. `.hwp`(이진)만 있는 경우는 별도 `pyhwp`/`olefile` 경로.

---

#### B-2. `mId=307` (보도자료) — 2026년 + 제목 "시행"

```python
MSIT_BBS_PRESS = f"{BASE}/bbs/list.do?sCode=user&mPid=208&mId=307"
TARGET_YEAR_307 = 2026
TITLE_KEYWORD_307 = "시행"

def is_target_press(item: dict) -> bool:
    return (
        item["published_year"] == TARGET_YEAR_307
        and TITLE_KEYWORD_307 in item["title"]
    )
```

- 적재: `source_type="GOVT_MSIT_PRESS"`, `raw_metadata.board_key="msit_bbs_307"`.
- 본문·첨부 첨부 다운로드는 선택(첨부도 hwpx 가능 → B-1과 같은 POST 패턴 재사용).

#### B-3. `mId=311` (사업공고) — 2026년 + 제목 "모집"

```python
MSIT_BBS_BIZ = f"{BASE}/bbs/list.do?sCode=user&mPid=121&mId=311"
TARGET_YEAR_311 = 2026
TITLE_KEYWORD_311 = "모집"

def is_target_biz(item: dict) -> bool:
    return (
        item["published_year"] == TARGET_YEAR_311
        and TITLE_KEYWORD_311 in item["title"]
    )
```

- 적재: `source_type="GOVT_MSIT_BIZ"`, `raw_metadata.board_key="msit_bbs_311"`.
- 본 보드는 **사업공고** 성격이라 후속에서 `raw_opportunity_data`(GRANT) 로의 **이중 적재** 도 검토 (현재 Bronze는 `raw_economic_data` 단일 유지).

---

#### 증분 수집 (Incremental Crawling) — 3개 보드 공통

**예상 문제**: 매일 게시판 **첫 페이지만** 동일하게 긁으면, 어제 이미 적재한 글을 반복 파싱해 **CPU·DB·상세 페이지 요청**을 낭비합니다.

**운영 원칙**:

1. **워터마크 저장**: 게시판별로 **마지막으로 성공 적재한 시점**을 DB에 기록합니다.
   - 예시 키: `msit_publicinfo_63`, `msit_bbs_307`, `msit_bbs_311` (URL의 `mId`·경로와 1:1 대응)
   - 후보 값: `last_published_at` (게시일), `last_post_url` 또는 URL 내 **고유 ID**(예: `nttId`, `bbsSeq` 등 실제 HTML에서 추출) — 사이트 구조에 맞게 하나를 **정렬 가능한 기준**으로 고정.
2. **수집 루프**: 목록을 **최신순**으로 읽으며, 워터마크 **이전**(더 오래된) 글을 만나면 **루프 중단**합니다. 새 글만 상세 본문 요청.
3. **멱등성**: `raw_economic_data.source_url` **UNIQUE** 로 이미 있는 URL은 ingest 단계에서 스킵 — 워터마크 버그 시에도 중복 적재 방지.
4. **첫 실행**: 워터마크가 없으면 **최근 N건**(예: 첫 페이지만) 또는 **최근 7일**만 시드 수집 후 워터마크 기록.

**워터마크 저장 위치 (구현 선택지)**:

| 방식 | 장점 | 단점 |
|------|------|------|
| 전용 테이블 `govt_crawl_state(board_key, last_ntt_id, last_published_at, updated_at)` | 명확, 게시판별 튜닝 용이 | 스키마 추가 |
| `raw_economic_data` 에서 `source_type IN (GOVT_MSIT_PRESS, GOVT_MSIT_BIZ, GOVT_MSIT_RND)` 의 `raw_metadata.board_key` 별 `MAX(published_at)` 조회 | 테이블 추가 없음 | 삭제·재수집 시 주의 |

**`bbs` 목록 공통 수집 함수** (307·311 모두 사용; 필터만 다름):

```python
import requests
from bs4 import BeautifulSoup
from datetime import datetime

BASE = "https://www.msit.go.kr"

def _parse_year(date_text: str) -> int | None:
    """'2026.05.13' 또는 'May 13, 2026' 등 게시일 문자열에서 연도만."""
    for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%b %d, %Y"):
        try:
            return datetime.strptime(date_text.strip(), fmt).year
        except Exception:
            continue
    return None

def fetch_msit_bbs_list(
    board_base_url: str,
    page: int = 1,
    *,
    target_year: int,
    title_keyword: str,
) -> list[dict]:
    """과기부 bbs(307·311) 목록 → 연도 + 제목 키워드로 필터."""
    sep = "&" if "?" in board_base_url else "?"
    url = f"{board_base_url}{sep}pageIndex={page}"  # 실제 페이지 파라미터명은 Probe로 확정

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ko,en;q=0.9",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    rows = soup.select("table tbody tr") or soup.select("div.board_list ul li")

    posts = []
    for row in rows:
        title_tag = row.select_one("a")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)

        date_tag = row.select_one("td.date") or row.select_one("span.date")
        date_text = date_tag.get_text(strip=True) if date_tag else ""
        year = _parse_year(date_text)

        # 보드별 필터 (단일 진입점)
        if year != target_year:
            continue
        if title_keyword not in title:
            continue

        href = title_tag.get("href", "")
        link = (BASE + href) if href.startswith("/") else href

        posts.append({
            "title": title,
            "url": link,
            "published_at": date_text,
            "published_year": year,
        })

    return posts
```

**호출 예** (307·311):

```python
# 보도자료: 2026 + "시행"
press_posts = fetch_msit_bbs_list(
    MSIT_BBS_PRESS, target_year=2026, title_keyword="시행",
)

# 사업공고: 2026 + "모집"
biz_posts = fetch_msit_bbs_list(
    MSIT_BBS_BIZ, target_year=2026, title_keyword="모집",
)
```

> **연도/키워드 정책 변경 시**: 위 두 호출 인자만 바꾸면 됨 (상수 1곳). 매년 1월에 `target_year` 만 갱신.

> **`publicinfo` mId=63**: `bbs`와 HTML이 다르며 위 함수가 아니라 **B-1의 `crawl_msit_publicinfo_63()`** 가 담당.

**DTO 변환 (본문은 Silver에서 LLM이 정형화)**:
```python
def build_dto_from_msit_post(post: dict, body_text: str, source_type: str) -> EconomicCollectDTO:
    """과기부 bbs/publicinfo 본문 → DTO. source_type 으로 보드 구분."""
    return EconomicCollectDTO(
        source_type=source_type,  # "GOVT_MSIT_PRESS" / "GOVT_MSIT_BIZ" / "GOVT_MSIT_RND"
        source_url=post["url"],
        raw_title=post["title"],
        investor_name="과학기술정보통신부",
        target_company_or_fund=None,
        investment_amount=None,  # Silver 단계에서 LLM 추출
        currency="KRW",
        raw_metadata={
            "body_text": body_text,
            "board_key": {
                "GOVT_MSIT_PRESS": "msit_bbs_307",
                "GOVT_MSIT_BIZ":   "msit_bbs_311",
                "GOVT_MSIT_RND":   "msit_publicinfo_63",
            }[source_type],
            "filter": {
                "GOVT_MSIT_PRESS": {"year": 2026, "title_keyword": "시행"},
                "GOVT_MSIT_BIZ":   {"year": 2026, "title_keyword": "모집"},
                "GOVT_MSIT_RND":   {"search_text": "예산", "publict_seq_no": 295},
            }[source_type],
            "is_signal": source_type in ("GOVT_MSIT_PRESS", "GOVT_MSIT_BIZ"),
        },
        published_at=_parse_date(post["published_at"]),
    )
```

---

### 전략 C: NTIS OpenAPI (팩트 체크용)

**적용 대상**: 과기부 보도자료에서 포착한 "투자 계획 신호"를 **실제 집행 내역**으로 검증

**프로세스**:
1. 과기부 보도자료에서 "AI에 100억 투자 계획 발표" 신호 포착 (전략 B)
2. 3~6개월 후, NTIS OpenAPI로 해당 키워드("AI") R&D 과제 조회
3. 실제 집행 내역 확인: "A대학 30억, B기업 70억" (팩트)
4. `raw_economic_data`의 `investment_amount` 필드 업데이트 (Silver/Gold 단계)

**NTIS OpenAPI 예시**:
```python
import requests

def fetch_ntis_projects(keyword: str, year: int = 2026) -> list[dict]:
    """NTIS에서 키워드별 R&D 과제 조회."""
    url = "https://www.ntis.go.kr/openapi/service/rndProjects"
    params = {
        "serviceKey": "<YOUR_API_KEY>",
        "keyword": keyword,
        "year": year,
        "numOfRows": 100,
    }
    
    resp = requests.get(url, params=params, timeout=30)
    # XML 파싱 또는 JSON 변환 필요
    
    projects = []
    # ... 파싱 로직 ...
    
    return projects
```

**Silver 단계 교차 검증 로직**:
```python
# Bronze에서 "AI 투자 계획 발표" 신호 추출
signal = {
    "source_type": "GOVT_MSIT_PRESS",  # 보도자료(mId=307)에서 포착
    "raw_title": "2026년 AI 분야 종합시행계획 발표 (1,500억 투입)",
    "published_at": "2026-03-15",
    "raw_metadata": {
        "is_signal": True,
        "board_key": "msit_bbs_307",
        "filter": {"year": 2026, "title_keyword": "시행"},
    },
}

# 6개월 후 NTIS에서 실제 집행 확인
facts = fetch_ntis_projects(keyword="AI", year=2026)

# 매칭 후 investment_amount 업데이트
for fact in facts:
    # 제목·날짜·키워드로 연결
    if is_matched(signal, fact):
        update_raw_economic_data(
            source_url=signal["source_url"],
            investment_amount=fact["budget"],
            target_company_or_fund=fact["organization"],
        )
```

---

### 2단계: 파일 다운로드 및 파싱 (Extraction) — 전략 A 전용

**다운로드 로직**:
```python
import tempfile
from pathlib import Path

async def download_attachments(post_url: str) -> list[Path]:
    """게시물 상세 페이지에서 첨부파일 다운로드."""
    async with aiohttp.ClientSession() as session:
        async with session.get(post_url) as resp:
            html = await resp.text()
    
    soup = BeautifulSoup(html, "html.parser")
    file_links = soup.select("div.attach a")
    
    downloaded_files = []
    for link in file_links:
        file_url = "https://www.moef.go.kr" + link["href"]
        file_name = link.get_text(strip=True)
        
        # 확장자 필터링
        if not any(file_name.endswith(ext) for ext in [".pdf", ".xlsx", ".xls", ".hwp"]):
            continue
        
        # 임시 폴더에 다운로드
        tmp_dir = Path(tempfile.gettempdir()) / "gov_docs"
        tmp_dir.mkdir(exist_ok=True)
        local_path = tmp_dir / file_name
        
        async with session.get(file_url) as file_resp:
            local_path.write_bytes(await file_resp.read())
        
        downloaded_files.append(local_path)
    
    return downloaded_files
```

**PDF 파싱 (pdfplumber)**:
```python
import pdfplumber

def extract_text_from_pdf(pdf_path: Path) -> dict:
    """PDF에서 텍스트 전체 추출 + 메타데이터."""
    full_text = []
    
    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text.append(text)
    
    return {
        "file_name": pdf_path.name,
        "page_count": page_count,
        "file_size_bytes": pdf_path.stat().st_size,
        "full_text": "\n\n".join(full_text),
        "extraction_method": "pdfplumber",
    }
```

**Excel 파싱 (pandas)**:
```python
import pandas as pd

def extract_text_from_excel(excel_path: Path) -> dict:
    """Excel 모든 시트를 텍스트로 변환."""
    sheets = pd.read_excel(excel_path, sheet_name=None, header=None)
    
    full_text_parts = []
    for sheet_name, df in sheets.items():
        full_text_parts.append(f"[시트: {sheet_name}]")
        full_text_parts.append(df.to_string(index=False, header=False))
    
    return {
        "file_name": excel_path.name,
        "sheet_count": len(sheets),
        "file_size_bytes": excel_path.stat().st_size,
        "full_text": "\n\n".join(full_text_parts),
        "extraction_method": "pandas",
    }
```

---

### 3단계: `raw_economic_data` 적재 (Schema Mapping)

**DTO 변환**:
```python
from domain.master.models.transfer.economic_collect_dto import EconomicCollectDTO
from datetime import datetime

def build_dto_from_govt_doc(
    post: dict,
    parsed_file: dict,
    source_type: str,  # "GOVT_MOEF_BUDGET" 또는 "GOVT_MSIT_RND"
) -> EconomicCollectDTO:
    """정부 문서를 EconomicCollectDTO로 변환."""
    return EconomicCollectDTO(
        source_type=source_type,
        source_url=post["url"],
        raw_title=post["title"],
        investor_name=_get_dept_name(source_type),  # "기획재정부" 또는 "과학기술정보통신부"
        target_company_or_fund=None,  # 특정 기업 없음
        investment_amount=None,  # Bronze 단계에서는 추출 불가
        currency="KRW",
        raw_metadata=parsed_file,  # full_text, page_count 등 모두 여기
        published_at=_parse_date(post["published_at"]),
    )

def _get_dept_name(source_type: str) -> str:
    """source_type에서 부처명 추출."""
    if "MOEF" in source_type:
        return "기획재정부"
    elif "MSIT" in source_type:
        return "과학기술정보통신부"
    return "정부"

def _parse_date(date_str: str) -> datetime | None:
    """'2026.08.15' 형식 파싱."""
    try:
        return datetime.strptime(date_str, "%Y.%m.%d")
    except:
        return None
```

---

## 🧠 Silver/Gold Layer 전략 (LLM + pgvector)

Bronze에 수십 페이지 분량의 `full_text`가 적재된 후:

### Silver Layer: Chunking + Embedding

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings

def chunk_and_embed(full_text: str) -> list[dict]:
    """대용량 텍스트를 Chunk 단위로 쪼개어 pgvector에 적재."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )
    chunks = splitter.split_text(full_text)
    
    embeddings = OpenAIEmbeddings()
    vectors = embeddings.embed_documents(chunks)
    
    return [
        {"chunk_text": chunk, "embedding": vec}
        for chunk, vec in zip(chunks, vectors)
    ]
```

### Gold Layer: RAG 기반 구조화 추출

```python
from langchain.chains import RetrievalQA
from langchain.vectorstores import PGVector

def extract_budget_info(query: str) -> dict:
    """RAG로 예산 정보 추출.
    
    예: "2026년 탄소 중립 관련 R&D 예산 규모는?"
    """
    vectorstore = PGVector(
        connection_string="postgresql://...",
        embedding_function=OpenAIEmbeddings(),
    )
    
    qa = RetrievalQA.from_chain_type(
        llm=ChatOpenAI(model="gpt-4"),
        retriever=vectorstore.as_retriever(),
    )
    
    result = qa.run(query)
    return {
        "investment_amount": _extract_number(result),
        "target_fund": _extract_target(result),
    }
```

---

## 🛠️ 구현 계획 (하이브리드 전략)

### Phase 1: 전략 A — 수동 다운로드 + 파일 업로드 API (우선 구현)

**목표**: 기재부·과기부 예산안 PDF를 수동 다운로드 후 백엔드로 업로드 → 자동 파싱 → DB 적재

1. ✅ **PDF 파싱 테스트** (`scripts/test_pdf_parsing.py`) — 완료
   - 수동 다운로드한 PDF로 pdfplumber 품질 확인

2. **파일 업로드 API 구현** (동기 파싱 금지 — 위 **「타임아웃 방어」** 준수):
   ```python
   # backend/api/v1/master/admin_router.py (신규)
   @router.post("/admin/upload/budget")
   async def upload_budget_file(
       background_tasks: BackgroundTasks,
       file: UploadFile,
       source_type: str,  # GOVT_MOEF_BUDGET, GOVT_MSIT_RND
       source_url: str,
       raw_title: str,
       published_at: str,
   ) -> dict:
       """관리자용 정부 문서 파일 업로드 API."""
       # 1. 동기: 검증 + 임시 저장 + parse_job 행 생성 (queued)
       # 2. background_tasks.add_task(run_budget_parse_job, job_id)
       # 3. 즉시 반환: {"job_id": ..., "status": "queued"}
       # — run_budget_parse_job 안에서만 pdfplumber/pandas + ingest
   ```
   - 운영 부하가 크면 `BackgroundTasks` 대신 **Celery** 태스크로 동일 분리.

3. **연 1~2회 운영**:
   - 9월(예산안 발표), 12월(국회 통과) → 수동 다운로드
   - Postman/curl로 업로드 API 호출
   - 5분 소요, 자동화 유지보수 불필요

---

### Phase 2: 전략 B — 과기부 3개 보드 자동 크롤링

**목표**: `mId=63` HWPX 자동 수집 + `mId=307/311` 일 1회 증분 수집을 보드별 단일 필터로 운영

1. **Probe** (`scripts/govt_docs_probe_sync.py`):
   - 실측해야 하는 항목: `bbs` 페이지 파라미터명(`pageIndex` vs `page`), `publicinfo/view.do` 의 `down_file` 셀렉터·다운로드 form 필드명·세션 쿠키 흐름
   - 사용자 환경 네트워크 차단으로 보류 상태인 경우 다른 네트워크에서 재실행

2. **Collector 구현** (보드별 모듈 분리):
   ```bash
   backend/domain/master/hub/services/collectors/economic/msit_publicinfo_63_collector.py  # 예산/결산 HWPX
   backend/domain/master/hub/services/collectors/economic/msit_bbs_307_collector.py        # 보도자료 (year+"시행")
   backend/domain/master/hub/services/collectors/economic/msit_bbs_311_collector.py        # 사업공고 (year+"모집")
   ```

   각 collector가 책임지는 것:
   - **mId=63**: `crawl_msit_publicinfo_63()` — 목록(`publictSeqNo=295` "예산") → 각 row(`publictListSeqNo`) → `view.do` 진입 → `<ul class="down_file">` 의 `.hwpx` 우선 → POST `/ssm/file/fileDown.do` 로 다운로드 → 비동기 hwpx→텍스트 파싱. **알림 없음**, 워터마크: 마지막 `publictListSeqNo`.
   - **mId=307**: `fetch_msit_bbs_list(MSIT_BBS_PRESS, target_year=2026, title_keyword="시행")` → 상세 본문 수집. 워터마크: 게시일 또는 `nttId`.
   - **mId=311**: `fetch_msit_bbs_list(MSIT_BBS_BIZ, target_year=2026, title_keyword="모집")` → 상세 본문/첨부 수집. 워터마크 동일.

3. **ingest 서비스 추가**:
   ```python
   # bronze_economic_ingest_service.py
   async def ingest_msit_bronze() -> BronzeIngestResult:
       """과기부 publicinfo(63) + bbs(307, 311) 보드별 단일 필터로 증분 수집."""
       await msit_bbs_307.collect_incremental("msit_bbs_307")   # 2026 + "시행"
       await msit_bbs_311.collect_incremental("msit_bbs_311")   # 2026 + "모집"
       await msit_publicinfo_63.collect_incremental("msit_publicinfo_63")  # "예산" HWPX
       # DTO 변환 → DB (source_url UNIQUE), HWPX는 parse_job queued로 비동기 파싱
   ```

4. **라우터 엔드포인트** (보드별 분리 또는 통합 1엔드포인트):
   ```python
   POST /api/master/bronze/economic/msit-press       # mId=307 (year+"시행")
   POST /api/master/bronze/economic/msit-biz         # mId=311 (year+"모집")
   POST /api/master/bronze/economic/msit-rnd-budget  # mId=63  (publictSeqNo=295 "예산" HWPX)
   # 또는 POST /api/master/bronze/economic/msit-bronze 한 번에 오케스트레이션
   ```

5. **스케줄러 등록** (APScheduler / Celery):
   - `mId=307`·`mId=311`: 매일 새벽 2시 자동 실행 (증분).
   - `mId=63`: **주 1회** (예: 매주 월요일 03:00) — 보드 자체가 연 1회만 갱신되므로 더 자주 돌릴 필요 없음.
   - 실패 시 Slack 알림(운영 단계 옵션).

6. **연도 정책 운영**:
   - `mId=307/311`의 `target_year`는 **매년 1월 첫 주에 +1** (단일 상수 변경).
   - 과거 연도까지 보존하려면 `target_year=None`(필터 미적용) 모드를 옵션으로 추가.

---

### Phase 3: 전략 C — NTIS OpenAPI 연동 (팩트 체크용)

**목표**: 과기부 보도자료 신호를 실제 R&D 과제 집행 내역으로 검증

1. **NTIS collector 구현**:
   ```bash
   backend/domain/master/hub/services/collectors/economic/ntis_collector.py
   ```
   - NTIS OpenAPI로 R&D 과제 조회 (키워드, 연도)
   - 과제명, 연구기관, 예산 정보 추출

2. **Silver 단계 교차 검증 로직** (추후 구현):
   - Bronze의 "신호" 데이터와 NTIS "팩트" 매칭
   - `investment_amount` 필드 업데이트

---

### Phase 4: Silver/Gold Layer (LLM + pgvector) — 장기 로드맵

1. LangChain + pgvector 연동
2. Chunking + Embedding 파이프라인
3. RAG 기반 예산 정보 추출 에이전트

---

## 📋 source_type 정의 (하이브리드 전략)

| `source_type` | 설명 | 수집 방법 | `investor_name` | 데이터 특성 |
|--------------|------|-----------|----------------|----------|
| `GOVT_MOEF_BUDGET` | 기재부 예산안 | **수동 업로드** (연 1~2회) | "기획재정부" | PDF/Excel 대용량, 구조화 예산 표 |
| `GOVT_MOEF_FISCAL` | 기재부 재정운용계획 | **수동 업로드** | "기획재정부" | 5개년 계획, 정책 방향 |
| `GOVT_MSIT_RND` | 과기부 예산·결산 사전정보공표 (`publicinfo` mId=63, `publictSeqNo=295` "예산") | **자동 크롤링 + `.hwpx` POST 다운로드 + 비동기 파싱** (주 1회) | "과학기술정보통신부" | HWPX 본문; 워터마크 `msit_publicinfo_63` |
| `GOVT_MSIT_PRESS` | 과기부 보도자료 (`bbs` mPid=208/mId=307) | **자동 크롤링** (일 1회, 증분) — **2026년 + 제목 "시행"** | "과학기술정보통신부" | 시행계획 보도; 워터마크 `msit_bbs_307` |
| `GOVT_MSIT_BIZ` | 과기부 사업공고 (`bbs` mPid=121/mId=311) | **자동 크롤링** (일 1회, 증분) — **2026년 + 제목 "모집"** | "과학기술정보통신부" | 모집공고 본문; 워터마크 `msit_bbs_311` |
| `GOVT_NTIS_PROJECT` | NTIS R&D 과제 | **Open API** (상시) | "과학기술정보통신부" | 실제 집행 "팩트", 연구기관·예산 |
| `GOVT_MOTIE_POLICY` | 산자부 산업 정책 (선택) | 수동 업로드 | "산업통상자원부" | 에너지·산업 정책 |
| `GOVT_ME_CARBON` | 환경부 탄소 중립 (선택) | 수동 업로드 | "환경부" | 탄소 중립 예산·정책 |

---

## 🚀 다음 단계 (하이브리드 전략 로드맵)

### 즉시 실행 가능 (네트워크 제약 없음)
1. ✅ **전략 문서 완성** — 완료
2. ✅ **PDF 파싱 테스트 스크립트** (`test_pdf_parsing.py`) — 완료
3. **파일 업로드 API 구현** (`admin_router.py`) — 다음 우선순위
   - 수동 다운로드한 예산안 PDF 업로드
   - pdfplumber 자동 파싱 → DB 적재
   - Postman으로 테스트

### 네트워크 환경 개선 후 실행
4. **과기부 보도자료 크롤링** (`msit_news_collector.py`)
   - Probe 재실행 (다른 네트워크에서)
   - 게시판 셀렉터 확정 → collector 구현
5. **NTIS OpenAPI 연동** (`ntis_collector.py`)
   - API 키 발급
   - R&D 과제 조회 테스트

### 장기 로드맵
6. Silver/Gold Layer — LangChain + pgvector
7. RAG 기반 예산 정보 자동 추출 에이전트

---

## 📚 참고 자료

- 공공저작물 자유이용: https://www.copyright.or.kr/
- pdfplumber 문서: https://github.com/jsvine/pdfplumber
- LangChain Text Splitter: https://python.langchain.com/docs/modules/data_connection/document_transformers/
- pgvector + LangChain: https://python.langchain.com/docs/integrations/vectorstores/pgvector
