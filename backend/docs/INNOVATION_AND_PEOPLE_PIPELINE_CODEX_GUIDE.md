# Bronze Innovation & People Pipeline — Codex 구현 가이드

**작성일:** 2026-06-07  
**대상:** Codex (AI 코딩 어시스턴트)  
**우선순위 기준:** P0 = 이번 태스크에서 반드시 구현 / P1 = 다음 태스크 / P2 = 장기 후보

---

## 0. 현황 요약 및 편향 분석

### 0-1. 현재 raw_innovation_data 상태

`raw_innovation_data` 테이블은 ERD에 DDL이 정의되어 있으나 **인프라가 전혀 없다**.

| 항목 | 상태 |
|------|------|
| ORM 모델 | ❌ 없음 |
| DTO | ❌ 없음 |
| Repository | ❌ 없음 |
| Ingest Service | ❌ 없음 |
| Collector 디렉토리 | ❌ 없음 |
| Alembic 마이그레이션 | ❌ 없음 (테이블 자체는 DDL에만 있음) |

KIPRIS 특허 컬렉터(`kipris_patent_collector.py`)는 혁신 신호이지만 현재 `raw_economic_data`에 적재 중이다.  
**이 가이드에서 KIPRIS 마이그레이션은 다루지 않는다.** KIPRIS는 `raw_economic_data`에 그대로 두고, 신규 혁신 소스만 `raw_innovation_data`에 적재한다.

### 0-2. 현재 수집 편향 (AI/IT 쏠림 진단)

현재 `raw_economic_data` 기준 섹터별 커버리지:

| 섹터 | 커버리지 | 주요 소스 |
|------|----------|---------|
| AI/ML·소프트웨어 | 🟢 과잉 | KIPRIS(AI_ML), Naver DataLab(AI_ML), MSIT, DART, VC 뉴스 |
| 바이오/헬스케어 | 🟡 보통 | KIPRIS(BIOHEALTH), MFDS 허가, DART B |
| 에너지/기후 | 🟡 보통 | KIPRIS(ENERGY_CLIMATE), Yahoo ETF |
| 반도체/소재 | 🟡 보통 | KIPRIS(SEMICONDUCTOR) |
| 모빌리티/자동차 | 🟡 보통 | KIPRIS(MOBILITY) |
| 핀테크/금융 | 🟡 보통 | KIPRIS(FINTECH), BOK ECOS, Yahoo Finance |
| **콘텐츠/크리에이터** | 🔴 공백 | 없음 |
| **교육/에듀테크** | 🔴 공백 | 없음 |
| **식품/농업** | 🔴 공백 | 없음 |
| **패션/뷰티(K-beauty)** | 🔴 공백 | 없음 |
| **사회서비스/복지** | 🔴 공백 | 없음 |
| **물류/유통** | 🔴 공백 | 없음 |
| **관광/여행/레저** | 🔴 공백 | 없음 |

Roadmap 타깃 사용자(10대 후반~30대 초반)의 직업 탐색 범위는 AI 개발자에만 국한되지 않는다.  
현재 수집 체계로는 크리에이터, 교사, 셰프, 물류 기획자, 사회복지사 등의 커리어 경로에 대한 **선행 지표가 없다**.

---

## 1. 구현할 파일 구조 (전체)

```
backend/
├── alembic/versions/
│   └── xxxx_create_raw_innovation_data_raw_people_data.py   ← (1) Alembic 마이그레이션
│
├── domain/master/
│   ├── models/
│   │   ├── bases/
│   │   │   ├── raw_innovation_data.py                        ← (2) ORM 모델
│   │   │   └── raw_people_data.py                            ← (3) ORM 모델
│   │   └── transfer/
│   │       ├── innovation_collect_dto.py                     ← (4) DTO
│   │       └── people_collect_dto.py                         ← (5) DTO
│   │
│   └── hub/
│       ├── repositories/
│       │   ├── innovation_repository.py                      ← (6) Repository
│       │   └── people_repository.py                          ← (7) Repository
│       │
│       └── services/
│           ├── bronze_innovation_ingest_service.py           ← (8) Ingest Service
│           ├── bronze_people_ingest_service.py               ← (9) Ingest Service
│           │
│           └── collectors/
│               ├── innovation/
│               │   ├── __init__.py
│               │   ├── arxiv/
│               │   │   ├── __init__.py
│               │   │   └── arxiv_papers_collector.py         ← (10) P0 컬렉터
│               │   ├── github/
│               │   │   ├── __init__.py
│               │   │   └── github_trending_collector.py      ← (11) P0 컬렉터
│               │   └── kocca/
│               │       ├── __init__.py
│               │       └── kocca_content_collector.py        ← (12) P1 컬렉터
│               │
│               └── people/
│                   ├── __init__.py
│                   ├── worknet/
│                   │   ├── __init__.py
│                   │   └── worknet_job_info_collector.py     ← (13) P0 컬렉터
│                   └── hrdnet/
│                       ├── __init__.py
│                       └── hrdnet_training_collector.py      ← (14) P0 컬렉터
│
├── api/v1/master/
│   └── master_routor.py                                      ← (15) 라우터 엔드포인트 추가
│
└── core/
    └── scheduler.py                                          ← (16) 잡 추가
```

