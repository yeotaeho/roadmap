# People 소스 카탈로그 — raw_people_data (Competency/Demand)

> 사람·역량 흐름. Competency(직업분류·역량) + Demand(채용 수요) 선행 신호.
> 상태: ✅ 구현 / 🟡 골격(키 게이트) / 📄 문서(차기 후보).
> 조사·검증일 2026-06-23.

## 구현·후보 소스

| 소스 | 엔드포인트 | 데이터 | source_type | 키 | 상태 |
|---|---|---|---|---|---|
| 고용24 채용정보 | `https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo210L01.do` · [data.go.kr/3038225](https://www.data.go.kr/data/3038225/openapi.do) | 직종별 실시간 채용공고 → **건수 집계(Demand)** | `PEOPLE_GOYONG24_RECRUIT` | `GOYONG24_RECRUIT_API_KEY` ⚠️**기업회원 전용** | ✅(코드)/🔴(키등급) |
| 사람인 채용 OpenAPI | [oapi.saramin.co.kr/job-search](https://oapi.saramin.co.kr/guide/job-search) | 키워드별 `jobs.total` (Demand) | `PEOPLE_SARAMIN_RECRUIT` | `SARAMIN_ACCESS_KEY` (기존) | 🟡 |
| 고용24 직업정보 | `callOpenApiSvcInfo212L01.do` | 직업 분류 taxonomy | `PEOPLE_WORKNET_JOB` | `WORKNET_API_KEY` | ✅(기존) |
| 고용24 훈련과정 | `callOpenApiSvcInfo310L01.do` | NCS 직종별 훈련 수요 | `PEOPLE_HRDNET_TRAINING` | `HRDNET_API_KEY` | ✅(기존) |
| 커리어넷 직업정보 | career.go.kr openApi | 직업·연봉·발전가능성 | `PEOPLE_CAREERNET_JOB` | `CAREERNET_API_KEY` | ✅(기존) |
| 커리어넷 학과정보 | career.go.kr openApi `svcCode=MAJOR` | 학과→직업 매칭 | `PEOPLE_CAREERNET_MAJOR` | `CAREERNET_API_KEY` | 📄 |
| 워크넷 직무데이터사전 | [data.go.kr/15088880](https://www.data.go.kr/data/15088880/openapi.do) | 요구 스킬셋(SKILL_INFO) | — | `WORKNET_API_KEY` | 📄 |
| Google Trends (KR) | pytrends(비공식) | 직무 검색 관심도 | — | 불필요 | 📄 |

## 구현 메모 / 함정

- **고용24 채용정보 (2026-06-23 live 확인)**: 올바른 오퍼레이션은 **`210L01`**(직업정보는 212, 채용정보는 210 계열 — 처음 추정한 `211L01`은 "서비스가 존재하지 않습니다" 에러). `210L01`로 호출 시 **`"개인회원은 사용할 수 없는 OPEN-API입니다"`** → 현재 보유 `GOYONG24_RECRUIT_API_KEY`는 **개인회원** 등급이라 채용정보 접근 불가. **해결: ① work24를 기업회원으로 재가입 후 키 재발급, 또는 ② data.go.kr 워크넷 채용정보(3038225) serviceKey 발급(개인 가능), 또는 ③ 사람인.** 코드(파서·집계)는 정상이라 기업회원 키만 넣으면 동작.
- **Demand 집계 전략**: 개별 공고를 그대로 적재하면 `(source_type, keyword_or_job, reference_date)` UNIQUE와 충돌 → **직종(`jobsNm`)별 공고 건수**로 집계해 직종당 1행. `raw_metadata.data_role = "DEMAND_HIRING_SIGNAL"`, `scanned_total` 동봉.
- **사람인**: 일 500콜 한도 → 키워드별 `count=1`로 `jobs.total`만 읽어 한도 절약. 요청 간 0.15초 딜레이.
- **수집기**: `collectors/people/goyong24/recruit_collector.py`, `collectors/people/saramin/saramin_recruit_collector.py`.
