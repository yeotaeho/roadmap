# DART Economic Collector 고도화 전략

> **작성일**: 2026-05-11  
> **목적**: 현재 `dart_collector.py`의 데이터 품질을 Bronze Layer 최고 수준으로 끌어올리기

---

## 📊 현재 상태 진단

### ✅ 잘 구현된 부분
- **비동기 오프로딩**: `asyncio.to_thread`로 동기 `dart-fss` 라이브러리를 안전하게 처리
- **페이지네이션**: `total_page` 기반 완전 순회 로직
- **중복 제거**: `source_url` 기반 Set 필터링
- **키워드 필터링**: M&A/출자/인수합병 관련 공시 정확히 타겟팅

### ⚠️ 개선 필요 영역
1. **데이터 커버리지**: 자본 흐름의 핵심인 "신규시설투자", "유상증자(제3자배정)" 미포함
2. **`investment_amount` 누락**: 현재 `None`으로 비워두어 Silver Layer에서 LLM 재파싱 필요
3. **`target_company_or_fund` 정확도**: 제목 전체를 넣어 피투자 대상 기업명 추출 불가

---

## 🎯 3단계 고도화 로드맵

### Phase 1: 즉시 적용 (키워드 확장) — **15분 소요**

**목표**: 데이터 커버리지를 자본 흐름의 80%로 확대

#### 1-1. 키워드 튜플 확장

```python
_REPORT_KEYWORDS = (
    # 기존 - 타법인 지분 거래
    "타법인주식 및 출자증권 취득",
    "타법인주식 및 출자증권 처분",
    "타법인 주식",
    "출자증권 취득",
    "출자증권 처분",
    "주식교환",
    "주식이전",
    "회사합병",
    "회사분할",
    "영업양수",
    "영업양도",
    "자산양수",
    "자산양도",
    
    # ✅ 추가 1 - 신규시설투자 (CAPEX - 미래 산업 팽창 지표)
    "신규시설투자",
    "증설결정",
    
    # ✅ 추가 2 - 유상증자 (자본 조달의 역방향 추적)
    "유상증자 결정",
    "제3자배정",
)
```

#### 1-2. 비즈니스 임팩트
- **신규시설투자**: "SK하이닉스 용인 AI 반도체 클러스터 3조원", "LG에너지솔루션 배터리 공장 1.5조원" 같은 **가장 확실한 산업 팽창 예측 지표**
- **유상증자(제3자배정)**: 대기업이 유망 상장사에 대규모 투자할 때 주로 사용. 누가 누구에게 자본을 수혈했는지 정확히 파악 가능

**예상 수집량 증가**: 현재 대비 **2~3배** (주요사항보고서 중 신규시설/유상증자 빈도가 매우 높음)

---

### Phase 2: 선택적 적용 (source_type 세분화) — **30분 소요**

**목표**: 데이터 분석 시 카테고리 구분 편의성 확보

#### 2-1. `source_type` 다중화

현재: 모든 데이터를 `"DART_MAJOR_SECURITIES_ACQUISITION"` 단일 타입으로 저장

**개선안**: 키워드 그룹별로 `source_type` 분리

```python
# dart_collector.py 상단에 매핑 추가
_KEYWORD_TO_SOURCE_TYPE = {
    "타법인주식": "DART_CORP_INVESTMENT",
    "출자증권": "DART_CORP_INVESTMENT",
    "회사합병": "DART_MA",
    "영업양수": "DART_MA",
    "신규시설투자": "DART_FACILITY_INVESTMENT",
    "증설결정": "DART_FACILITY_INVESTMENT",
    "유상증자": "DART_PAID_IN_CAPITAL",
    "제3자배정": "DART_PAID_IN_CAPITAL",
}

def _classify_source_type(title: str) -> str:
    """공시 제목 기반 source_type 자동 분류"""
    for keyword, stype in _KEYWORD_TO_SOURCE_TYPE.items():
        if keyword in title:
            return stype
    return "DART_MAJOR_SECURITIES_ACQUISITION"  # fallback
```

