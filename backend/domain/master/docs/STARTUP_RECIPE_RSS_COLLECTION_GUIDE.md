# 스타트업레시피 RSS 수집 가이드 (`raw_economic_data`)

## 개요

| 항목 | 값 |
|------|------|
| **출처명** | 스타트업레시피 (Startup Recipe) |
| **공식 사이트** | https://startuprecipe.co.kr/ |
| **RSS URL** | `https://startuprecipe.co.kr/feed` |
| **포맷** | WordPress 표준 RSS 2.0 (`content:encoded` 풀텍스트 제공) |
| **업데이트 빈도** | 일 2~10건 |
| **매핑 테이블** | `raw_economic_data` |
| **수집 모듈** | `backend/domain/master/hub/services/collectors/economic/startup_recipe_collector.py` |
| **서비스 진입점** | `BronzeEconomicIngestService.ingest_startup_recipe()` |
| **API** | `POST /api/master/bronze/economic/startup-recipe?max_items=50` |

---

## 왜 스타트업레시피인가?

Wowtale에 이은 **2번째 RSS 출처**입니다. 한 매체에만 의존할 때 발생하는
다음 리스크를 분산해 줍니다.

1. **출처 다양성**: Wowtale 에 누락된 사건이 스타트업레시피 에는 종종 잡힙니다.
2. **정부 정책·행사 시그널** 비중이 Wowtale 보다 큼 → SMES Opportunity 수집과
   상호 보완 (정책 변화의 다각도 관측).
3. **RSS 구조가 Wowtale 과 동일한 WordPress 기반** → 기존 Wowtale Collector
   의 패턴(옵션 A · 별도 컬렉터 복제)을 그대로 활용해 추가 구현 시간이 최소.

---

## 1회 RSS Probe 결과 (2026-05-11 기준)

수집기 설계에 앞서 **실제 피드를 1회 호출하여 구조를 검증**했습니다.

| 검증 항목 | 결과 | 비고 |
|-----------|------|------|
| HTTP Status | 200 OK | `https://startuprecipe.co.kr/feed` (정식 URL) |
| `bozo` 플래그 | False | 표준 RSS 2.0 정상 파싱 |
| 1회 노출 엔트리 수 | **4건** | Wowtale 보다 적음 → `max_items=50` 도 안전한 상한 |
| `content:encoded` 제공 | ✅ **YES** | 4,355~9,745 자 (Wowtale 의 2~3배) |
| `published_parsed` | ✅ 제공 (UTC) | KST 변환 필요 |
| `id`/`guid` | `https://startuprecipe.co.kr/?p=NNNNN` | 영구 식별자 |
| `tags` | ⚠️ **거의 모두 `['news']`** | **태그 기반 필터링 불가능** |
| 제목 패턴 | ⚠️ `[AI서머리] 헤드라인1‧헤드라인2` 묶음 위주 | 1개 본문 안에 5~10개 별개 사건 혼재 |

### Wowtale 과의 핵심 차이 4가지

| 항목 | Wowtale | 스타트업레시피 |
|------|---------|---------------|
| 태그 시그널 | 강함 (`벤처투자`, `Investments` 등 카테고리 있음) | **없음 (`news` 1종)** |
| 제목 패턴 | 단일 사건 (`A사, 시리즈B 100억 유치`) | **묶음(digest) 위주** |
| 본문 크기 | 1~3 KB | 4~10 KB |
| 노이즈 비율 | 낮음 (투자 전문지) | 보통 (정책·행사 다수) |

---

## 핵심 설계 결정

### ① `[AI서머리]`(외) 묶음글은 별도 `source_type`으로 식별

`[AI서머리]`, `[이번주행사]`, `[이번주이벤트]`, `[금주의 펀딩]`, `[채용]` 등의
**대괄호 prefix 가 붙은 글은 1개 본문에 여러 사건이 섞여 있어
개별 사건 분류가 의미가 없습니다.**

→ 이런 글은 무조건 ``STARTUPRECIPE_DIGEST`` 로 적재하고,
**개별 사건의 분해는 Silver 계층의 LLM 책임**으로 명확히 위임합니다.

```python
_DIGEST_PREFIX_RE = re.compile(
    r"^\s*\[\s*(?:"
    r"AI\s*서머리"
    r"|이번주[\s ]?(?:행사|이벤트|펀딩|투자)"
    r"|금주(?:의)?[\s ]?(?:펀딩|투자|행사)"
    r"|이벤트"
    r"|행사"
    r"|채용"
    r")\s*\]",
    re.IGNORECASE,
)
```

### ② 일반 글은 **제목 + 본문** 둘 다 키워드 검사

Wowtale 은 카테고리에 강한 시그널이 있어 제목+태그 만으로도 노이즈 차단이
가능했지만, 스타트업레시피는 태그가 무력합니다.

→ 일반 글은 **제목**에 키워드가 없으면 **본문 앞 2,000자**까지 한 번 더 검사합니다.
   (Silver LLM 비용 절감 vs Recall 의 균형을 이 깊이로 결정)

```python
def _is_relevant(title, tags, full_text, *, is_digest):
    if is_digest:
        return True  # 묶음글은 무조건 통과 (일부 투자 사건 거의 항상 포함)
    haystack_short = title + " " + " ".join(tags)
    if any(k in haystack_short for k in _INVESTMENT_KEYWORDS):
        return True
    body_head = full_text[:2000]
    return any(k in body_head for k in _INVESTMENT_KEYWORDS)
```

