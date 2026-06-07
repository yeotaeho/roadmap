# The VC 데이터 수집 전략

> **작성일**: 2026-05-12  
> **최종 갱신**: 2026-05-12 (이용약관 정독 결과 — **🛑 The VC 자동 수집 전면 보류**, 시나리오 B까지 폐기)  
> **목적**: The VC(더브이씨) 한국 스타트업 투자 데이터 수집 전략 수립 및 구현 가이드

---

## 🛑 2026-05-12 최종 결정 — The VC 자동 수집 전면 보류

**결정**: The VC에 대한 **모든 자동 수집 경로(시나리오 A·B·C 전부)를 보류**합니다.  
**이유**: 이용약관(이하 "ToS") 제13조 4항·제18조 3항·제18조 4·5항이 자동 수집을 사실상 전면 금지하며, "robots.txt 허용"은 ToS의 면책 사유가 되지 못합니다. 자세한 조항 분석은 본 문서 「📜 이용약관(ToS) 검토 결과」 섹션 참조.

| 항목 | 상태 |
|------|------|
| `scripts/thevc_probe.py` | **실행 차단** (가드 환경변수 `THEVC_PROBE_ACK_TOS_BLOCK=1` 없이는 즉시 종료) |
| `thevc_collector.py` 구현 | **미착수 / 보류** |
| ingest 서비스·라우터 | **미생성 / 보류** |
| 본 문서의 「수집 방법 분석」 이하 구현 가이드 | **역사 보존용** (재개 시점에만 참고) |

**다음 행동**:
1. The VC 데이터가 실제 비즈니스에 필요해진 시점에 → **회사와 B2B 데이터 라이선스 계약** 협상(ToS 제13조 4항 "별도 계약" 단서가 유일한 합법 경로).
2. 그 사이에는 **DART(A~F·D 지분공시), SMES, Yahoo Finance, Yahoo Macro, Startup Recipe, Wowtale** 등 이미 합법 경로가 확보된 소스로 투자/경제 데이터를 확장.
3. 향후 약관 개정 시 본 문서 상단 결정 박스 재검토.

---

> ⚠ **본 문서를 읽기 전 필독**:  
> 본 문서 아래의 robots.txt 분석·시나리오 비교·구현 가이드는 **2026-05-12 ToS 검토 이전**의 사고 흐름을 보존한 것입니다. 현 시점 결정은 위의 **「🛑 자동 수집 전면 보류」**가 우선합니다.

---

## 🛡️ robots.txt 분석 결과 (2026-05-12 확인)

The VC `robots.txt` (`https://thevc.kr/robots.txt`) 실측 결과:

```text
User-agent: *
Allow: /
Disallow: /api

User-agent: Nuclei
User-agent: WikiDo
User-agent: Riddler
User-agent: PetalBot
User-agent: Zoominfobot
User-agent: Go-http-client
User-agent: Node/simplecrawler
User-agent: CazoodleBot
User-agent: dotbot/1.0
User-agent: Gigabot
User-agent: Barkrowler
User-agent: BLEXBot
User-agent: magpie-crawler
Disallow: /

Sitemap: https://thevc.kr/sitemap_index.xml
```

### 해석

| 대상 | 규칙 | 우리 작업에 미치는 의미 |
|------|------|-------------------|
| `User-agent: *` (일반 봇) | `Allow: /` + **`Disallow: /api`** | 공개 페이지 크롤링 ✅, **`/api/*` 직접 호출 ❌** |
| `Go-http-client`, `Node/simplecrawler`, BLEXBot 등 | `Disallow: /` | 기본 라이브러리 UA 사용 시 차단 위험 → **Chrome 정상 UA 필수** |
| Sitemap 제공 | `/sitemap_index.xml` | 페이지 인덱스 활용 가능 |

### 시나리오별 robots.txt 준수 판정

| 시나리오 | robots.txt 판정 | ToS 판정 | 최종 채택 여부 |
|--------|--------------|---------|--------------|
| **A. RSS** | ✅ 허용 (단, RSS 미제공 확인됨) | — | ❌ 사용 불가(미제공) |
| **B. Playwright + 공개 페이지** | ✅ 허용 | ❌ 13조 4항 위반 위험 | ❌ **보류 (2026-05-12)** |
| **C. `/api/*` 직접 호출** (`aiohttp`) | ❌ **명백한 `Disallow: /api` 위반** | ❌ 13조 4항 위반 | ❌ **폐기** |

> robots.txt만으로는 B가 통과처럼 보였지만, 후술하는 **ToS 제13조 4항이 "robots.txt 허용 + 별도 계약" 둘 중 하나를 요구**하며 자동 수집 자체를 금지합니다. 따라서 B도 함께 보류로 정리되었습니다.

### 시나리오 B 운영 원칙 (robots.txt 마지노선 준수)

1. **공개 페이지(`/funding/...`, `/oneoneone/...`, `/discussions/...`)만 로드** — `/api/*` 를 직접 URL로 호출하지 않습니다.
2. **Network Interception은 "보수적 해석"** — 브라우저가 페이지 렌더링 도중 자동 호출한 `/api/*` 응답에서, **화면에 실제 렌더링되는 데이터에 한정**해 사용합니다. 화면에 노출되지 않는 추가 필드(내부 ID, 어드민용 데이터 등)는 저장하지 않습니다.
3. **User-Agent는 실제 Chrome 기본 UA 사용** — `Go-http-client`, `python-requests/X.X` 같은 식별 가능한 라이브러리 UA 금지 (차단 목록 확장 시 함께 막힐 위험).
4. **`robots.txt` 의 `Sitemap` 활용** — 어떤 URL이 공개 페이지인지 사이트맵으로 확인 후 접근.
5. **호출 간격 ≥ 2초**, **시간당 60건 이하** — 정중한 봇으로 분류되도록.

### robots.txt가 알려주지 못하는 것 (별도 확인 필요)