#### 2-2. 비즈니스 임팩트
- Silver/Gold Layer에서 "M&A만", "시설투자만" 필터링 쿼리 간소화
- 대시보드에서 "투자 유형별 트렌드" 차트 생성 가능

---

### Phase 3: 고급 (investment_amount 자동 추출) — **2~4시간 소요**

**목표**: Bronze Layer에서 투자 금액을 즉시 수치화하여 Silver Layer LLM 비용 제로화

#### 3-1. 문제 인식

Open DART는 **주요사항보고서의 표 데이터를 JSON으로 제공하는 전용 API**가 존재하지만, `dart-fss` 라이브러리는 이를 직접 지원하지 않습니다.

- 공식 문서에는 **"주요사항보고서 36개 API"**가 있다고 명시
- 하지만 웹 검색 결과 구체적인 엔드포인트(`/api/piicpe_get.json`, `/api/neofac_get.json` 등)가 명확히 문서화되지 않음

#### 3-2. 해결 전략 (3가지 옵션)

##### 옵션 A: Open DART 공식 문서 직접 조사 ⭐ **권장**

1. Open DART 개발가이드 (https://opendart.fss.or.kr/guide/main.do?apiGrpCd=DE002) 접속
2. "주요사항보고서 36개 API" 목록에서 다음 엔드포인트 검색:
   - 타법인 주식 취득 결정 (`/api/piicpe_get.json` 추정)
   - 신규시설투자 결정 (`/api/neofac_get.json` 추정)
   - 유상증자 결정 (`/api/pifric_decsn.json` 등)
3. 각 API의 **응답 스키마**에서 금액 필드명 확인 (예: `inv_amt`, `isu_dcrs_de_fce_amt`)

**구현 예시** (타법인 출자 전용 API 호출):
```python
async def _fetch_investment_detail(
    self,
    corp_code: str,
    rcept_no: str,
    report_keyword: str,
) -> dict | None:
    """주요사항보고서 상세 정보 API 호출 → investment_amount 추출"""
    
    # 키워드에 따라 API 엔드포인트 선택
    if "타법인" in report_keyword or "출자" in report_keyword:
        api_path = "/api/piicpe_get.json"  # 타법인 출자 전용
        amount_field = "inv_amt"
        target_field = "oth_corp_nm"
    elif "신규시설" in report_keyword:
        api_path = "/api/neofac_get.json"  # 신규시설투자 전용
        amount_field = "fci_amt"
        target_field = "inv_obj_dtl"
    elif "유상증자" in report_keyword:
        api_path = "/api/pifric_decsn.json"  # 유상증자 전용
        amount_field = "isu_dcrs_de_fce_amt"
        target_field = None  # 자기자본 확충이므로 target 없음
    else:
        return None
    
    url = f"https://opendart.fss.or.kr{api_path}"
    params = {
        "crtfc_key": self._api_key,
        "corp_code": corp_code,
        "rcept_no": rcept_no,
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            
            # 금액 필드 추출 (단위: 원 → int 변환)
            amount_str = data.get(amount_field, "")
            amount = self._parse_amount(amount_str)
            
            target = data.get(target_field) if target_field else None
            
            return {"amount": amount, "target": target}

def _parse_amount(self, amount_str: str) -> int | None:
    """'1,500,000,000' → 1500000000 변환"""
    if not amount_str:
        return None
    try:
        return int(amount_str.replace(",", "").replace(" ", ""))
    except ValueError:
        return None
```

**적용 위치**: `collect_sync` 메서드의 `for report in res.report_list:` 반복문 내부에서, 키워드 매칭 후 `await self._fetch_investment_detail(...)`를 비동기 호출하여 DTO에 `investment_amount`와 정확한 `target_company_or_fund`를 채운다.

##### 옵션 B: `opendart-fss` 대안 라이브러리 활용

- `dart-fss` 대신 `opendart-fss` (https://pypi.org/project/opendart-fss/) 사용
- 이 라이브러리는 **83개 API 엔드포인트를 명시적으로 지원**하며, 타법인 출자 현황 조회 메서드 제공 (`client.report.get_other_corp_investments()`)
- **단점**: 현재 코드베이스를 전면 재작성해야 하므로, Phase 1 완료 후 별도 spike 작업으로 검토

##### 옵션 C: Phase 1만 적용 후 Silver Layer에서 LLM 파싱

- Bronze Layer는 현재처럼 `investment_amount=None` 유지
- Silver Layer에서 Gemini를 활용해 공시 원문 URL을 크롤링 → "투자금액: XXX원" 추출
- **비용**: 공시 1건당 Gemini 1.5 Flash 호출 약 $0.0001~0.0003 (10만건 기준 $10~30)
- **장점**: 구현 부담 없이 빠르게 MVP 완성

#### 3-3. 권장 순서

1. **Phase 1 (키워드 확장)을 먼저 적용하여 데이터 수집량 확보**
2. 수집된 데이터 1~2주치 확인 후, `investment_amount`의 비즈니스 중요도 재평가
3. 중요도가 높다면 → 옵션 A (Open DART 전용 API 직접 호출) 시도
4. 전용 API 문서가 불명확하다면 → 옵션 C (Silver Layer LLM 파싱)로 우회

---

## 🚨 Phase 1에서 제외할 항목 (합의)

### R&D 투자 데이터

**이유**:
- R&D는 주요사항보고(B)가 아닌 **정기공시(A)의 사업보고서 본문**에 기재
- XBRL/XML 파싱이 필요하여 구현 난이도가 높고, 데이터 추출 정확도가 낮음
- 분기별로만 업데이트되어 실시간성이 떨어짐

**대안**:
- Phase 1, 2 완료 후 별도 `DartRnDCollector` 클래스를 만들어 정기공시 파싱 전담
- 또는 NTIS(국가과학기술지식정보서비스) OpenAPI를 활용하여 국가 R&D 과제 정보로 대체 (오히려 더 포괄적)

---

## 📋 실행 체크리스트

### Phase 1 (즉시 적용 - 15분)
- [ ] `_REPORT_KEYWORDS` 튜플에 "신규시설투자", "증설결정", "유상증자 결정", "제3자배정" 추가
- [ ] 로컬에서 통합 테스트 실행 (`python backend/scripts/bronze_dart_integration_test.py`)
- [ ] 수집량 증가 확인 (기존 0~5건 → 15~30건 예상)
- [ ] Swagger `POST /api/master/bronze/economic/dart` 재실행 후 DB 확인

### Phase 2 (선택 - 30분)
- [ ] `_KEYWORD_TO_SOURCE_TYPE` 딕셔너리 작성
- [ ] `_classify_source_type()` 헬퍼 함수 구현
- [ ] DTO 생성 시 `source_type`을 동적으로 할당
- [ ] Silver Layer에서 source_type별 쿼리 테스트

### Phase 3 (고급 - 2~4시간)
- [ ] Open DART 공식 문서에서 주요사항보고서 전용 API 엔드포인트 확인
- [ ] `aiohttp` 기반 `_fetch_investment_detail()` 메서드 구현
- [ ] `_parse_amount()` 문자열→int 변환 로직 작성
- [ ] `collect_sync` 메서드에서 비동기 호출 통합 (asyncio.gather 활용)
- [ ] 통합 테스트로 `investment_amount` 채워짐 확인

---

## 📌 결론

**즉시 적용 권장**: Phase 1 (키워드 확장)  
→ 구현 부담 거의 없이 데이터 품질을 **즉시 2~3배** 향상시킬 수 있습니다.

**선택 사항**: Phase 2 (source_type 세분화)  
→ 나중에 Silver/Gold Layer에서 분석 편의성이 크게 증가합니다.

**연구 과제**: Phase 3 (investment_amount 자동 추출)  
→ Open DART API 문서 조사에 시간이 걸리므로, Phase 1 완료 후 별도 sprint로 진행하는 것을 권장합니다.

---

**다음 액션**: Phase 1 키워드 확장을 `dart_collector.py`에 즉시 적용하시겠습니까?
