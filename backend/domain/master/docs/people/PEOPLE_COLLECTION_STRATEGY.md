# People 흐름 수집 전략 — 사람·역량(Competency)·수요(Demand)

> Bronze 테이블: `raw_people_data` · 도메인: 진로 추천의 "어떤 역량이 필요하고, 시장이 무엇을 뽑는가"
> 최종 갱신: 2026-06-24

## 1. 목적과 두 축

진로 내비게이션은 **사람의 흐름**을 두 측면으로 본다.

| 축 | 의미 | 신호 성격 |
|---|---|---|
| **Competency(역량)** | 직업 분류·연봉·발전가능성·훈련 과정 | 정적 사전 + 수요 라벨 |
| **Demand(수요)** | 시장이 *지금* 뽑는 직무·키워드별 채용 건수 | 선행 채용 신호 |

`data_role`로 신호를 구분한다: `JOB_TAXONOMY_SIGNAL`(직업분류), `MAJOR_DEMAND_SIGNAL`(학과), `TRAINING_DEMAND_SIGNAL`(훈련), **`DEMAND_HIRING_SIGNAL`(채용 수요 — 이번 신규)**.

## 2. 수집기 현황

| 소스 | 컬렉터 | source_type | 신호 | 키 | 상태 |
|---|---|---|---|---|---|
| 고용24 직업정보 | `people/worknet/worknet_job_info_collector.py` | `PEOPLE_WORKNET_JOB` | 직업 분류 492건 | WORKNET_API_KEY | ✅ |
| 고용24 훈련과정 | `people/hrdnet/hrdnet_training_collector.py` | `PEOPLE_HRDNET_TRAINING` | NCS 직종별 훈련 수요 | HRDNET_API_KEY | ✅ |
| 커리어넷 직업·학과 | `people/careernet/careernet_collector.py` | `PEOPLE_CAREERNET_JOB/MAJOR` | 직업·연봉·발전가능성 | CAREERNET_API_KEY | ✅ |
| **고용24 채용정보** | `people/goyong24/recruit_collector.py` | `PEOPLE_GOYONG24_RECRUIT` | **직종별 채용 건수(Demand)** | GOYONG24_RECRUIT_API_KEY | 🔴 등급제한 |
| **사람인 채용** | `people/saramin/saramin_recruit_collector.py` | `PEOPLE_SARAMIN_RECRUIT` | 키워드별 채용 total(Demand) | SARAMIN_ACCESS_KEY | 🟡 키 대기 |

## 3. Demand 수집 설계 (신규)

### 집계 전략 — UNIQUE 제약과의 정합
`raw_people_data`의 UNIQUE는 `(source_type, keyword_or_job, reference_date)`이다. 개별 채용공고를 그대로 적재하면 같은 직무·날짜가 충돌한다. 따라서 **직종/키워드별 공고 건수로 집계**해 직종당 1행을 적재한다(`search_volume_or_count` = 건수). 이는 "어떤 직무가 지금 뜨는가"를 정량화하는 선행 수요 신호다.

- **고용24 채용**: 최근 공고를 페이지 순회 → 직종명(`jobsNm`)별 건수 집계. worknet 직업정보 컬렉터의 이중 파서(`_find_lists`)를 재사용해 XML/JSON 래퍼 무관 파싱.
- **사람인**: 일 500콜 한도 → 키워드별 `count=1`로 `jobs.total`만 읽어 한도 절약. 요청 간 0.15초 딜레이.

## 4. ⚠️ 실측 함정 (live 검증으로만 드러남)

- **고용24 채용 = 기업회원 전용 (2026-06-24 확인).** 올바른 오퍼레이션은 `callOpenApiSvcInfo210L01.do`(직업정보 212 계열과 달리 채용은 **210 계열**, 처음 추정한 211L01은 "서비스가 존재하지 않습니다"). 단 보유 개인회원 키로는 **`"개인회원은 사용할 수 없는 OPEN-API"`** 에러. → 코드는 정상이며 **기업회원 키 확보 시 즉시 동작**. 개인 경로는 사람인.
- **data.go.kr/3038225(워크넷 채용정보)은 "API 유형: LINK"** = work24 자체 API로 연결되므로 동일한 기업회원 제한. 개인 우회 불가.
- **careernet `prospect`(일자리전망) 필드는 API 미제공** → 항상 빈 값. 대체 신호는 `possibility`(발전가능성)·`salery`(연봉).

## 5. 멱등성·인프라
- Repository `people_repository.py`: `insert_many_skip_duplicates` (ON CONFLICT DO NOTHING). **대량 적재 시 asyncpg 32,767 파라미터 한도 회피용 배치(1000행) 적용** — `BaseRepository._commit_batched_returning` 공통 헬퍼.
- Ingest `bronze_people_ingest_service.py`: 일별 `reference_date` watermark(같은 날 재실행 skip).
- 라우터 `/api/master/bronze/people/{worknet-jobs,hrdnet-training,careernet,goyong24-recruit,saramin-recruit}`.
- 스케줄러: worknet/hrdnet/careernet=월간, goyong24/saramin 채용=일별(Demand는 자주 변함).

## 6. 차기
- 사람인 키 승인 → Demand 축 채움(개인 가능 경로).
- 워크넷 직무데이터사전(SKILL_INFO)·Google Trends(pytrends) 후보.
- Silver에서 직종 키워드 → 섹터 매핑(현재 People→섹터는 HRDNET `sector_name`만 사용).

> 소스 카탈로그(주소·키·함정): [`backend/docs/sources/people_sources.md`](../../../../docs/sources/people_sources.md)