- ❓ **로그인 후 행위에 대한 제약** → 이용약관(ToS) 확인 필요
- ❓ **수집 데이터 재배포·상업적 활용 가능 여부** → ToS + 저작권법 검토
- ❓ **본인 계정 자동화 사용 허용 여부** → ToS "자동화·계정 사용" 조항 검토

→ **`robots.txt` 만으로는 본인 계정 사용 가부를 결정할 수 없으며**, ToS 정독이 별도 의사결정 단계로 필요합니다. 결과는 바로 아래 「📜 이용약관(ToS) 검토 결과」 섹션 참조.

---

## 📜 이용약관(ToS) 검토 결과 (2026-05-12)

> **결론**: The VC의 ToS는 robots.txt와 별도로 **자동 수집(크롤링·스크래핑·캐싱·액세스 + 그 시도)을 명시적으로 금지**합니다. 본인 계정 로그인 후의 자동화는 **약관상 더 강하게 금지**되며, 1계정 1자연인 규정과 결합해 회피 경로가 없습니다. → **The VC 자동 수집 전면 보류**.

### 1) 결정에 직접 영향을 준 핵심 조항

| 조항 | 핵심 문구 (요약) | 우리 작업에 미치는 의미 |
|------|-----------------|----------------------|
| **제13조 4항** (저작권) | "회사와 별도 계약 및 robots.txt 규정에서 허용된 경우를 제외하고 … 크롤링·스크래핑·캐싱·액세스 또는 미러링하는 행위 **또는 그러한 모든 시도**는 금지. 또한 사이트 기능(**필터·더보기·검색 등**)을 과도하게 이용하는 행위도 금지." | 자동 수집의 **수단 자체**가 차단. **시도까지** 포섭하므로 Probe도 위험. 우리 Probe의 `buttons`/`keyboard`/`scroll`/`tabs`/`detail` 페이즈가 정확히 "기능의 과도한 이용" 정의에 부합. |
| **제18조 3항** (유료서비스) | "회원/비회원은 가격페이지에 명시된 정책에 따라 자신이 구독·접근할 수 있는 데이터만 이용. 그 외 데이터를 **스크래핑/크롤링/매크로/해킹** 등으로 이용 시 적발·의심만으로 자격 박탈." | 본인 계정 권한 범위 내라도 **수단**이 자동화면 박탈. 로그인 후 자동화 카드 봉쇄. |
| **제18조 4·5항** (계정) | "한 계정 = 1인(자연인) 한정. **동일 법인 임직원 간에도 공유 엄격 금지**." | "팀 공용 계정"으로 우회 불가. 부주의 관리로 인한 손해는 회원 책임. |
| **제14조 2항** (이용제한) | "주민등록법·저작권법·정통망법 위반(불법 통신, 접속권한 초과행위 등) 시 **즉시 계약 해지**, 별도 보상 없음." | 자동화 적발이 단순 이용 위반을 넘어 정통망법 이슈로 비화 가능. |
| **제19조** (환불) | "위약금(결제금액 10%) + 사용 월수 비율 + 신청월 비용 차감." | 박탈 직전 결제분도 사실상 거의 회수 불가. 비용 리스크. |
| **제22조** (회원 의무) | "신청·변경 시 허위 등록 금지, 타인 정보 도용 금지, 사이트에 게시된 정보 변경 금지." | 가짜 계정·도용·게시정보 변조 모두 금지. |

### 2) 시나리오별 ToS 판정 재정리

| 옵션 | ToS상 가부 | 코멘트 |
|------|----------|------|
| **(a) 본인 계정 로그인 후 자동 수집** (Probe + collector) | ❌ **불가** | 13조 4항·18조 3항 정면 위반. 박탈·소송 위험. |
| **(b) 익명 + robots.txt 준수 자동 수집/캐싱** | ❌ **사실상 불가 (회색지대)** | 13조 4항은 robots.txt 허용 *혹은* 별도 계약을 요구. "캐싱·시도"까지 금지. 회사 단독 판단으로 차단·고지 없이 막을 권한 명시. |
| **(c) 익명 + 순수 사람 브라우징, 자동화 ❌·저장 ❌** | 회색지대지만 위험 낮음 | 단, 비즈니스 데이터 파이프라인으로는 가치 없음. |
| **(d) 회사와 별도 데이터 라이선스 계약(B2B)** | ✅ **유일하게 안전** | 13조 4항 단서의 "별도 계약" 경로. 협상·비용·범위 명시 필요. |
| **(e) 대체 소스로 우회** (DART, SMES, Yahoo, RSS 등) | ✅ 가능 | 현재 이미 구현되어 있는 경로. 본 보류 결정의 사실상 대체안. |

### 3) "robots.txt만 지키면 되는 것 아닌가?"에 대한 답

- robots.txt의 `Allow: /` 는 **봇 크롤링 범위**만 규정합니다.
- ToS 제13조 4항은 robots.txt와 **별개로** "별도 계약 / robots.txt **규정에서 허용된** 경우" 이외의 자동 수집을 금지.
- 통상 robots.txt는 disallow(금지)만 명시하지, "이 경로에 대한 자동 수집/캐싱을 적극 허가"하는 도구가 아닙니다.
- 따라서 회사는 robots.txt에 disallow가 없더라도 **"자동 수집을 허가한 적 없음 + ToS 위반"**으로 단독 판단해 차단·법적 조치를 취할 권한을 보유.

### 4) Probe 스크립트(`scripts/thevc_probe.py`) 처분

- **삭제하지 않습니다**(향후 B2B 계약 체결 시 검증 자산으로 재사용 가능).
- **실행 차단 가드 추가**: 환경변수 `THEVC_PROBE_ACK_TOS_BLOCK=1` 가 없으면 즉시 `SystemExit(2)`. 가드는 "차단을 해제하라"가 아니라 "ToS 위험을 이해했음을 인수한다"는 의미의 인수증 역할.
- **권장**: 실무에서는 가드 환경변수를 설정하지 말 것. 라이선스 협상 후 합의된 범위에서만 1회 검증 목적으로 사용.

### 5) 이번 결정에서 함께 정리되는 것