### ③ `source_type` 세분화 (Wowtale 와 통일된 분류 체계)

| source_type | 매칭 키워드 (제목 우선) |
|-------------|------------------------|
| `STARTUPRECIPE_DIGEST` | `[AI서머리]` 등 묶음 prefix (최우선) |
| `STARTUPRECIPE_MA` | M&A, 인수합병, 인수, 합병 |
| `STARTUPRECIPE_IPO` | Pre-IPO, 프리IPO, IPO, 상장 |
| `STARTUPRECIPE_FUND` | 펀드 결성, 결성, 펀드 |
| `STARTUPRECIPE_INVEST` | (위에 안 잡힌 일반 투자 사건 — 기본값) |

### ④ KST 타임존 변환 (DART · Wowtale 와 동일 규칙)

`feedparser` 의 `published_parsed` 는 UTC `struct_time` 입니다.
DART 에서 발생했던 9시간 시차 버그를 방지하기 위해 KST(UTC+9) 변환을 강제합니다.

```python
_KST = timezone(timedelta(hours=9))
ts = time.mktime(parsed)
return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(_KST)
```

### ⑤ `content:encoded` 우선 사용 + 출처 메타데이터 기록

본문 크기가 큰 만큼 ``_html_to_text`` 의 ``max_len`` 을 Wowtale(5,000)
보다 키운 **8,000자** 로 설정했습니다.

```python
raw_metadata["content_text"] = full_text
raw_metadata["content_source"] = (
    "content_encoded" if entry.get("content") else "summary"
)
```

---

## DTO 매핑

| `EconomicCollectDto` 필드 | RSS 소스 | 비고 |
|---------------------------|----------|------|
| `source_type` | 위 ③ 규칙 | 묶음글은 `STARTUPRECIPE_DIGEST` 고정 |
| `source_url` | `entry.link` | DB의 unique constraint 대상 |
| `raw_title` | `entry.title` | 500자 cap |
| `investor_name` | 제목에서 임시 추출 (digest 는 `None`) | `[…]` prefix 제거 후 첫 토큰 |
| `target_company_or_fund` | `None` | Phase 1 정책 (Silver 위임) |
| `investment_amount` | `None` | Phase 1 정책 |
| `published_at` | `published_parsed` (UTC) → KST 변환 | 9시간 시차 버그 방지 |
| `raw_metadata` | `{guid, tags, is_digest, content_text, content_source}` | 모든 디버깅·재처리 신호 보존 |

---

## 4가지 디지털 함정 방어 (스타트업레시피 특화)

DART·Wowtale 단계에서 정착된 4가지 함정 외에, 스타트업레시피 RSS에서
특히 주의해야 할 항목입니다.

1. **태그 신뢰 금지** — `news` 외에 거의 없음. 분류·필터 입력으로 사용하지 않는다.
2. **묶음글 처리** — `[…]` prefix 글은 단일 사건 컬렉터로 가공하지 않는다.
   investor_name 추출도 건너뛴다 (대괄호 안 텍스트가 회사명으로 잘못 들어감).
3. **본문 길이 큼** — `content_text` 한도를 5,000 → 8,000 자로 상향.
   Silver 단계 토큰 비용 추산 시 Wowtale 평균의 2~3배로 산정.
4. **노이즈 비율 보통** — 정부 정책·행사·제품 출시도 자주 등장.
   제목만으로 필터링이 부족하므로 본문 앞 2,000자에서 키워드를 한 번 더 검사.

---

## 사용 예시

### API 호출

```bash
# 새 데이터 수집 (최근 50건 중 신규만 적재)
curl -X POST "http://127.0.0.1:8000/api/master/bronze/economic/startup-recipe?max_items=50"
```

응답 예시:
```json
{
  "source": "startup_recipe",
  "fetched": 4,
  "inserted": 4,
  "not_inserted": 0,
  "skipped_noise": 0
}
```

### 통합 테스트 스크립트

```powershell
cd backend
python scripts/startup_recipe_integration_test.py
```

샘플 출력 (실제 수집 결과):
```
[STATS] STARTUPRECIPE source_type 분포:
  - STARTUPRECIPE_DIGEST: 4건
```

---

## 한계 및 향후 개선

| 한계 | 향후 개선 (Phase 3) |
|------|---------------------|
| `investor_name` 휴리스틱 추출 — 제목 첫 토큰 기반 | Silver 단계 LLM 으로 본문에서 정확히 추출 |
| 묶음글 안의 개별 사건이 1개 row 로만 적재됨 | Silver 단계 LLM 이 본문을 사건 단위로 분해 후 별도 row 생성 |
| `tags` 가 사실상 무력 | 본문 NER 기반 카테고리 자동 분류 |
| 본문 크기 8KB 한도 | 본문 전문 보존이 필요한 사건은 별도 `raw_economic_data_full_text` 도입 검토 |

---

## 관련 문서

- `WOWTALE_RSS_COLLECTION_GUIDE.md` — 동일 패턴의 1번째 RSS 컬렉터 (참고 모델)
- `RAW_ECONOMIC_DATA_COLLECTION_GUIDE.md` — 경제 도메인 6개 출처 종합 가이드
- `BRONZE_ARCHITECTURE_DECISION.md` — 전체 Bronze 아키텍처 결정 사항
- `backend/docs/DATA_COLLECTION_SOURCES_GUIDE_V3.md` — 전체 출처 인덱스
