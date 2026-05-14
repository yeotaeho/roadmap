# 중소벤처기업부 사업공고 OpenAPI 수집 가이드

> **작성일**: 2026-05-11  
> **목적**: 중소벤처기업부 사업공고 OpenAPI 연동 구현 및 신청 가이드

---

## 📊 중소벤처기업부 사업공고 OpenAPI 개요

중소벤처기업부는 창업·혁신 기업을 위한 다양한 정부 지원사업 공고를 **공공데이터포털**을 통해 OpenAPI로 제공합니다.

- **제공 기관**: 중소벤처기업부
- **데이터 포털**: https://www.data.go.kr/
- **API 형식**: REST (XML 응답)
- **서비스 유형**: 정기적 지원사업 공고 (창업지원, R&D, 수출지원 등)
- **업데이트 주기**: 실시간 (새 공고 등록 시)
- **데이터 품질**: 공고명, 주관기관, 지원규모, 접수기간, 첨부파일 등 구조화된 정보 제공

---

## 🎯 비즈니스 목적 (Why)

### 1. 데이터 수집 목표

`raw_opportunity_data` 테이블에 **정부의 스타트업·중소기업 지원사업 공고**를 수집하여:

1. **기회 발굴**: 사용자(스타트업·예비창업자)에게 적합한 정부 지원사업을 추천
2. **트렌드 분석**: 정부 예산이 어느 산업(AI, 바이오, 탄소중립 등)에 집중되는지 파악
3. **선행 지표**: 정부 지원 → 스타트업 투자 유치 연결고리 추적

### 2. 타겟 사용자

- 예비 창업자 (정부 지원금으로 초기 자본 확보)
- 초기 스타트업 (시리즈 A 이전 단계에서 R&D 자금 필요)
- 투자자 (정부가 집중 지원하는 분야 = 미래 유망 산업)

---

## 🔑 API 신청 가이드

### 1. 신청 절차

1. **공공데이터포털 회원가입**  
   https://www.data.go.kr/ 접속 → 회원가입 (본인인증 필요)

2. **중소벤처기업부_사업공고 API 찾기**  
   검색창에 "중소벤처기업부 사업공고" 입력 → 해당 API 상세 페이지 진입

3. **활용신청 클릭**  
   "OpenAPI 개발계정 신청" 버튼 클릭

4. **활용목적 작성** (⚠️ 중요)  
   아래 가이드 참고하여 신청 사유 입력

5. **승인 대기**  
   보통 **1~2영업일** 내 자동 승인 (심사 누락 시 3~5일 소요)

6. **API 키(Service Key) 발급**  
   승인 후 "마이페이지 → 인증키 발급현황"에서 확인

---

### 2. 활용목적 작성 가이드 ✍️

#### ✅ 추천 작성 예시 (정직하고 구체적인 접근)

```
[활용 분야 선택]
☑ 앱개발(모바일솔루션)

[활용목적 상세]
스타트업 및 예비창업자를 위한 정부지원사업 정보 큐레이션 모바일/웹 플랫폼 개발에 활용하고자 합니다.

1. 서비스 목적:
   - 창업·혁신 기업이 놓치기 쉬운 정부 지원사업 공고를 통합 수집하여 사용자 맞춤형 추천
   - 마감 임박 공고 알림, 산업별·단계별 필터링 기능 제공

2. 데이터 활용 방식:
   - 중소벤처기업부 사업공고 OpenAPI를 통해 공고명, 지원규모, 접수기간 등을 수집
   - 자체 DB에 저장 후 사용자에게 실시간으로 제공
   - 공고 원문 링크는 정부 사이트로 직접 연결하여 공공데이터 출처 명시

3. 기대 효과:
   - 스타트업 생태계의 정보 접근성 개선
   - 정부 지원사업의 실제 수혜율 증가 기여

데이터는 비영리적 서비스 제공 목적으로만 활용하며, 출처를 반드시 명시하겠습니다.
```

#### ⚠️ 피해야 할 작성 방식

- ❌ "개인 프로젝트", "공부용" (신뢰도 낮음 → 거부 가능성)
- ❌ "데이터 분석", "연구" (학술 연구가 아니면 부적절)
- ❌ "재판매", "제3자 제공" (공공데이터 이용약관 위반)

#### 💡 작성 팁