- `thevc_collector.py`, `thevc_ingest_service`, `/api/master/bronze/opportunity/thevc` 류 라우터: **모두 미착수**.
- `THEVC_PROBE_PHASES`(buttons/tabs/keyboard/detail/home) 확장 Probe 결과는 본 문서 「📜 ToS 검토 결과」가 우선되어 **사용하지 않음**(보존만).
- 후속 사이트(예: 다른 투자 DB)에 대해서도, robots.txt + ToS 동시 확인을 **수집 시작 전 필수 절차**로 본 프로젝트에 일반화.

---

## 📊 The VC 개요

### 플랫폼 특성

| 항목 | 내용 |
|------|------|
| **서비스명** | The VC (더브이씨) |
| **URL** | https://thevc.kr/ |
| **유형** | **한국 스타트업 투자 데이터베이스** (단순 뉴스 미디어 ❌) |
| **월 이용자** | 20만 명 (창업자, 투자자, 미디어) |
| **데이터 품질** | ⭐⭐⭐⭐⭐ (최상급 — 투자 금액·VC명·라운드 정확도 높음) |
| **갱신 주기** | 실시간 (투자 유치 발표 즉시 DB 반영) |

### Wowtale/Startup Recipe와의 핵심 차이

| 구분 | Wowtale/Startup Recipe | **The VC** |
|------|----------------------|-----------|
| **본질** | 뉴스 미디어 (RSS 중심) | **투자 데이터베이스** (구조화된 DB) |
| **데이터 구조** | 비정형 (기사 본문 파싱 필요) | **정형 (투자 금액·VC·라운드 필드화)** |
| **정확도** | 중간 (기사 작성자에 따라 편차) | **매우 높음 (자체 DB 검증)** |
| **커버리지** | 주요 투자 + 정책·행사 섞임 | **순수 투자 건만** |
| **중복도** | 높음 (서로 동일 사건 보도) | **낮음 (1차 소스 + DB 통합 정리)** |

---

## 🎯 비즈니스 가치

### Why The VC?

1. **"한국 VC 투자의 Ground Truth"**  
   - Wowtale·Startup Recipe는 **기사 기반 2차 소스**  
   - The VC는 **자체 DB 기반 1차 소스** + 창업진흥원·금융위 공식 데이터 병행 활용  
   - **투자 금액의 정확도가 압도적으로 높음**

2. **Bronze Layer에서 즉시 정형화 가능**  
   - Wowtale: "A사, B펀드로부터 100억 유치" → LLM 파싱 필요  
   - The VC: `{"company": "A사", "investor": "B펀드", "amount": 10000000000}` → **구조화된 JSON 제공 가능성**

3. **중복 제거의 마스터 소스**  
   - 동일 투자 건을 Wowtale, Startup Recipe, The VC 3곳에서 모두 수집하면 중복 발생  
   - **The VC를 기준(Ground Truth)으로 삼아 중복 판단** 가능

4. **월별 트렌드 통계 제공**  
   - "2026년 4월 투자 84건, 1조 1,304억원" 같은 메타 통계도 수집 가능  
   - **Gold Layer에서 "공식 통계와 우리 집계의 정합성 검증"**에 활용

---

## 🚨 4대 현실적 난관 (Probe 단계 필수 확인)

The VC는 **데이터베이스의 가치를 지키기 위한 보안 정책**이 강력합니다. 일반적인 SPA 스크래핑보다 한 단계 더 까다로운 변수가 4가지 존재하며, **이를 Probe 단계에서 확인하지 않으면 본 구현이 모두 무용지물**이 됩니다.

---

### 난관 1. 🔒 로그인/유료화 벽 (가장 중요)

**현상**:
- The VC는 **구체적 투자 금액·전체 투자자 목록을 비로그인/무료 유저에게 마스킹**합니다.
- "비공개" 텍스트, 모자이크 처리, `***억`, `--`, 빈 문자열 등 다양한 형태로 노출됩니다.
- 즉, 익명 스크래핑 시 **`investment_amount`의 50~70% 가 NULL** 일 수 있습니다.

**방어 전략**:

```python
_MASKED_TOKENS = ("비공개", "공개되지", "***", "--", "—", "")

def _parse_amount_or_none(raw: str | None) -> int | None:
    """마스킹된 금액은 안전하게 None 반환 (예외 ❌)."""
    if not raw:
        return None
    cleaned = raw.strip()
    if any(tok in cleaned for tok in _MASKED_TOKENS):
        return None
    return _parse_korean_amount(cleaned)
```

**`raw_metadata`에 마스킹 플래그 기록**:

```python
raw_metadata = {
    "amount_raw": "비공개",           # 원본 보존 (Silver 단계 재처리 대비)
    "is_amount_masked": True,         # 마스킹 여부 명시
    "auth_state": "anonymous",        # "anonymous" / "authenticated"
}
```

**[선택] 인증 우회 전략** (사용자 계정 활용 시):
- Playwright: `context.add_cookies([...])` 로 **세션 쿠키 주입**
- aiohttp: 헤더에 `Cookie: session=...` 또는 `Authorization: Bearer ...` 동적 갱신
- ⚠ **이용약관 검토 필수**: 자동화·재배포 금지 조항이 있는 경우 우회 금지

---

### 난관 2. 👥 공동 투자(Syndicate) 데이터 정규화

**현상**:
- 스타트업 투자는 보통 **리드 투자자 1명 + 참여 투자자 N명**으로 구성됩니다.
- 예: "한화임팩트(리드), IMM인베스트먼트, KB인베스트먼트, 미래에셋벤처투자"
- `investor_name VARCHAR(255)` 컬럼에 **모두 콤마로 이어 붙이면** 다음 문제 발생:
  - 길이 초과 (255자 부족)
  - **`SELECT WHERE investor_name = '한화임팩트'`** 같은 정확 매칭 쿼리 깨짐
  - VC별 투자 건수 집계 불가능

**정규화 전략** (Bronze 단계 강제 규칙):