---

## 2. 인프라 레이어 구현 (1~9번)

### (1) Alembic 마이그레이션

`alembic revision --autogenerate -m "add_raw_innovation_data_and_raw_people_data"` 실행 후 생성 파일 검토.

테이블 DDL은 `backend/docs/erd.md` §4를 참고한다.  
**UNIQUE 제약**: `raw_innovation_data`는 `source_url` UNIQUE(`uq_raw_innovation_data_source_url`).  
`raw_people_data`는 `(source_type, keyword_or_job, reference_date)` 3-컬럼 UNIQUE(`uq_raw_people_data_source_keyword_date`).

### (2) ORM 모델 — `raw_innovation_data.py`

파일 경로: `backend/domain/master/models/bases/raw_innovation_data.py`

```python
from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from core.database import Base

class RawInnovationData(Base):
    __tablename__ = "raw_innovation_data"
    __table_args__ = (
        UniqueConstraint("source_url", name="uq_raw_innovation_data_source_url"),
        {"comment": "Bronze — 특허·논문·오픈소스 등 혁신 흐름 원천"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author_or_assignee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    abstract_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

### (3) ORM 모델 — `raw_people_data.py`

파일 경로: `backend/domain/master/models/bases/raw_people_data.py`

```python
from __future__ import annotations
from datetime import date, datetime
from sqlalchemy import BigInteger, Date, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from core.database import Base