- **구체성**: "어떤 서비스", "누구를 위해", "어떻게 활용"을 명확히 기술
- **공익성 강조**: 스타트업 생태계 지원, 정보 접근성 개선 등
- **출처 명시 약속**: 공공데이터 활용 시 출처 표기 의무 이행 의지 표명

---

## 📡 API 명세 (예상)

> **주의**: 실제 API 승인 후 공공데이터포털의 "개발가이드" 참조 필수

### 1. 기본 정보

| 항목 | 내용 |
|------|------|
| **Base URL** | `http://apis.data.go.kr/1051000/...` (승인 후 확인) |
| **Method** | GET |
| **Response** | XML (기본) / JSON (선택 가능 시) |
| **인증** | Service Key (Query Parameter) |
| **호출 제한** | 하루 1,000~10,000회 (API마다 다름) |

### 2. 요청 파라미터 (예상)

| 파라미터 | 필수 | 타입 | 설명 | 예시 |
|---------|------|------|------|------|
| `serviceKey` | ⭕ | String | 인증키 (발급받은 API Key) | `"abc123..."` |
| `pageNo` | ⭕ | Integer | 페이지 번호 | `1` |
| `numOfRows` | ⭕ | Integer | 페이지당 결과 수 | `100` |
| `pblancNm` | ❌ | String | 공고명 검색어 | `"창업지원"` |
| `strtPblancDe` | ❌ | String | 공고 시작일 (YYYYMMDD) | `"20260501"` |
| `endPblancDe` | ❌ | String | 공고 종료일 (YYYYMMDD) | `"20260531"` |

### 3. 응답 구조 (XML 예상)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header>
    <resultCode>00</resultCode>
    <resultMsg>NORMAL SERVICE</resultMsg>
  </header>
  <body>
    <items>
      <item>
        <pblancId>2026001234</pblancId>              <!-- 공고 ID -->
        <pblancNm>2026년 예비창업패키지</pblancNm>   <!-- 공고명 -->
        <insttNm>중소벤처기업진흥공단</insttNm>      <!-- 주관기관 -->
        <regDt>20260428</regDt>                      <!-- ⭐ 등록일자 (정보가 세상에 나온 날) -->
        <bltnBgn>20260501</bltnBgn>                  <!-- 공고 게시 시작일 -->
        <bltnEnd>20260531</bltnEnd>                  <!-- 공고 게시 종료일 -->
        <rcritStrtDt>20260510</rcritStrtDt>          <!-- 모집(접수) 시작일자 -->
        <rcptBgn>20260510</rcptBgn>                  <!-- (별칭) 접수 시작일 -->
        <rcptEnd>20260525</rcptEnd>                  <!-- 접수 종료일 -->
        <scaleAmt>50000000000</scaleAmt>             <!-- 지원규모 (원) -->
        <pblancUrl>https://...</pblancUrl>           <!-- 원문 URL (가끔 null 또는 내부 URL) -->
        <atchFileId>FILE_12345</atchFileId>          <!-- 첨부파일 ID -->
        <pblancCn><![CDATA[                          <!-- ⚠️ 공고 내용 (HTML 태그 + 표 + 인라인 스타일 범벅) -->
          <p style="..."><span>지원자격</span>...</p>
          <table border="1"><tr><td>...</td></tr></table>
        ]]></pblancCn>
      </item>
      <!-- ... 더 많은 item -->
    </items>
    <totalCount>45</totalCount>
    <pageNo>1</pageNo>
    <numOfRows>10</numOfRows>
  </body>