| 필드 | 저장 내용 | 예시 |
|------|---------|------|
| `investor_name` | **리드 투자자만** (배열의 첫 번째 또는 명시적 lead) | `"한화임팩트"` |
| `raw_metadata["lead_investor"]` | 리드 투자자 (중복 보존) | `"한화임팩트"` |
| `raw_metadata["co_investors"]` | **공동 투자자 배열 전체** | `["IMM인베스트먼트", "KB인베스트먼트", "미래에셋벤처투자"]` |
| `raw_metadata["investor_count"]` | 총 투자자 수 (집계 편의용) | `4` |

**효과**:
- "한화임팩트가 리드한 투자 건만" 조회 → `WHERE investor_name = '한화임팩트'`
- "한화임팩트가 참여한 모든 투자 건" 조회 → `WHERE raw_metadata @> '{"co_investors": ["한화임팩트"]}'::jsonb OR investor_name = '한화임팩트'`
- Silver/Gold Layer에서 **VC 네트워크 그래프 분석** 가능

---

### 난관 3. 🕵️ Playwright 사용 시 DOM 파싱 ❌ → Network Interception ⭕

**안티 패턴** (느리고 깨지기 쉬움):

```python
# ❌ 화면 렌더링 완료 대기 + DOM 셀렉터 파싱
await page.goto("https://thevc.kr/oneoneone/fundings")
await page.wait_for_selector("div.funding-item")
html = await page.content()
soup = BeautifulSoup(html, "html.parser")
items = soup.select("div.funding-item")  # 클래스명 바뀌면 끝장
```

**문제점**:
- DOM 렌더링 대기로 **5~10배 느림**
- 디자인·CSS 클래스 변경에 매우 취약
- 마스킹된 금액이 이미지로 들어오면 OCR까지 필요

**권장 패턴** (Network Interception):

```python
# ⭕ 백엔드가 화면 렌더링용으로 반환하는 깔끔한 JSON 응답을 가로채기
captured: list[dict] = []

async def _on_response(response):
    url = response.url
    # The VC 내부 API 엔드포인트 패턴 매칭
    if "/api/" in url and "funding" in url and response.status == 200:
        try:
            payload = await response.json()
            captured.append(payload)
        except Exception:
            pass  # 비 JSON 응답은 무시

page.on("response", _on_response)
await page.goto("https://thevc.kr/oneoneone/fundings", wait_until="networkidle")
# 페이지네이션은 page.click() 또는 page.evaluate("window.scrollTo(...)") 트리거
```

**효과**:
- 백엔드가 React/Next.js 컴포넌트에 넘기는 **구조화된 JSON** 을 그대로 획득
- 마스킹 여부도 JSON 필드(`is_masked: true`)로 확인 가능
- DOM 변경에 영향 없음

---

### 난관 4. 🛡️ ~~직접 API 호출 시 보안 토큰 방어~~ → **❌ 폐기 (robots.txt `Disallow: /api`)**

> **2026-05-12 결정**: `robots.txt` 분석 결과 The VC는 모든 봇에 대해 **`/api/*` 경로 직접 호출을 명시적으로 금지**하고 있습니다. CSRF·세션·Cloudflare 우회 같은 보안 토큰 처리 자체가 robots.txt 위반의 전제이므로, **본 난관은 우회 대상이 아니라 "이 경로로는 가지 않는다"는 결정 사항**으로 정리합니다.

**참고 (역사 보존)**: 만약 향후 The VC가 **공식 B2B API 라이선스**를 발급해 준다면, 그때 본 섹션의 보안 토큰 처리 패턴(CSRF, Referer, Origin, `_bootstrap_session()`)을 다시 활용할 수 있습니다. 그 전까지는:

- ❌ `aiohttp` 로 `https://api.thevc.kr/*` 또는 `https://thevc.kr/api/*` 직접 호출 금지
- ❌ `cloudscraper`, `curl_cffi` 같은 **Cloudflare/TLS Fingerprint 우회 라이브러리** 사용 금지
- ✅ 시나리오 B (Playwright + 공개 페이지) **단일 채택**
- ✅ 시나리오 B에서 페이지 렌더링 도중 자동 호출된 `/api/*` 응답을 가로채는 것은, **화면에 실제 렌더링되는 데이터에 한정**해 보수적으로 사용 (난관 3 참고)

---

## 🔍 데이터 수집 방법 분석

> 🛑 **2026-05-12 이후**: 본 섹션 이하의 시나리오 비교·구현 가이드는 ToS 검토 이전의 사고 흐름을 **역사 보존**한 것입니다. 현 시점 결정은 본 문서 상단의 **「🛑 자동 수집 전면 보류」** 와 **「📜 ToS 검토 결과」** 가 우선합니다.
>
> **(보존된) 핵심 결론** (`robots.txt` 검토 후, ToS 검토 이전): 시나리오 B(Playwright + 공개 페이지)만 채택. 시나리오 A는 RSS 미제공으로 사용 불가, 시나리오 C는 `Disallow: /api` 위반으로 폐기. → 이후 ToS 검토로 B까지 보류 처리됨.

### 옵션 A: RSS 피드 — ❌ 사용 불가

| 항목 | 내용 |
|------|------|
| **검토 결과** | `https://thevc.kr/feed` · `https://thevc.kr/rss` 모두 응답 없음 (2026-05-12 실측) |
| **판정** | RSS 미제공 → 채택 불가 |

---

### 옵션 B: Playwright + 공개 페이지 스크래핑 ⭐ **단일 채택**

> **The VC `robots.txt` `Allow: /` 범위 내에서 작동하는 유일한 합법적 경로.**

**타겟 페이지 (공개 경로만)**:
- `https://thevc.kr/oneoneone/fundings` — 일일일 투자 현황 (메인 수집 대상)
- `https://thevc.kr/funding/{id}` — 개별 투자 건 상세
- `https://thevc.kr/discussions/...` — 월별 투자 통계
- `https://thevc.kr/sitemap_index.xml` — 어떤 URL이 공개되어 있는지 인덱스

> ⚠ **`/api/*` 는 절대 직접 URL로 호출하지 않습니다.**