class RawPeopleData(Base):
    __tablename__ = "raw_people_data"
    __table_args__ = (
        UniqueConstraint(
            "source_type", "keyword_or_job", "reference_date",
            name="uq_raw_people_data_source_keyword_date",
        ),
        {"comment": "Bronze — 검색량·채용·훈련 수요 등 사람·역량 수요 원천"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    keyword_or_job: Mapped[str] = mapped_column(String(100), nullable=False)
    search_volume_or_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reference_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

### (4) DTO — `innovation_collect_dto.py`

파일 경로: `backend/domain/master/models/transfer/innovation_collect_dto.py`

```python
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field

class InnovationCollectDto(BaseModel):
    source_type: str = Field(..., max_length=50)
    source_url: Optional[str] = Field(default=None)
    title: str = Field(..., max_length=500)
    author_or_assignee: Optional[str] = Field(default=None, max_length=255)
    abstract_text: Optional[str] = Field(default=None)
    raw_metadata: Optional[dict[str, Any]] = Field(default=None)
    published_at: Optional[datetime] = Field(default=None)
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_config = {"str_strip_whitespace": True}
```

### (5) DTO — `people_collect_dto.py`

파일 경로: `backend/domain/master/models/transfer/people_collect_dto.py`

```python
from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field

class PeopleCollectDto(BaseModel):
    source_type: str = Field(..., max_length=50)
    source_url: Optional[str] = Field(default=None)
    keyword_or_job: str = Field(..., max_length=100)
    search_volume_or_count: Optional[int] = Field(default=None)
    raw_metadata: Optional[dict[str, Any]] = Field(default=None)
    reference_date: Optional[date] = Field(default=None)
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_config = {"str_strip_whitespace": True}
```

### (6) Repository — `innovation_repository.py`

파일 경로: `backend/domain/master/hub/repositories/innovation_repository.py`

`economic_repository.py` 패턴을 그대로 따른다. 핵심 메서드:

```python
class InnovationRepository(BaseRepository):
    async def insert_many_skip_duplicates(self, rows: list[InnovationCollectDto]) -> int:
        # source_url UNIQUE → ON CONFLICT DO NOTHING
        # 배치 단위 1회 커밋
        ...

    async def latest_by_source_type(self, source_type: str) -> RawInnovationData | None:
        # 워터마크 조회용 — ORDER BY published_at DESC LIMIT 1
        ...
```

### (7) Repository — `people_repository.py`

파일 경로: `backend/domain/master/hub/repositories/people_repository.py`

```python
class PeopleRepository(BaseRepository):
    async def insert_many_skip_duplicates(self, rows: list[PeopleCollectDto]) -> int:
        # (source_type, keyword_or_job, reference_date) UNIQUE → ON CONFLICT DO NOTHING
        ...

    async def latest_reference_date(self, source_type: str) -> date | None:
        # 워터마크 조회용
        ...
```

### (8) Ingest Service — `bronze_innovation_ingest_service.py`

파일 경로: `backend/domain/master/hub/services/bronze_innovation_ingest_service.py`

`bronze_economic_ingest_service.py` 구조를 그대로 따른다.

```python
class BronzeInnovationIngestService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        github_token: str | None = None,
    ) -> None:
        self._session = session
        self._github_token = github_token
        self._repo = InnovationRepository(session)

    async def ingest_arxiv(self, *, max_results: int = 100) -> dict[str, Any]: ...
    async def ingest_github_trending(self, *, days_back: int = 7) -> dict[str, Any]: ...
    # P1
    async def ingest_kocca(self, *, year: int | None = None) -> dict[str, Any]: ...
```

### (9) Ingest Service — `bronze_people_ingest_service.py`

파일 경로: `backend/domain/master/hub/services/bronze_people_ingest_service.py`

```python
class BronzePeopleIngestService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        worknet_api_key: str | None = None,
        hrdnet_api_key: str | None = None,
        saramin_api_key: str | None = None,
    ) -> None: ...

    async def ingest_worknet_job_info(self) -> dict[str, Any]: ...
    async def ingest_hrdnet_training(self) -> dict[str, Any]: ...
    # P1
    async def ingest_saramin_jobs(self, *, keyword: str | None = None) -> dict[str, Any]: ...
```

---

## 3. P0 컬렉터 — 상세 API 스펙

### (10) arXiv Papers Collector

**파일:** `collectors/innovation/arxiv/arxiv_papers_collector.py`  
**테이블:** `raw_innovation_data`  
**source_type:** `INNOVATION_ARXIV_KR`  
**스케줄:** 주간 (weekly)  
**API 키:** 불필요 (무료 공개 API)

#### API 엔드포인트

```
GET https://export.arxiv.org/api/query
```

#### 쿼리 파라미터

| 파라미터 | 값 | 설명 |
|---------|---|------|
| `search_query` | 아래 표 참고 | 카테고리 + 날짜 필터 |
| `start` | `0` | 페이지 오프셋 |
| `max_results` | `50` | 카테고리당 최대 수 |
| `sortBy` | `submittedDate` | 최신순 |
| `sortOrder` | `descending` | 내림차순 |

#### 카테고리별 쿼리 (다양성 확보)

```python
_ARXIV_CATEGORIES: list[tuple[str, str, str]] = [
    # (group_name, arxiv_cat, description)
    ("AI_CS",         "cs.AI",       "Artificial Intelligence"),
    ("ML_CS",         "cs.LG",       "Machine Learning"),
    ("BIOINFO",       "q-bio.GN",    "Genomics / 생명정보"),
    ("BIOMEDICAL",    "q-bio.QM",    "Quantitative Methods / 바이오의약"),
    ("ECONOMICS",     "econ.GN",     "General Economics / 경제학"),
    ("FINANCE",       "q-fin.GN",    "General Finance / 금융"),
    ("PHYSICS_APPLY", "physics.app-ph", "Applied Physics / 소재·에너지"),
    ("ENV_SCI",       "physics.ao-ph",  "Atmospheric·Ocean / 기후·환경"),
    ("ROBOTICS",      "cs.RO",       "Robotics / 자동화"),
    ("SOCIAL_INFO",   "cs.SI",       "Social and Information Networks"),
    ("ECON_LABOR",    "econ.GN",     "노동경제·인적자본"),
]
```

#### 날짜 필터

쿼리 예시 (최근 7일):
```
search_query=cat:cs.AI+AND+submittedDate:[20260531000000+TO+20260607235959]
```
날짜 포맷: `YYYYMMDDHHMMSS`

#### 응답 파싱 (Atom XML)

```python
import xml.etree.ElementTree as ET

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}

root = ET.fromstring(xml_text)
for entry in root.findall("atom:entry", NS):
    arxiv_id = entry.find("atom:id", NS).text.split("/abs/")[-1]  # e.g. "2406.12345"
    title = entry.find("atom:title", NS).text.strip()
    summary = entry.find("atom:summary", NS).text.strip()
    published = entry.find("atom:published", NS).text  # ISO 8601
    authors = [a.find("atom:name", NS).text for a in entry.findall("atom:author", NS)]
```

#### source_url (멱등성 키)

```python
source_url = f"https://arxiv.org/abs/{arxiv_id}"  # 논문별 UNIQUE
```

#### InnovationCollectDto 매핑

```python
InnovationCollectDto(
    source_type="INNOVATION_ARXIV_KR",
    source_url=f"https://arxiv.org/abs/{arxiv_id}",
    title=title[:500],
    author_or_assignee=", ".join(authors[:3])[:255],
    abstract_text=summary[:2000],
    raw_metadata={
        "arxiv_id": arxiv_id,
        "category": cat,
        "group_name": group_name,
        "author_count": len(authors),
        "data_role": "RESEARCH_TREND_SIGNAL",
    },
    published_at=datetime.fromisoformat(published),
)
```

#### 워터마크

```python
@dataclass(frozen=True)
class ArxivWatermark:
    last_week_start: str | None = None  # YYYYMMDD
```

이번 주 시작일이 워터마크와 동일하면 skip.

#### Rate limiting

카테고리 간 `await asyncio.sleep(1.0)` (arXiv 권장: 1초 간격).  
1회 실행 = 11개 카테고리 × 50건 = 최대 550건/주.

---

### (11) GitHub Trending Collector

**파일:** `collectors/innovation/github/github_trending_collector.py`  
**테이블:** `raw_innovation_data`  
**source_type:** `INNOVATION_GITHUB_TRENDING`  
**스케줄:** 주간 (weekly)  
**API 키:** `GITHUB_TOKEN` (선택 — 없으면 60 req/hr, 있으면 5,000 req/hr)

#### API 엔드포인트

```
GET https://api.github.com/search/repositories
```

#### 파라미터

```python
params = {
    "q": f"created:>={week_start_str} stars:>50",  # 이번 주 생성 + 스타 50+ 레포
    "sort": "stars",
    "order": "desc",
    "per_page": 30,  # 토픽당 30개
}
headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {token}",  # 선택
    "X-GitHub-Api-Version": "2022-11-28",
}
```

#### 토픽 기반 다양성 확보

```python
_GITHUB_TOPIC_GROUPS: list[tuple[str, list[str]]] = [
    ("AI_ML",        ["machine-learning", "deep-learning", "llm", "generative-ai"]),
    ("BIOINFO",      ["bioinformatics", "genomics", "drug-discovery"]),
    ("FINTECH",      ["fintech", "defi", "blockchain"]),
    ("EDUTECH",      ["education", "e-learning", "edtech"]),
    ("CLIMATE",      ["climate-change", "carbon-neutral", "renewable-energy"]),
    ("HEALTHTECH",   ["healthcare", "medical-imaging", "digital-health"]),
    ("FOODTECH",     ["food-tech", "agriculture", "precision-farming"]),
    ("CREATOR_TOOL", ["creative-tools", "design", "content-creation"]),
    ("ROBOTICS",     ["robotics", "autonomous-vehicles", "drone"]),
    ("SOCIAL_GOOD",  ["social-impact", "nonprofit", "civic-tech"]),
]
```

쿼리 예시:
```
q=topic:machine-learning+created:>=2026-06-01+stars:>50
```

#### source_url (멱등성 키)

```python
# 동일 레포가 주마다 재수집될 수 있으므로 주(week) 단위 멱등성 키
source_url = f"https://github.com/{owner}/{repo}?week={week_start_str}"
```

#### InnovationCollectDto 매핑

```python
InnovationCollectDto(
    source_type="INNOVATION_GITHUB_TRENDING",
    source_url=source_url,
    title=f"[{group_name}] {full_name} ⭐{stars} ({week_start_str}W)"[:500],
    author_or_assignee=owner[:255],
    abstract_text=(repo_json.get("description") or "")[:2000],
    raw_metadata={
        "full_name": full_name,
        "stars": stars,
        "forks": forks,
        "language": language,
        "topics": topics,
        "group_name": group_name,
        "week_start": week_start_str,
        "data_role": "OPENSOURCE_MOMENTUM_SIGNAL",
    },
    published_at=datetime.fromisoformat(created_at.rstrip("Z") + "+00:00"),
)
```

---

### (13) WorkNet 직업정보 Collector

**파일:** `collectors/people/worknet/worknet_job_info_collector.py`  
**테이블:** `raw_people_data`  
**source_type:** `PEOPLE_WORKNET_JOB`  
**스케줄:** 월간 (monthly — 매월 1일, APScheduler CronTrigger `day=1`)  
**API 키:** `WORKNET_API_KEY` (고용24 OpenAPI 회원가입 후 발급, 무료)

#### API 엔드포인트

```
GET https://www.work.go.kr/cjob/openApi/getJobList.do
```

#### 파라미터

```python
params = {
    "apiKey": api_key,
    "callTp": "L",   # 목록 조회
    "pageNum": 1,
    "pageSize": 100,
    "occupation": "",  # 빈값 = 전 직종
    "returnType": "JSON",
}
```

#### 직종 코드 범위 (다양성 핵심)

`occupation` 파라미터에 코드를 넣어 섹터별 순회.

```python
_WORKNET_SECTORS: list[tuple[str, str]] = [
    ("IT_SOFTWARE",      "23"),   # IT·인터넷·통신
    ("ENGINEERING",      "09"),   # 기계·금속
    ("BIOHEALTH",        "07"),   # 의료·보건·복지
    ("EDUCATION",        "12"),   # 교육·연구·법률
    ("CREATIVE",         "04"),   # 문화·예술·방송·스포츠
    ("FOOD_SERVICE",     "11"),   # 외식·음식서비스
    ("DISTRIBUTION",     "14"),   # 유통·무역·운송
    ("CONSTRUCTION",     "03"),   # 건설
    ("AGRICULTURE",      "01"),   # 농림·어업
    ("FINANCE",          "08"),   # 금융·보험
    ("PUBLIC_SERVICE",   "21"),   # 공무원·공공서비스
    ("BEAUTY_FASHION",   "20"),   # 미용·숙박·여행·오락
    ("WELFARE",          "17"),   # 사회복지
]
```

#### 응답에서 핵심 지표 추출

```python
# 직업별 채용공고 건수 (search_volume_or_count)
job_count = item.get("totalCnt", 0)  # 해당 직종 현재 공고 수
job_name = item.get("jobNm", "")
```

#### PeopleCollectDto 매핑

```python
PeopleCollectDto(
    source_type="PEOPLE_WORKNET_JOB",
    source_url=f"https://www.work.go.kr/cjob/openApi/getJobList.do?occupation={occ_code}",
    keyword_or_job=job_name[:100],
    search_volume_or_count=job_count,
    raw_metadata={
        "occupation_code": occ_code,
        "sector_name": sector_name,
        "data_role": "JOB_DEMAND_SIGNAL",
    },
    reference_date=today,  # 수집 당일
)
```

---

### (14) HRD-Net 훈련과정 Collector

**파일:** `collectors/people/hrdnet/hrdnet_training_collector.py`  
**테이블:** `raw_people_data`  
**source_type:** `PEOPLE_HRDNET_TRAINING`  
**스케줄:** 월간 (monthly — 매월 1일)  
**API 키:** `HRDNET_API_KEY` (고용24/HRD-Net OpenAPI, 무료)

#### API 엔드포인트

```
GET https://www.hrd.go.kr/hrdp/co/pcoao/PCOAO0100P.do
```

> ⚠️ HRD-Net API는 공공데이터포털(data.go.kr)에서도 동일 데이터를 제공한다.  
> `https://api.odcloud.kr/api/15070807/v1/uddi:...` 형태로 접근 가능하므로  
> 발급된 키 형식에 따라 엔드포인트를 결정할 것.

#### 수집 목표

훈련직종별 **현재 개설 과정 수** + **훈련비 규모**  
→ "어떤 직종에 국가 훈련비가 많이 투입되는가" = 노동시장 수요 선행 지표

#### 직종 코드 — NCS 중분류 기준

```python
_NCS_TRAINING_SECTORS: list[tuple[str, str]] = [
    ("ICT_SW",          "20"),  # 정보통신 소프트웨어
    ("ICT_HW",          "21"),  # 정보통신 하드웨어
    ("MANUFACTURING",   "15"),  # 기계
    ("FOOD",            "07"),  # 식품가공
    ("BEAUTY",          "12"),  # 이용·미용
    ("SOCIAL_WELFARE",  "23"),  # 사회복지·종교
    ("EDUCATION",       "24"),  # 교육
    ("CONSTRUCTION",    "04"),  # 건설
    ("HEALTH",          "08"),  # 보건·의료
    ("DESIGN",          "02"),  # 디자인
    ("CULTURE_ARTS",    "01"),  # 문화·예술·디자인·방송
    ("LOGISTICS",       "22"),  # 물류·유통
]
```

#### PeopleCollectDto 매핑

```python
PeopleCollectDto(
    source_type="PEOPLE_HRDNET_TRAINING",
    source_url=f"https://www.hrd.go.kr/hrdp/co/pcoao/PCOAO0100P.do?ncsOccupCd={ncs_code}",
    keyword_or_job=sector_name[:100],
    search_volume_or_count=course_count,  # 개설 과정 수
    raw_metadata={
        "ncs_code": ncs_code,
        "sector_name": sector_name,
        "total_training_cost": total_cost,  # 훈련비 합계 (원)
        "trainee_capacity": trainee_cap,    # 훈련 정원 합계
        "data_role": "TRAINING_DEMAND_SIGNAL",
    },
    reference_date=today,
)
```

---

## 4. P1 컬렉터 — 개요만 기술 (상세 구현 다음 태스크)

### (12) KOCCA 콘텐츠 산업 통계 Collector

**파일:** `collectors/innovation/kocca/kocca_content_collector.py`  
**테이블:** `raw_innovation_data`  
**source_type:** `INNOVATION_KOCCA_CONTENT`  
**스케줄:** 월간  
**API:** `data.go.kr` — 서비스ID `15086820` (콘텐츠산업통계조사)  
**API 키:** `data.go.kr` ServiceKey (공공데이터포털 가입 후 발급)

수집 목표: 게임, 음악, 웹툰/만화, 방송, 영화, 캐릭터 등 6개 콘텐츠 분야별 매출액·수출액·종사자 수.  
선행 지표로서 K-콘텐츠 성장 궤도 추적 가능.

### 사람인 Open API (P1)

**파일:** `collectors/people/saramin/saramin_jobs_collector.py`  
**테이블:** `raw_people_data`  
**source_type:** `PEOPLE_SARAMIN_JOB`  
**스케줄:** 주간  
**API:** `https://oapi.saramin.co.kr/job-search`  
**API 키:** `SARAMIN_ACCESS_KEY` (사람인 OpenAPI 신청)

수집 목표: IT/비IT 전 직종 채용공고 건수 시계열.

---

## 5. KIPRIS 키워드 다양화 (기존 컬렉터 수정)

파일: `backend/domain/master/hub/services/collectors/economic/kipris/kipris_patent_collector.py`

현재 `_TECH_KEYWORD_GROUPS`에 아래 3개 그룹을 **추가**한다 (기존 6개 유지, 총 9개):

```python
# 기존 6개 그룹 유지...
("CONTENT_MEDIA",   ["웹툰", "OTT", "메타버스", "실감콘텐츠"]),
("FOODTECH",        ["스마트팜", "대체단백질", "식품기술", "배양육"]),
("EDUTECH",         ["에듀테크", "VR학습", "AI교육", "학습분석"]),
```

> ⚠️ 주의: KIPRIS API 한도 = 월 1,000건.  
> 키워드 총합 최대 40개 × 주 1회 = ~160건/월 → 한도 내 여유 있음.

---

## 6. 라우터 엔드포인트 추가 (15번)

파일: `backend/api/v1/master/master_routor.py`

아래 4개 엔드포인트를 기존 패턴(`POST /bronze/economic/...`)과 동일하게 추가:

```python
# Innovation
POST /bronze/innovation/arxiv        # arXiv 논문 수집 (선택: ?days_back=7)
POST /bronze/innovation/github       # GitHub Trending 수집 (선택: ?days_back=7)

# People
POST /bronze/people/worknet-jobs     # 워크넷 직업정보 수집
POST /bronze/people/hrdnet-training  # HRD-Net 훈련과정 수집
```

각 엔드포인트:
- `BronzeInnovationIngestService` / `BronzePeopleIngestService` 인스턴스화
- API 키 없으면 `settings`에서 꺼내 `ValueError` → HTTP 400 반환
- 기타 오류 → HTTP 502 반환
- 성공 → 수집 결과 dict 그대로 반환

의존성 주입은 기존 `get_db` 패턴 그대로 사용.

---

## 7. 스케줄러 잡 추가 (16번)

파일: `backend/core/scheduler.py`

### 추가할 잡 함수

```python
async def _job_arxiv_papers() -> dict[str, Any] | None:
    async with AsyncSessionLocal() as session:
        svc = BronzeInnovationIngestService(session)
        return await svc.ingest_arxiv(max_results=50)

async def _job_github_trending() -> dict[str, Any] | None:
    settings = get_settings()
    token = getattr(settings, "github_token", None)  # 없어도 동작
    async with AsyncSessionLocal() as session:
        svc = BronzeInnovationIngestService(session, github_token=token)
        return await svc.ingest_github_trending(days_back=7)

async def _job_worknet_jobs() -> dict[str, Any] | None:
    settings = get_settings()
    key = getattr(settings, "worknet_api_key", None)
    if not key:
        logger.warning("[scheduler] worknet_api_key 없음 — 워크넷 잡 스킵")
        return None
    async with AsyncSessionLocal() as session:
        svc = BronzePeopleIngestService(session, worknet_api_key=key)
        return await svc.ingest_worknet_job_info()

async def _job_hrdnet_training() -> dict[str, Any] | None:
    settings = get_settings()
    key = getattr(settings, "hrdnet_api_key", None)
    if not key:
        logger.warning("[scheduler] hrdnet_api_key 없음 — HRD-Net 잡 스킵")
        return None
    async with AsyncSessionLocal() as session:
        svc = BronzePeopleIngestService(session, hrdnet_api_key=key)
        return await svc.ingest_hrdnet_training()
```

### 스케줄 배치

```python
# _WEEKLY_JOBS에 추가
("arxiv_papers",     _job_arxiv_papers),
("github_trending",  _job_github_trending),

# _MONTHLY_JOBS (새 그룹 추가 필요)
# APScheduler CronTrigger(day=1, hour=9, timezone=KST)
("worknet_jobs",     _job_worknet_jobs),
("hrdnet_training",  _job_hrdnet_training),
```

> `_MONTHLY_JOBS` 그룹이 없으면 신규 추가한다.  
> `_WEEKLY_JOBS`와 동일한 패턴으로 `CronTrigger(day=1, hour=daily_hh, ...)` 사용.

---

## 8. 환경변수 추가

파일: `backend/core/config/settings.py`  
아래 필드를 `Settings` 클래스에 추가 (기존 필드 형식 그대로):

```python
github_token: str | None = Field(default=None, validation_alias="GITHUB_TOKEN")
worknet_api_key: str | None = Field(default=None, validation_alias="WORKNET_API_KEY")
hrdnet_api_key: str | None = Field(default=None, validation_alias="HRDNET_API_KEY")
saramin_access_key: str | None = Field(default=None, validation_alias="SARAMIN_ACCESS_KEY")  # P1
```

`.env.example`에도 항목 추가:
```
GITHUB_TOKEN=                  # GitHub Personal Access Token (optional, rate limit 향상)
WORKNET_API_KEY=               # 고용24 OpenAPI 키 (https://openapi.work.go.kr/)
HRDNET_API_KEY=                # HRD-Net OpenAPI 키 (data.go.kr)
SARAMIN_ACCESS_KEY=            # 사람인 OpenAPI Access Key (P1)
```

---

## 9. API 키 발급 가이드

| 키 | 발급처 | 비용 | 비고 |
|---|--------|------|------|
| `WORKNET_API_KEY` | https://openapi.work.go.kr | 무료 | 고용24 회원가입 후 API 신청 |
| `HRDNET_API_KEY` | https://www.data.go.kr | 무료 | 공공데이터포털 — "HRD-Net 훈련과정" 검색 후 활용신청 |
| `GITHUB_TOKEN` | https://github.com/settings/tokens | 무료 | Personal Access Token, `public_repo` scope만 필요 |
| `SARAMIN_ACCESS_KEY` | https://oapi.saramin.co.kr | 무료 | 사람인 OpenAPI 회원 신청 (P1) |
| `arXiv` | 없음 | 무료 | API 키 불필요 |

---

## 10. 구현 우선순위 체크리스트

### Phase 1 — 인프라 (먼저 완료 필요)

- [ ] ORM 모델: `raw_innovation_data.py`
- [ ] ORM 모델: `raw_people_data.py`
- [ ] DTO: `innovation_collect_dto.py`
- [ ] DTO: `people_collect_dto.py`
- [ ] Repository: `innovation_repository.py`
- [ ] Repository: `people_repository.py`
- [ ] Alembic 마이그레이션 생성 + 검토
- [ ] `alembic upgrade head`

### Phase 2 — P0 컬렉터

- [ ] `arxiv_papers_collector.py` — arXiv 11개 카테고리, 주간
- [ ] `github_trending_collector.py` — 10개 토픽, 주간
- [ ] `worknet_job_info_collector.py` — 13개 직종, 월간
- [ ] `hrdnet_training_collector.py` — 12개 NCS 직종, 월간
- [ ] `BronzeInnovationIngestService`
- [ ] `BronzePeopleIngestService`

### Phase 3 — 라우터 + 스케줄러

- [ ] 라우터 4개 엔드포인트 추가
- [ ] 스케줄러 잡 4개 추가 (weekly 2 + monthly 2)
- [ ] 환경변수 추가 (`settings.py` + `.env.example`)

### Phase 4 — KIPRIS 다양화 (기존 파일 수정)

- [ ] `_TECH_KEYWORD_GROUPS`에 `CONTENT_MEDIA`, `FOODTECH`, `EDUTECH` 그룹 추가

### Phase 5 — P1 (다음 태스크)

- [ ] `kocca_content_collector.py`
- [ ] `saramin_jobs_collector.py`
- [ ] 워크넷 직업 상세 정보 (연봉·전망 지표) 수집

---

## 11. 구현 패턴 주의사항

1. **멱등성 우선**: 모든 컬렉터는 동일 조건으로 2번 실행해도 중복 적재 없어야 함.  
   `source_url` (또는 다중 컬럼 UNIQUE)로 `ON CONFLICT DO NOTHING` 처리.

2. **워터마크 패턴**: `last_week_start: str | None` (YYYYMMDD) — KIPRIS/DataLab 패턴 그대로.  
   Service에서 `_latest_{source}_watermark()` 메서드로 DB 조회 후 Collector에 전달.

3. **Rate limit**: arXiv 1초, GitHub Search 2초 간격. aiohttp `ClientTimeout(total=15)` 설정.

4. **에러 격리**: 카테고리/토픽 단위로 try/except — 1개 실패가 전체를 막지 않도록.

5. **`abstract_text` 크기**: arXiv 초록은 최대 2,000자로 truncate. DB 컬럼은 TEXT이지만 너무 긴 초록은 불필요.

6. **__all__**: 각 컬렉터 파일 하단에 `__all__` 선언 (기존 컬렉터 패턴 동일).

7. **월간 잡 추가 시**: `_MONTHLY_JOBS` 그룹을 `_WEEKLY_JOBS`와 동일 구조로 추가.  
   `CronTrigger(day=1, hour=..., minute=..., timezone=...)` 사용.

8. **__init__.py**: 새 패키지 디렉토리마다 빈 `__init__.py` 생성.

---

## 12. 완료 후 커버리지 예상

| 섹터 | 기존 | 구현 후 |
|------|------|---------|
| AI/ML·소프트웨어 | 🟢 | 🟢 (arXiv cs.AI, GitHub AI 토픽 추가) |
| 콘텐츠/크리에이터 | 🔴 | 🟡 (arXiv cs.SI, GitHub creator-tool, KIPRIS 웹툰) |
| 교육/에듀테크 | 🔴 | 🟡 (HRD-Net 교육직종, KIPRIS 에듀테크, arXiv) |
| 식품/농업 | 🔴 | 🟡 (HRD-Net 식품직종, KIPRIS 스마트팜·대체단백질) |
| 사회서비스/복지 | 🔴 | 🟡 (WorkNet 복지직종, HRD-Net 사회복지) |
| 바이오/헬스케어 | 🟡 | 🟢 (arXiv q-bio, GitHub healthtech 추가) |
| 에너지/기후 | 🟡 | 🟢 (arXiv physics.ao-ph, GitHub climate 추가) |
| 물류/유통 | 🔴 | 🟡 (WorkNet 유통직종, HRD-Net 물류) |
| 패션/뷰티 | 🔴 | 🟡 (WorkNet 미용직종, HRD-Net 미용) |