</response>
```

> **필드 주의사항**:  
> - `regDt`(등록일자) ≠ `bltnBgn`(게시 시작일) ≠ `rcritStrtDt`(모집 시작일) — **셋이 다른 날짜**입니다.  
> - `pblancUrl`은 누락되거나 내부 관리자용 URL이 섞여 들어오는 경우가 있어 **Fallback 처리 필수**.  
> - `pblancCn`은 HTML 태그·표·CDATA 블록이 그대로 박혀 있는 비정형 텍스트 → **Bronze 단계에선 원형 보존**.

---

## 🗂️ 데이터 매핑 전략

### 1. ERD 매핑 (`raw_opportunity_data`)

| XML 필드 | 테이블 컬럼 | 변환 로직 |
|---------|----------|----------|
| `<pblancNm>` | `raw_title` | 그대로 저장 |
| `<pblancUrl>` | `source_url` | 원문 링크 (중복 체크 키). **null 시 Fallback 필수** |
| `<insttNm>` | `host_name` | 주관기관명 |
| `<rcptEnd>` | `deadline_at` | `YYYYMMDD` → `TIMESTAMPTZ(KST)` |
| `<regDt>` (1순위) → `<bltnBgn>` (2순위) | `published_at` | **'정보가 세상에 나온 날'** 기준. `regDt`가 없으면 `bltnBgn`으로 Fallback |
| `<pblancCn>` | `raw_content` | **HTML·CDATA 원형 그대로 저장** (Bronze 원칙) |
| `<scaleAmt>` | `raw_metadata["budget"]` | JSON에 숫자로 저장 |
| `<atchFileId>` | `raw_metadata["attachments"]` | 첨부파일 ID 배열 |
| `<rcritStrtDt>`, `<rcptBgn>`, `<rcptEnd>` | `raw_metadata["application_period"]` | 모집/접수 일정 — `published_at`과 분리 |
| `<bltnBgn>`, `<bltnEnd>` | `raw_metadata["bulletin_period"]` | 공고 게시 기간 |
| 전체 XML | `raw_metadata["original_xml"]` | 원본 보존 (파싱 실패 대비) |

#### 🌟 `published_at` 매핑 원칙

| 후보 필드 | 의미 | `published_at` 적합도 |
|---------|------|--------------------|
| `regDt` (등록일자) | 공무원이 시스템에 공고를 **등록한 날** | ⭐⭐⭐ (가장 정확) |
| `bltnBgn` (게시 시작일) | 공고가 외부에 **노출되기 시작한 날** | ⭐⭐ (차선책) |
| `rcritStrtDt` / `rcptBgn` (모집 시작일) | 신청 **접수**가 시작되는 날 | ❌ (전혀 다른 의미) |

> 시계열 분석에서 "이 시점에 이런 정책이 나왔다"를 추적하려면 **등록일/게시일**이 맞고, 모집 시작일은 **신청 마감 알림 기능**에서만 의미가 있습니다.

### 2. source_type 분류 전략

공고명에서 키워드를 추출하여 세분화:

| source_type | 매칭 키워드 | 의미 |
|------------|-----------|------|
| `SMES_STARTUP` | 창업, 예비창업, 초기창업 | 창업지원 |
| `SMES_RND` | 연구개발, R&D, 기술개발 | 연구개발 지원 |
| `SMES_EXPORT` | 수출, 해외진출, 글로벌 | 수출·해외진출 |
| `SMES_SCALE_UP` | 스케일업, 성장, 도약 | 성장 지원 |
| `SMES_GRANT` | (그 외) | 일반 지원사업 |

---

## ⚡ 공공 API 4대 함정 (반드시 코드에 반영)

공공데이터포털 API는 "데이터가 비어있거나, 타입이 맘대로 바뀌는" 엣지 케이스가 많습니다. 구현 전 반드시 아래 4가지 함정을 코드에 미리 방어해두어야 운영 단계에서 깨지지 않습니다.

---

### 함정 1: 🚨 `xmltodict`의 List vs Dict 변환 함정

**문제**:
`xmltodict`는 동일한 태그가 **여러 개일 때만 List**로 변환하고, **1개일 때는 Dict**로 변환합니다.

```python
# items가 2개 이상일 때
items = [
    {"pblancNm": "공고A", ...},
    {"pblancNm": "공고B", ...},
]

# items가 1개일 때 (List가 아닌 Dict!)
items = {"pblancNm": "공고A", ...}