**수집 데이터 (화면 렌더링 데이터에 한정)**:
```json
{
  "company_name": "업스테이지",
  "round": "시리즈 C",
  "amount_raw": "1,800억",
  "amount_parsed": 180000000000,
  "lead_investor": "한화임팩트",
  "co_investors": ["IMM인베스트먼트"],
  "date": "2026-04-15",
  "sector": "AI",
  "source_url": "https://thevc.kr/funding/123456"
}
```

**구현 방법**:
1. **Playwright** Chromium 헤드리스 + 실제 Chrome User-Agent
2. 공개 페이지 로드 → Network Interception으로 페이지 렌더링용 `/api/*` 응답을 받기는 하지만, **화면에 실제로 노출되는 필드에 한해서만 저장**
3. 페이지네이션 순회 (스크롤 또는 "더 보기" 버튼)
4. `raw_economic_data` 매핑:
   - `source_type`: 라운드별 (`THEVC_SEED`, `THEVC_SERIES_A`, ...)
   - `investor_name`: **리드 투자자만** (난관 2)
   - `raw_metadata.co_investors`: 공동 투자자 배열
   - `raw_metadata.is_amount_masked`: 마스킹 여부
   - `raw_metadata.auth_state`: `"anonymous"` (기본) / `"authenticated_personal"` (ToS 확인 후 본인 계정 사용 시)

**장점**:
- ✅ robots.txt `Allow: /` 범위 내
- ✅ Cloudflare·CSRF 통과 (실제 브라우저)
- ✅ DOM 변경에 비교적 강건 (Network Interception은 백엔드 API 변경에만 영향)
- ✅ 화면 렌더링 데이터에 한정함으로써 **저작권·DB권 분쟁 위험 최소화**

**단점**:
- ⚠ Probe 결과에 따라 마스킹 비율이 50~70%일 수 있음 (난관 1)
- ⚠ Playwright 의존성·CPU 사용량 ↑ (Wowtale RSS 대비)
- ⚠ 호출 간격 제약 (≥ 2초)

---

### ~~옵션 C: 직접 API 호출~~ — ❌ **폐기 (robots.txt 위반)**

| 항목 | 내용 |
|------|------|
| **금지 사유** | `User-agent: * Disallow: /api` — The VC가 모든 봇에 대해 명시적 금지 |
| **시도 방법** | `aiohttp` · `cloudscraper` · `curl_cffi` 모두 금지 |
| **판정** | ❌ **채택 금지.** 향후 The VC와 공식 B2B API 라이선스 협상이 이루어진 경우에만 재검토. |

---

## 📋 구현 우선순위

### Phase 1: 데이터 소스 Probe (즉시 실행)

#### 1-A. 기본 소스 확인

1. **RSS 확인**: `curl https://thevc.kr/feed` 또는 `https://thevc.kr/rss` → ✅ **확인 결과: RSS 없음** (응답 timeout / 미제공)
2. **`robots.txt` 재확인**: `https://thevc.kr/robots.txt` → ✅ **확인 결과: `Disallow: /api` 명시** (시나리오 C 폐기 사유)
3. **공개 페이지 구조 분석**: `https://thevc.kr/oneoneone/fundings` HTML 구조 + DevTools Network 탭 (Network Interception 가능성 확인)

#### 1-B. 시나리오 B 실현 가능성 Probe (필수)

> ⚠ 이 표의 항목은 모두 **공개 페이지 로딩 + Network Interception 수동 관찰**으로 확인합니다. `/api/*` 를 직접 cURL 로 호출하는 행위는 하지 않습니다.

| 확인 항목 | 도구 | 기록할 내용 |
|---------|------|-----------|
| **마스킹 패턴** | 브라우저 시크릿 모드 (비로그인) vs 로그인 상태 | 비공개 표기 패턴 (`***억`, `비공개`, `--` 등) — 화면 표기 기준 |
| **화면 렌더링 필드** | 페이지 화면을 눈으로 확인 | 사용자에게 실제 보이는 필드 목록 (회사명·라운드·금액·투자자·날짜 등) |
| **JSON 응답 vs 화면 필드 비교** | DevTools → Network (브라우저가 자동 호출한 응답만 관찰) | 화면 비노출 내부 필드(예: `admin_*`, `internal_score`) 식별 → 사용 자제 |
| **Cloudflare 여부** | 응답 헤더의 `Server`, `cf-ray` | Cloudflare 보호 여부 (Playwright는 통과) |
| **공동 투자자 필드명** | 화면 + 캡쳐된 JSON | `lead_investor`, `co_investors`, `investors` 중 어느 필드명을 쓰는지 |
| **금액 필드 표현** | 화면 표기 | "180억" vs "1,800억" vs "비공개" vs "***억" |
| **페이지네이션 방식** | 페이지 하단 동작 관찰 | 무한 스크롤 vs "더 보기" 버튼 vs 페이지 번호 |
| **Playwright UA 통과 여부** | 헤드리스 브라우저로 1회 로드 시도 | 200 OK 응답 + Cloudflare Challenge 화면 미노출 |

#### 1-C. Probe 산출물

`scripts/thevc_probe.py` 실행 결과로 다음을 콘솔에 출력:
- ✅ 시나리오 B 가능 여부 (Playwright 로 공개 페이지 로드 성공 여부)
- 마스킹 비율 (수집 후보 N건 중 `is_amount_masked=True` 비율)
- 화면 렌더링 필드 목록 (저장 대상 결정용)
- 페이지네이션 트리거 방식 (구현 코드 결정용)
- robots.txt 준수 모드에서 실제 추출 가능한 샘플 데이터 5건

---

### Phase 2: Collector 구현 — **시나리오 B 단일 채택**

> robots.txt 검토 결과 시나리오 A·C는 모두 폐기 / 사용 불가로 결정되었으므로, **시나리오 B(Playwright + 공개 페이지 + Network Interception)만 구현**합니다.

#### 시나리오 B: Playwright + 공개 페이지 + Network Interception ⭐ **유일한 채택안**

> ⚠ **준수 사항**  
> 1. `Allow: /` 범위인 **공개 페이지(`/funding/...`, `/oneoneone/...`, `/discussions/...`)만** 로드  
> 2. `/api/*` 를 **직접 URL로 호출하지 않음** (브라우저가 페이지 렌더링용으로 자동 호출한 응답을 듣기만 함)  
> 3. **화면에 실제 렌더링되는 데이터에 한정**해 저장 (화면 비노출 내부 필드 사용 자제)  
> 4. User-Agent는 **실제 Chrome 기본 UA** 사용 (Go-http-client / python-requests UA 금지)  
> 5. 호출 간격 ≥ 2초, 시간당 60건 이하

```python
# thevc_collector.py
import asyncio
from playwright.async_api import async_playwright

# robots.txt 마지노선 — 공개 페이지 화이트리스트
_ALLOWED_PATH_PREFIXES: tuple[str, ...] = (
    "/oneoneone/",
    "/funding/",
    "/discussions/",
)


class TheVCEconomicCollector:
    _LIST_URL = "https://thevc.kr/oneoneone/fundings"
    # robots.txt 차단 UA 목록에 들어 있는 라이브러리 UA 절대 금지.
    # 일반 Chrome UA 사용 (Playwright Chromium 기본 UA 그대로 둠).

    async def collect(self, max_items: int = 100) -> list[EconomicCollectDto]:
        captured_payloads: list[dict] = []

        async def _on_response(resp):
            # 페이지 렌더링용으로 브라우저가 자동 호출한 /api/* 응답만 듣는다.
            # 우리가 직접 /api/* URL 을 호출하지 않으므로 robots.txt 마지노선 안.
            if "/api/" not in resp.url or resp.status != 200:
                return
            try:
                payload = await resp.json()
                captured_payloads.append(payload)
            except Exception:
                return

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            ctx = await browser.new_context(
                # Chrome 정상 UA — robots.txt 차단 UA 목록 회피
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                locale="ko-KR",
                timezone_id="Asia/Seoul",
            )
            # [선택] 본인 계정 사용 시 — ToS 확인 후에만 활성화
            # session_cookie = os.getenv("THEVC_SESSION_COOKIE")
            # if session_cookie:
            #     await ctx.add_cookies([{...}])

            page = await ctx.new_page()
            page.on("response", _on_response)

            await page.goto(self._LIST_URL, wait_until="networkidle", timeout=30000)

            # 페이지네이션 — 스크롤 또는 "더 보기" 버튼
            # 호출 간격 준수: 한 번 스크롤 후 ≥ 2초 대기
            for _ in range(max_items // 20):
                await page.mouse.wheel(0, 5000)
                await page.wait_for_timeout(2000)

            await browser.close()

        # 가로챈 payload 중 화면 렌더링용 데이터만 추출 → DTO 변환
        return self._parse_visible_data(captured_payloads, max_items)

    def _parse_visible_data(
        self, payloads: list[dict], max_items: int
    ) -> list[EconomicCollectDto]:
        """화면에 실제 렌더링되는 필드에 한정해 DTO 변환.

        - 화면 비노출 내부 필드 (admin_note, internal_score 등) 는 무시.
        - 마스킹된 금액은 _parse_korean_amount() 가 None 반환.
        - 리드/공동 투자자 분리 (_split_investors 사용).
        """
        ...
```

**구현 시간**: 3~4시간 (Playwright 세팅·페이지네이션 트리거·정규화 로직 포함)

**장점**:
- ✅ robots.txt `Allow: /` 범위 내 (`/api/*` 직접 호출 ❌)
- ✅ Cloudflare 통과 자동화 (실제 브라우저)
- ✅ DOM 변경 영향 ❌ (백엔드 JSON 직접 획득)
- ✅ 마스킹 여부도 JSON 필드로 명확히 판별

**한계**:
- ⚠ Probe 결과에 따라 마스킹 비율이 50~70%일 수 있음 (난관 1)
- ⚠ 호출 간격 제약으로 100건 수집 시 10~15분 소요

---

#### ~~시나리오 C: 직접 API 호출~~ — ❌ **폐기 (robots.txt `Disallow: /api`)**

> 본 섹션은 의도적으로 비워둡니다. 향후 The VC와 **공식 B2B API 라이선스** 협상이 성사되면 다시 검토합니다. 그 전까지는:
>
> - ❌ `aiohttp` / `httpx` 로 `api.thevc.kr` 또는 `thevc.kr/api/*` 직접 호출 금지
> - ❌ `cloudscraper`, `curl_cffi` 같은 TLS Fingerprint 우회 라이브러리 금지
> - ❌ Bearer Token / CSRF Token 자동 획득 후 직접 호출 금지

---

## 🗂️ 데이터 매핑 전략

### `raw_economic_data` 매핑

| The VC 필드 | 매핑 대상 | 변환 로직 |
|------------|----------|----------|
| `company_name` | `target_company_or_fund` | 그대로 저장 (최대 255자) |
| `lead_investor` (또는 `investors[0]`) | `investor_name` | **리드 투자자만** (난관 2). 마스킹 시 `None` |
| `amount` | `investment_amount` | `_parse_amount_or_none()` — **마스킹("비공개", `***억`) 시 안전하게 `None`** (난관 1) |
| `round` | `raw_metadata["round"]` | "시리즈 A", "Pre-A" 등 |
| `investors` (전체, 리드 제외) | `raw_metadata["co_investors"]` | **공동 투자자 배열** (난관 2) |
| (집계) | `raw_metadata["investor_count"]` | 총 투자자 수 (집계 편의용) |
| `sector` | `raw_metadata["sector"]` | "AI", "바이오", "핀테크" 등 |
| `amount` (원본) | `raw_metadata["amount_raw"]` | **원본 문자열 보존** ("비공개"·"180억" 그대로) — Silver 재처리용 |
| (계산) | `raw_metadata["is_amount_masked"]` | **마스킹 여부 boolean** (난관 1) |
| (수집 컨텍스트) | `raw_metadata["auth_state"]` | `"anonymous"` / `"authenticated"` (재현성) |
| `date` | `published_at` | YYYYMMDD → KST datetime |
| `detail_url` | `source_url` | 상세 페이지 URL (unique 제약 키) |