# items가 0개일 때 (구조 자체가 None)
items = None
```

**해결 - 강제 리스트화 헬퍼**:

```python
def _ensure_list(value) -> list:
    """xmltodict 결과를 항상 list로 보장"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]

# 사용
items_raw = data.get("response", {}).get("body", {}).get("items", {})
# items 자체가 빈 문자열로 올 수도 있음
if not items_raw or not isinstance(items_raw, dict):
    return []

items = _ensure_list(items_raw.get("item"))
```

---

### 함정 2: ⏰ `published_at`과 '모집 시작일' 혼동

**문제**:
공공기관 공고는 **"3월 1일에 공고를 등록(`regDt`)하고, 3월 5일부터 게시(`bltnBgn`), 3월 15일부터 접수(`rcritStrtDt`)"** 처럼 날짜가 3개 이상입니다.  
`rcritStrtDt`(모집 시작일)를 `published_at`에 넣으면 시계열 분석이 **2주씩 어긋납니다**.

**해결 - 우선순위 기반 Fallback**:

```python
def _resolve_published_at(item: dict) -> Optional[datetime]:
    """등록일(regDt) > 게시 시작일(bltnBgn) 순서로 fallback"""
    for field in ("regDt", "creatDt", "bltnBgn"):
        value = item.get(field)
        if value:
            parsed = _parse_date_to_kst(value)
            if parsed:
                return parsed
    return None

# 모집 시작일은 published_at이 아니라 raw_metadata["application_period"]로!
raw_metadata["application_period"] = {
    "start": item.get("rcritStrtDt") or item.get("rcptBgn"),
    "end": item.get("rcptEnd"),
}
```

---

### 함정 3: 🧹 `pblancCn`의 CDATA / HTML 태그 — 정제하지 않기

**현상**:
중기부 API의 `pblancCn`(공고 내용) 필드는 공무원들이 한글·워드에서 복사 붙여넣기 한 결과물이라 다음과 같은 **노이즈가 그대로 들어옵니다**:

- `<![CDATA[...]]>` 블록
- `<table>`, `<tr>`, `<td>` 표 태그 (제일 중요한 지원 자격이 표 안에 있음!)
- `<span style="color:#FF0000;font-size:14pt;">` 같은 인라인 스타일
- 깨진 한글 인코딩, `&nbsp;` 등 HTML 엔티티

**잘못된 접근** ❌:

```python
# Collector에서 BeautifulSoup으로 무리하게 정제 → 표 내용이 통째로 뭉개짐
clean_text = BeautifulSoup(pblancCn, "html.parser").get_text(separator=" ", strip=True)
```

**Bronze 계층 원칙 (올바른 접근)** ⭕:

```python
raw_content = item.get("pblancCn", "")
# HTML 태그 제거하지 않고 원형 그대로 저장
return OpportunityCollectDto(
    ...,
    raw_content=raw_content,  # HTML 포함 원본 그대로
)
```

> **Silver 계층 전략**:  
> Silver 단계에서 LLM에게 *"이 HTML 내용에서 지원 자격과 지원 내용만 표 구조를 유지해서 추출해 줘"* 라고 프롬프트로 던지면, 표 구조까지 살려서 깔끔하게 추출할 수 있습니다. Bronze에서 미리 지우면 **복원이 불가능**합니다.

---

### 함정 4: 🔗 `source_url`이 비어있거나 잘못된 URL일 때 Fallback

**현상**:
- `pblancUrl`이 `null` 또는 빈 문자열로 오는 경우 (특히 임시 저장 공고)
- 내부 관리자용 URL (`https://admin.bizinfo.go.kr/...`)이 잘못 들어오는 경우
- 위 경우 그대로 적재하면 **`source_url NOT NULL` 제약 위반** 또는 사용자가 접속할 수 없는 죽은 링크 적재

**해결 - 3단계 Fallback**:

```python
BIZINFO_BASE = "https://www.bizinfo.go.kr"
BIZINFO_DETAIL = "https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId="

def _resolve_source_url(item: dict) -> str:
    """source_url 3단계 Fallback"""
    # 1순위: API가 준 pblancUrl이 정상 외부 URL인지 검증
    url = (item.get("pblancUrl") or "").strip()
    if url.startswith("https://www.bizinfo.go.kr") or url.startswith("http://www.bizinfo.go.kr"):
        return url
    
    # 2순위: 공고 ID로 기업마당 상세 페이지 URL 조합
    pblanc_id = (item.get("pblancId") or "").strip()
    if pblanc_id:
        return f"{BIZINFO_DETAIL}{pblanc_id}"
    
    # 3순위: 기업마당 메인 (최후의 방어)
    return BIZINFO_BASE
```

> 이렇게 하면 NOT NULL 제약을 절대 위반하지 않고, 사용자가 클릭했을 때 최소한 기업마당 메인으로는 연결됩니다.

---

## 🛠️ 구현 전략

### Phase 1: 기본 수집 파이프라인 (현재)

**목표**: XML 파싱 + DB 적재까지 완료

```python
# backend/domain/master/hub/services/collectors/economic/smes_collector.py
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Any

import aiohttp
import xmltodict

from domain.master.models.transfer.opportunity_collect_dto import OpportunityCollectDto

logger = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))

# Fallback URL (함정 4)
BIZINFO_BASE = "https://www.bizinfo.go.kr"
BIZINFO_DETAIL = "https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId="


def _ensure_list(value: Any) -> list:
    """xmltodict 결과 → 항상 list로 보장 (함정 1 방어)"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _parse_date_to_kst(date_str: Optional[str]) -> Optional[datetime]:
    """YYYYMMDD 또는 YYYY-MM-DD → datetime(KST)"""
    if not date_str:
        return None
    s = str(date_str).strip().replace("-", "")
    if len(s) != 8:
        return None
    try:
        return datetime.strptime(s, "%Y%m%d").replace(tzinfo=_KST)
    except ValueError:
        return None