**최종 `raw_metadata` 스키마 예시**:

```json
{
  "round": "시리즈 C",
  "lead_investor": "한화임팩트",
  "co_investors": ["IMM인베스트먼트", "KB인베스트먼트"],
  "investor_count": 3,
  "sector": "AI",
  "amount_raw": "1,800억원",
  "is_amount_masked": false,
  "auth_state": "anonymous",
  "source_strategy": "playwright_public_page_intercept",
  "robots_compliant": true
}
```

> `source_strategy` 값은 추후 다른 우회 전략과 구분되도록 명시적으로 `playwright_public_page_intercept` 로 기록합니다. `robots_compliant: true` 는 본 수집 건이 robots.txt 마지노선 준수 모드에서 수집되었음을 운영 추적용으로 남기는 플래그입니다.

### `source_type` 분류

| source_type | 매칭 규칙 | 의미 |
|------------|---------|------|
| `THEVC_SERIES_A` | `round` 필드가 "시리즈 A" | 시리즈 A 투자 |
| `THEVC_SERIES_B` | `round` 필드가 "시리즈 B" | 시리즈 B 투자 |
| `THEVC_SEED` | `round` 필드가 "시드" | 시드 투자 |
| `THEVC_PRE_A` | `round` 필드가 "Pre-A" | Pre-A 투자 |
| `THEVC_GROWTH` | `round` 필드가 "성장", "Growth" | 후기 단계 투자 |
| `THEVC_FUNDING` | (그 외) | 일반 투자 (라운드 미분류) |

---

## ⚠️ 주의사항

### 1. 투자 금액 파싱 (마스킹 방어 포함)

The VC는 "180억", "1,800억", "18조" 같은 **한글 단위**를 사용하며, **마스킹된 경우** "비공개", `***억`, `--` 등으로 노출됩니다 (난관 1).

**파싱 로직** (필수):

```python
import re

_MASKED_TOKENS = ("비공개", "공개되지", "***", "--", "—", "비공개")
_AMOUNT_PATTERN = re.compile(r"([\d\.]+)\s*(조|억|만)")


def _parse_korean_amount(amount_str: str) -> int | None:
    """한글 금액 표기 → 원 단위 정수 변환 (마스킹은 None 반환).

    예:
      "180억"     → 18000000000
      "1.8조"    → 1800000000000
      "50만"     → 500000
      "비공개"   → None  (마스킹)
      "***억"    → None  (마스킹)
      ""         → None
    """
    if not amount_str:
        return None
    cleaned = amount_str.replace(",", "").strip()
    if not cleaned:
        return None
    # 난관 1 — 마스킹 토큰 우선 차단
    if any(tok in cleaned for tok in _MASKED_TOKENS):
        return None
    match = _AMOUNT_PATTERN.search(cleaned)
    if not match:
        return None
    num = float(match.group(1))
    unit = match.group(2)
    if unit == "조":
        return int(num * 1_000_000_000_000)
    if unit == "억":
        return int(num * 100_000_000)
    if unit == "만":
        return int(num * 10_000)
    return None
```

**호출 시 원본 보존 패턴**:

```python
amount_raw = item.get("amount", "")
amount = _parse_korean_amount(amount_raw)
is_masked = (amount is None) and any(tok in amount_raw for tok in _MASKED_TOKENS)

raw_metadata = {
    "amount_raw": amount_raw,
    "is_amount_masked": is_masked,
    # ...
}
```


### 2. 공동 투자자(Syndicate) 정규화 (난관 2 재명시)

```python
def _split_investors(raw_investors: list[str] | str) -> tuple[str | None, list[str], int]:
    """리드 투자자·공동 투자자 분리.

    반환: (lead_investor, co_investors, investor_count)
    """
    if isinstance(raw_investors, str):
        # "한화임팩트, IMM인베스트먼트, KB인베스트먼트" 같은 단일 문자열 케이스
        names = [n.strip() for n in raw_investors.split(",") if n.strip()]
    else:
        names = [n.strip() for n in raw_investors if n and n.strip()]
    if not names:
        return None, [], 0
    return names[0], names[1:], len(names)
```

`investor_name` 컬럼에는 **`names[0]` (리드 투자자) 만** 저장합니다.


### 3. 인증 상태별 동작 (난관 1 재명시)

| 상태 | 환경변수 | 동작 |
|------|---------|------|
| `anonymous` (기본) | 없음 | 마스킹 다수 발생 → `is_amount_masked=True` 다수 기록 |
| `authenticated` | `THEVC_SESSION_COOKIE` 설정 | Playwright 컨텍스트에 쿠키 주입 후 수집 |

```python
import os

class TheVCEconomicCollector:
    def __init__(self):
        self._session_cookie = os.getenv("THEVC_SESSION_COOKIE")
        self._auth_state = "authenticated" if self._session_cookie else "anonymous"
```

### 4. 스크래핑 에티켓 및 법적 검토

- **호출 빈도**: 1시간당 1회 이하 (The VC 서버 부담 최소화)
- **User-Agent**: 정중한 Bot 식별 (`User-Agent: RoadmapBot/1.0 (+contact@example.com)`)
- **스케줄러**: 매일 새벽 3시 10분 (DART/Wowtale 직후, Cloudflare 트래픽 한산 시간)
- **이용약관 준수**: The VC 이용약관에 **자동화·재배포·상업적 활용 제한 조항** 검토 필수. 상업 활용 전 사용자(태호님) 직접 검토 후 진행.
- **`robots.txt`**: `https://thevc.kr/robots.txt` 의 `Disallow` 경로 준수.

### 5. 중복 방지

- `source_url`을 **개별 투자 건 상세 페이지 URL**로 설정 (리스트 페이지 URL ❌)
- 예: `https://thevc.kr/funding/123456` (투자 건 고유 ID 포함)
- 동일 투자 건이 Wowtale/Startup Recipe 와 중복 적재될 수 있으나, **The VC = Ground Truth** 로 두고 Silver 단계에서 다른 소스를 보조 데이터로 매칭.

---

## 🚀 실행 계획

### Phase 0: Probe (2~3시간) — **본 구현 전 필수**

> robots.txt 검토 결과 **시나리오 B만 채택**되었으므로, Probe도 "시나리오 B 실현 가능성 검증"에 집중합니다.

1. **Probe 스크립트 작성** (`scripts/thevc_probe.py`)
   - `robots.txt` 재확인 (`Disallow: /api` 유지 여부)
   - 공개 페이지(`/oneoneone/fundings`)를 **Playwright Chromium 헤드리스**로 로드
   - Network Interception으로 페이지 렌더링 도중 자동 호출되는 응답 캡쳐
   - **화면에 렌더링되는 필드** 와 **JSON 응답 내 전체 필드**를 비교 → 화면 비노출 필드 식별
   - 마스킹 패턴 기록 (`***억`, `비공개`, `--` 등 실제 표기 확인)
   - 페이지네이션 트리거 동작 확인 (스크롤 vs "더 보기" 버튼)
   - Cloudflare 보호 여부 확인 (`cf-ray` 응답 헤더)

2. **Probe 결과 기반 결정 사항**
   - ✅ 시나리오 B 단일 채택 — 그대로 본 구현 진입
   - ❓ 본인 계정 사용 여부 — **ToS 정독 결과**에 따라 별도 결정 (`auth_state="authenticated_personal"` 활성화 가부)
   - ❌ 시나리오 C는 검토조차 하지 않음 (`Disallow: /api`)

### Phase 1: 구현 (1일차)

3. **Collector 구현** (`thevc_collector.py`)
   - 마스킹 방어 + 공동 투자자 정규화 + 인증 상태 분기 포함
4. **Service 메서드 추가** (`BronzeEconomicIngestService.ingest_thevc()`)
5. **API 엔드포인트 추가** (`POST /api/master/bronze/economic/thevc`)

### Phase 2: 검증 (2일차)

6. **통합 테스트** (`scripts/thevc_integration_test.py`)
   - 마스킹 비율 측정 (`is_amount_masked=True` 건수 / 전체 건수)
   - source_type 분포 (THEVC_SEED, SERIES_A 등)
   - 공동 투자자 정규화 검증 (`investor_name` vs `co_investors` 비교)
7. **문서 갱신** (`DATA_COLLECTION_SOURCES_GUIDE_V3.md`, `RAW_ECONOMIC_DATA_COLLECTION_GUIDE.md`)

---

## 📊 예상 ROI

| 항목 | 값 |
|------|-----|
| **Probe 시간** | 2~3시간 (마스킹 비율·공개 페이지 구조·페이지네이션 패턴 검증) |
| **구현 시간** | 시나리오 B 단독 — 3~4시간 (Playwright + 공개 페이지 + Network Interception) |
| **데이터 증가** | 월 300~500건 (2026년 4월 기준 84건/월 + 다른 라운드 포함, 익명 수집 시 마스킹 다수) |
| **데이터 품질** | ⭐⭐⭐⭐ (익명 기준) / ⭐⭐⭐⭐⭐ (본인 계정 + ToS 허용 시) |
| **중복 제거** | Wowtale·Startup Recipe 와 50~70% 중복 → The VC를 Ground Truth로 활용 |
| **비즈니스 가치** | 🎯 **최고** — 한국 VC 투자의 단일 소스 진리(SSOT) |
| **법적·정책적 리스크** | 🟢 **낮음** (시나리오 B + 공개 페이지 한정 + Chrome UA + 호출 간격 준수) |
| **차단 리스크** | 🟡 보통 (Playwright UA 차단 가능성 < 5%, robots.txt 준수 모드에서) |

---

## 🎯 결론

**The VC는 Economic Data 수집의 최종 보스(Final Boss)**입니다.

- Wowtale/Startup Recipe: 뉴스 기사 기반 2차 소스 (정확도 중간)
- DART: 공시 기반 1차 소스 (정확도 높음, 상장사만)
- **The VC: DB 기반 1차 소스 (정확도 최고, 비상장 스타트업 포함)**

### 작업 순서 (`robots.txt` 검토 결과 반영)

1. **시나리오 B(Playwright + 공개 페이지)가 robots.txt 준수의 마지노선이자 유일한 채택안.**  
   시나리오 A(RSS 미제공)와 시나리오 C(`Disallow: /api` 위반)는 모두 폐기.
2. **Probe 먼저, 구현은 그 다음.** 마스킹 패턴·공개 페이지 페이지네이션·렌더링 필드 구조를 Probe 산출물로 확인합니다.
3. **`/api/*` 는 절대 직접 호출하지 않습니다.** Network Interception은 브라우저가 렌더링용으로 자동 호출한 응답만 수동적으로 듣고, **화면에 실제 렌더링되는 데이터에 한정**해 저장합니다.
4. **User-Agent는 실제 Chrome 기본 UA.** `Go-http-client`, `Node/simplecrawler`, `python-requests/*` 같은 식별 가능한 라이브러리 UA는 차단 목록 확장 위험이 있으므로 금지.
5. **마스킹은 예외가 아닌 정상 케이스**로 가정하고, `is_amount_masked` 플래그·`amount_raw` 원본 보존으로 Bronze에서 안전하게 흡수.
6. **공동 투자자는 첫 날부터 정규화**해서 적재 — 나중에 마이그레이션하면 매우 비쌉니다.
7. **본인 계정 사용은 ToS 정독 후 결정.** 명시적 자동화 금지 조항이 있으면 익명 수집(마스킹 흡수) 모드 유지.

---

**다음 액션**: The VC Probe 스크립트(`scripts/thevc_probe.py`)를 작성하여 시나리오 B의 전제 조건(공개 페이지 페이지네이션 방식, 마스킹 비율, 렌더링 필드 구조)을 검증한 뒤 본 구현으로 진입합니다.