class SmesOpenAPICollector:
    """중소벤처기업부 사업공고 OpenAPI Collector"""

    BASE_URL = "http://apis.data.go.kr/1051000/smes/getBizAnnouncement"  # 예시 (실제 URL은 승인 후 확인)

    def __init__(self, service_key: str):
        self.service_key = service_key

    async def collect(
        self,
        max_items: int = 100,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[OpportunityCollectDto]:
        """
        중소벤처기업부 사업공고 수집

        Args:
            max_items: 최대 수집 건수
            start_date: 공고 시작일 (YYYYMMDD)
            end_date: 공고 종료일 (YYYYMMDD)
        """
        params = {
            "serviceKey": self.service_key,
            "pageNo": "1",
            "numOfRows": str(min(max_items, 100)),
        }
        if start_date:
            params["strtPblancDe"] = start_date
        if end_date:
            params["endPblancDe"] = end_date

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(self.BASE_URL, params=params) as resp:
                    if resp.status != 200:
                        raise RuntimeError(f"중소벤처 API 호출 실패: HTTP {resp.status}")
                    xml_text = await resp.text()
            except aiohttp.ClientError as e:
                raise RuntimeError(f"중소벤처 API 네트워크 오류: {e}") from e

        try:
            data = xmltodict.parse(xml_text)
        except Exception as e:
            raise RuntimeError(f"중소벤처 XML 파싱 실패: {e}") from e

        # 응답 헤더 검증
        header = data.get("response", {}).get("header", {}) or {}
        result_code = header.get("resultCode", "")
        if result_code not in ("00", "0"):
            raise RuntimeError(
                f"중소벤처 API 오류: code={result_code}, msg={header.get('resultMsg', 'Unknown')}"
            )

        # 함정 1: items가 dict / None / 빈 문자열일 수 있음
        body = data.get("response", {}).get("body", {}) or {}
        items_wrapper = body.get("items")
        if not items_wrapper or not isinstance(items_wrapper, dict):
            return []
        items = _ensure_list(items_wrapper.get("item"))

        dtos: list[OpportunityCollectDto] = []
        for item in items:
            try:
                dto = self._parse_item(item)
                if dto:
                    dtos.append(dto)
            except Exception:
                logger.warning("중소벤처 아이템 파싱 실패, 스킵: %s", item.get("pblancId"))
                continue
        return dtos

    # ------------------------------------------------------------------
    # Helpers (4대 함정 방어)
    # ------------------------------------------------------------------

    def _resolve_source_url(self, item: dict) -> str:
        """함정 4: source_url 3단계 Fallback"""
        url = (item.get("pblancUrl") or "").strip()
        if url.startswith(("https://www.bizinfo.go.kr", "http://www.bizinfo.go.kr")):
            return url

        pblanc_id = (item.get("pblancId") or "").strip()
        if pblanc_id:
            return f"{BIZINFO_DETAIL}{pblanc_id}"

        return BIZINFO_BASE

    def _resolve_published_at(self, item: dict) -> Optional[datetime]:
        """함정 2: regDt > creatDt > bltnBgn 순서로 fallback (모집시작일 사용 금지)"""
        for field in ("regDt", "creatDt", "bltnBgn"):
            parsed = _parse_date_to_kst(item.get(field))
            if parsed:
                return parsed
        return None

    def _parse_item(self, item: dict) -> Optional[OpportunityCollectDto]:
        """XML item → OpportunityCollectDto 변환"""
        raw_title = (item.get("pblancNm") or "").strip()
        if not raw_title:
            return None

        host_name = (item.get("insttNm") or "").strip() or None

        # 함정 2: published_at은 등록일/게시일 기준 (모집시작일 ❌)
        published_at = self._resolve_published_at(item)
        deadline_at = _parse_date_to_kst(item.get("rcptEnd") or item.get("rcritEndDt"))

        # 함정 4: source_url Fallback
        source_url = self._resolve_source_url(item)

        # 함정 3: pblancCn은 HTML/CDATA 원형 그대로 저장 (정제 X)
        raw_content = item.get("pblancCn") or None

        source_type = self._classify_source_type(raw_title)

        raw_metadata = {
            "announcement_id": item.get("pblancId"),
            "bulletin_period": {
                "start": item.get("bltnBgn"),
                "end": item.get("bltnEnd"),
            },
            "application_period": {
                "start": item.get("rcritStrtDt") or item.get("rcptBgn"),
                "end": item.get("rcptEnd") or item.get("rcritEndDt"),
            },
            "budget": item.get("scaleAmt"),
            "attachment_file_id": item.get("atchFileId"),
            "original_pblanc_url": item.get("pblancUrl"),  # 원본 URL도 보존
            "original_xml": item,  # 원본 보존 (파싱 실패 대비 / 추후 재처리용)
        }

        return OpportunityCollectDto(
            source_type=source_type,
            source_url=source_url,
            raw_title=raw_title,
            host_name=host_name,
            raw_content=raw_content,
            deadline_at=deadline_at,
            published_at=published_at,
            raw_metadata=raw_metadata,
        )

    def _classify_source_type(self, title: str) -> str:
        """공고명으로 source_type 분류"""
        if any(k in title for k in ["창업", "예비창업", "초기창업"]):
            return "SMES_STARTUP"
        if any(k in title for k in ["연구개발", "R&D", "기술개발", "R&amp;D"]):
            return "SMES_RND"
        if any(k in title for k in ["수출", "해외진출", "글로벌"]):
            return "SMES_EXPORT"
        if any(k in title for k in ["스케일업", "성장", "도약"]):
            return "SMES_SCALE_UP"
        return "SMES_GRANT"
```

### Phase 2: 서비스 계층 통합

```python
# backend/domain/master/hub/services/bronze_opportunity_ingest_service.py
class BronzeOpportunityIngestService:
    def __init__(self, db: AsyncSession, config: dict):
        self.db = db
        self.config = config
        self._opportunity_repo = OpportunityRepository(db)
    
    async def ingest_smes(
        self,
        max_items: int = 100,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """중소벤처기업부 공고 수집"""
        service_key = self.config.get("SMES_SERVICE_KEY")
        if not service_key:
            raise ValueError("SMES_SERVICE_KEY가 설정되지 않았습니다")
        
        collector = SmesOpenAPICollector(service_key)
        
        try:
            dtos = await collector.collect(
                max_items=max_items,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception:
            # logger.exception("중소벤처 수집 실패")
            dtos = []
        
        inserted = await self._opportunity_repo.insert_many_skip_duplicates(dtos)
        
        return {
            "source": "SMES",
            "fetched": len(dtos),
            "inserted": inserted,
            "duplicates": len(dtos) - inserted,
        }
```

### Phase 3: API 엔드포인트

```python
# backend/api/v1/master/master_router.py
@router.post("/bronze/opportunity/smes")
async def run_smes_opportunity_bronze(
    max_items: int = Query(100, ge=1, le=500, description="최대 수집 건수"),
    start_date: Optional[str] = Query(None, description="공고 시작일 (YYYYMMDD)"),
    end_date: Optional[str] = Query(None, description="공고 종료일 (YYYYMMDD)"),
    db: AsyncSession = Depends(get_db),
):
    """중소벤처기업부 사업공고 수집"""
    svc = BronzeOpportunityIngestService(db, app_config)
    try:
        return await svc.ingest_smes(
            max_items=max_items,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception:
        # logger.exception("중소벤처 Bronze ingest 실패")
        raise HTTPException(
            status_code=502,
            detail="중소벤처 API 수집 중 오류가 발생했습니다.",
        ) from None
```

---

## ⚠️ 주의사항 및 운영 가이드

### 1. API 호출 제한 대응

- **일일 한도**: 공공 API는 보통 **1,000~10,000회/일** 제한
- **전략**: 매일 1회 (새벽 3시) 전체 공고 수집 + 실시간 업데이트는 하지 않음
- **페이지네이션**: `numOfRows=100`으로 설정 후 `pageNo`를 증가시키며 전체 데이터 수집

### 2. 공공 API 불안정 대응

공공데이터포털 API는 서버 점검·트래픽 폭주로 Timeout이 자주 발생합니다.

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import aiohttp

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
)
async def fetch_with_retry(url: str, params: dict):
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, params=params) as resp:
            return await resp.text()
```

### 3. XML 파싱 에러 처리

- `xmltodict.parse()` 실패 시 로깅 후 빈 리스트 반환
- 개별 item 파싱 실패 시 해당 item만 스킵하고 나머지 진행
- **함정 1 ~ 함정 4** (위 「공공 API 4대 함정」 섹션) 방어 코드 필수:
  - `_ensure_list()`로 단일/복수 응답 정규화
  - `_resolve_published_at()`으로 등록일·게시일·모집일 구분
  - `pblancCn`은 HTML 원형 그대로 `raw_content`에 저장
  - `_resolve_source_url()`로 NOT NULL 방어용 3단계 Fallback

### 4. 환경변수 관리

```bash
# .env
SMES_SERVICE_KEY="your_service_key_here_without_encoding"
```

> **주의**: Service Key는 URL 인코딩하지 않은 **원본 키** 그대로 저장  
> (일부 API는 자동으로 인코딩하므로 중복 인코딩 시 오류)

---

## 📝 구현 체크리스트

### API 신청 단계
- [ ] 공공데이터포털 회원가입
- [ ] 중소벤처기업부_사업공고 API 활용신청
- [ ] 활용목적 작성 (위 가이드 참고)
- [ ] API 승인 대기 (1~2영업일)
- [ ] Service Key 발급 확인
- [ ] `.env`에 `SMES_SERVICE_KEY` 등록

### 코드 구현 단계
- [ ] `OpportunityCollectDto` 모델 확인/수정 (`raw_content` 필드 포함)
- [ ] `smes_collector.py` 작성
  - [ ] **함정 1**: `_ensure_list()` 헬퍼로 단일/복수 응답 정규화
  - [ ] **함정 2**: `_resolve_published_at()`에서 `regDt > creatDt > bltnBgn` 순서 fallback (모집시작일 사용 금지)
  - [ ] **함정 3**: `pblancCn`을 HTML 정제하지 않고 `raw_content`에 원형 저장
  - [ ] **함정 4**: `_resolve_source_url()` 3단계 Fallback (정상 URL → 공고 ID 조합 → 기업마당 메인)
  - [ ] 모든 날짜 필드에 KST 타임존 명시
- [ ] `bronze_opportunity_ingest_service.py` 작성 (DART 패턴 — try/except로 빈 결과 반환)
- [ ] `master_router.py`에 엔드포인트 추가
- [ ] 통합 테스트 스크립트 작성 (`scripts/smes_integration_test.py`)

### 운영 단계
- [ ] 수동 API 호출 테스트
- [ ] 스케줄러 등록 (매일 새벽 3시)
- [ ] 로그 모니터링 (API 에러율, 중복 건수)
- [ ] 대시보드에서 데이터 확인

---

## 🔗 관련 문서

- `backend/docs/erd.md` — `raw_opportunity_data` 테이블 스키마
- `RAW_ECONOMIC_DATA_COLLECTION_GUIDE.md` — 전체 수집 출처 개요
- `DART_ECONOMIC_ENHANCEMENT_STRATEGY.md` — DART API 연동 참고
- `WOWTALE_RSS_COLLECTION_GUIDE.md` — RSS 수집 참고

---

## 💡 다음 단계

1. **API 신청 및 승인 대기** (현재 단계)
2. **Service Key 발급 후 환경변수 등록**
3. **`smes_collector.py` 구현**
4. **통합 테스트 실행**
5. **운영 환경 배포 및 스케줄러 등록**

---

**작성자**: Cursor AI Agent  
**검토 필요**: API 승인 후 실제 응답 구조 확인 및 파싱 로직 보정
