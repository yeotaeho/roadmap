# KIAT 수요기술 → Gap youth_fit 변별 개선 + Gold 사영 단일화 (Phase 2 Refinement)

- **작성일** 2026-06-27
- **상태** 설계 승인, 구현 대기
- **범위** Phase 2(`2026-06-27-kiat-gap-tech-demand-phase2-design.md`) 후속 — youth_fit 점수가 변별을 못 하는 문제를 프롬프트로 고치고, 이를 위해 필요한 PROMPT_VERSION bump 가 공유 Gold 사영을 깨뜨리지 않도록 사영을 단일 잡으로 분리한다.

---

## 1. 배경 / 문제

Phase 2 로 `TechDemandGapService` 가 KIAT/KISTEP 수요기술을 LLM 추출하며 `youth_fit`(청년 개인 진입 가능도 0~1)을 매기고, `project_to_gold` 가 `tech_demand_youth_fit_min`(기본 0.5) 미만을 Gold 에서 배제하도록 설계됐다. 그러나 소규모 백필(45건) 후 분포가 퇴화했다 — min 0.6 / max 0.7 / avg 0.696, 0.6 미만 0건.

KIAT 산업기술 수요에는 설비·소재·공정 등 청년 무관 B2B 가 상당수일 텐데 저점수가 전무하다. 원인은 `_TECH_DEMAND_GAP_SYSTEM_PROMPT`(`backend/core/llm/client.py`)가 youth_fit 의 *개념*만 서술하고 *보정 앵커*가 없어, LLM 이 근거 없이 "안전한 중간값(0.6~0.7)"에 앵커링하기 때문이다. 결과적으로 youth_fit 게이트가 사실상 무력하다.

프롬프트 의미가 바뀌므로 `tech_demand` 의 `PROMPT_VERSION` 을 bump 해 기존 추출을 무효화·재추출해야 한다. 그런데 현재 discourse gap 과 tech_demand gap 이 `"v1"` 을 공유하고, 공유 `project_to_gold` 가 단일 pv 필터로 두 소스를 함께 재조립한다. pv 만 다르게 두면 마지막 사영 잡이 다른 소스의 Gold 를 삭제한다(아래 §2). 따라서 사영 재설계가 선행돼야 한다.

## 2. pv bump 가 사영을 깨뜨리는 메커니즘

`project_to_gold(pv, fit_min)` 는 `DELETE FROM gap_issues`(CASCADE) 후 `WHERE g.prompt_version = :pv` 로 재조립한다. 두 소스가 `"v1"` 이라 현재는 안전하다. tech_demand 를 `"v2"` 로 올리면:

- `gap_refine` 의 사영(`v1`) — Gold 를 discourse(v1) + **구 tech_demand(v1, 폐기 대상)** 로 재조립. 낡은 추출이 되살아난다.
- `tech_demand` 의 사영(`v2`) — Gold 를 비우고 **신 tech_demand(v2)만**으로 재조립. **discourse 가 Gold 에서 사라진다.**

마지막 실행 잡이 이기고, 어느 쪽도 완전한 Gold 를 만들지 못한다.

## 3. 목표 / 비목표

**목표**
- youth_fit 점수가 실제로 분산되게 프롬프트를 보정(앵커 루브릭 + 저·중·고 few-shot)한다.
- `tech_demand` `PROMPT_VERSION` 을 `"v2"` 로 bump 한다.
- Gold 사영을 단일 잡으로 분리해 discourse(v1) + innovation(v2)를 한 번에 일관 재조립한다.
- discourse gap 경로·기존 트리거·테스트에 회귀를 만들지 않는다.

**비목표**
- DB 스키마 변경(`youth_fit_score` 컬럼은 Phase 2 에서 이미 추가됨 — 마이그레이션 없음).
- youth_fit 임계 자동 최적화(수동 캘리브레이션).
- generic 소스 레지스트리 추상화(소스 2개라 명시적 2-소스 SQL 로 충분 · YAGNI).
- Gap 탭 프론트엔드 변경.

## 4. 설계

### 4.1 사영 분리 — `GapProjectionService` 신설 (단일 잡)

사용자 결정: 사영을 단일 잡으로 통합.

- **`GapRefineService` / `TechDemandGapService`** — `project_to_gold` 호출 제거. Silver 적재 루프 + 마지막 잔여분 flush commit 만 유지하고 `{scanned, gaps, skipped}` 반환(`issues` 키 제거).
- **신규 `GapProjectionService`**(`hub/services/gap_projection_service.py`) — 소스→현재 pv 매핑을 단일 소유. drift 방지를 위해 각 서비스의 `PROMPT_VERSION` 을 import:

  ```python
  from domain.market_insight.hub.services.gap_refine_service import PROMPT_VERSION as DISCOURSE_PV
  from domain.market_insight.hub.services.tech_demand_gap_service import PROMPT_VERSION as TECH_DEMAND_PV
  ```

  `project_and_serve()` → `repo.project_to_gold(DISCOURSE_PV, TECH_DEMAND_PV, fit_min)` 한 번 호출 후 commit, `{"issues": n}` 반환. `fit_min` 은 `settings.tech_demand_youth_fit_min`.
- 순환 import 없음 — 두 refine 서비스는 projection 을 import 하지 않는다.

### 4.2 `project_to_gold` 시그니처·SQL 변경 (`gap_repository.py`)

- 시그니처: `project_to_gold(disc_pv: str, td_pv: str, fit_min: float = 0.0) -> int`.
- `_FETCH_SILVER_FOR_GOLD` 의 `WHERE g.prompt_version = :pv` 를 소스별 pv 매칭으로 교체:

  ```sql
  WHERE g.extracted_problem IS NOT NULL
    AND ( (g.raw_table_ref = 'raw_discourse_data'  AND g.prompt_version = :disc_pv)
       OR (g.raw_table_ref = 'raw_innovation_data' AND g.prompt_version = :td_pv) )
    AND (g.raw_table_ref <> 'raw_innovation_data' OR g.youth_fit_score >= :fit_min)
  ```

  discourse@v1 + innovation@v2 만 Gold 통과. 구 tech_demand v1 Silver 는 리니지로 남되 Gold 에서 자동 배제(억지 삭제 불필요). evidence COALESCE·youth_fit 게이트·evidence_type 도출은 기존 그대로.

### 4.3 프롬프트 보정 (`_TECH_DEMAND_GAP_SYSTEM_PROMPT`, `core/llm/client.py`)

youth_fit 서술부에 **앵커 루브릭 + 저·중·고 few-shot** 주입.

- 루브릭(점수 대역 앵커):
  - `0.1~0.3` — 대규모 설비·소재·공정·자본집약·라이선스 장벽 큰 B2B 기술(개인 진입 불가).
  - `0.4~0.6` — 전문성·자본이 일부 필요하나 개인이 협업·소규모로 진입할 여지가 있는 기술.
  - `0.8~0.9` — 개인이 학습·포트폴리오로 진입 가능한 SW·디자인·데이터·서비스 기술.
- few-shot 3개(전 범위 시범) — 저(예: 반도체 식각 장비 국산화 → 0.2) · 중(예: 산업용 IoT 센서 SW 통합 → 0.5) · 고(예: 생성형 AI 응용 서비스 개발 → 0.85).
- 출력 JSON 형식은 불변(`{problem, opportunity, detail, stakeholders, next_actions, youth_fit}`). 파서(`_parse_tech_demand_gap`)·`extract_tech_demand_gap` 무변경.

### 4.4 PROMPT_VERSION bump

`tech_demand_gap_service.py` `PROMPT_VERSION = "v1"` → `"v2"`. 상단 "변경 금지" 주석을 새 사영 구조(소스별 pv)를 반영하도록 갱신. `fetch_unprocessed_tech_demand` 가 pv=`"v2"` 로 미처리분을 조회하므로 전량 자연 재추출(v2 행 없음). discourse `PROMPT_VERSION` 은 `"v1"` 유지.

### 4.5 호출부 갱신 (회귀 방지)

- **스케줄러**(`core/scheduler.py`) — `_job_gap_refine`·`_job_tech_demand_gap` 의 사영 의존 제거(서비스가 더 이상 사영 안 함). 신규 `_job_gap_project`(키 가드 동일) 추가, `_REFINE_PIPELINE` 에 `gap_refine` → `tech_demand_gap` → **`gap_project`** 순으로 등록. refine 잡이 스킵돼도 사영은 기존 Silver 로 멱등 재생성.
- **HTTP 트리거**(`api/v1/insight/insight_routor.py:205` `/gap/refine`) — refine 후 `GapProjectionService.project_and_serve()` 를 이어 호출해 Gold 재생성 유지, 결과 병합 반환. 임계 재튜닝(Gold 재사영만) 지원을 위해 소형 `POST /gap/project` 엔드포인트 추가(`require_internal_token`, projection 만 실행).
- **백필**(`scripts/tech_demand_gap_backfill.py`) — `refine_and_serve()` 후 `GapProjectionService.project_and_serve()` 호출, 결합 결과·youth_fit 분포 안내 출력.

### 4.6 테스트 갱신

- `scripts/gap_chunk_test.py` — `_FakeRepo.project_to_gold` 미호출 전제로 `project_to_gold 1회` 단언을 `0회`(`gold_calls == 0`)로 변경. trailing commit 유지 시 commit 카운트(`>= 3`, `>= 1`)는 불변.
- 신규 `scripts/gap_projection_test.py`(무네트워크) — `GapProjectionService` 가 `repo.project_to_gold` 를 두 pv(disc=v1, td=v2)·fit_min 으로 정확히 1회 호출하고 commit 함을 stub 으로 검증.

## 5. 데이터 흐름

```
raw_discourse_data ─ refined_text_sector_class ─┐
                                                 ├─ GapRefineService        → refined_gap_insights (pv=v1)   ┐
raw_innovation_data ─ refined_text_sector_class ─┘                                                            │ Silver only
   (KIAT/KISTEP)                                  └─ TechDemandGapService    → refined_gap_insights (pv=v2,   ┘ (사영 X)
                                                       (앵커 루브릭 프롬프트)     youth_fit_score)
                                                              ↓
                                          GapProjectionService.project_and_serve()  (단일 잡, 마지막 실행)
                                          repo.project_to_gold(v1, v2, fit_min)
                                          discourse@v1 + innovation@v2(youth_fit ≥ fit_min)
                                                              ↓
                                          gap_issues / issue_evidences  (Gap 탭 통합)
```

## 6. 변경 파일

| 파일 | 변경 |
|---|---|
| `core/llm/client.py` | `_TECH_DEMAND_GAP_SYSTEM_PROMPT` 에 앵커 루브릭 + 저·중·고 few-shot 주입 |
| `hub/services/tech_demand_gap_service.py` | `project_to_gold` 호출 제거(Silver only) · `PROMPT_VERSION "v2"` · 주석 갱신 |
| `hub/services/gap_refine_service.py` | `project_to_gold` 호출 제거(Silver only) · trailing commit 유지 · `issues` 키 제거 |
| `hub/services/gap_projection_service.py` | **신규** — 소스별 pv 매핑 단일 소유, 단일 사영 |
| `hub/repositories/gap_repository.py` | `project_to_gold(disc_pv, td_pv, fit_min)` · `_FETCH_SILVER_FOR_GOLD` 소스별 pv 매칭 |
| `core/scheduler.py` | `_job_gap_project` 신설 · `_REFINE_PIPELINE` 에 `gap_project` 등록 |
| `api/v1/insight/insight_routor.py` | `/gap/refine` 에 projection 이어 호출 · `POST /gap/project` 추가 |
| `scripts/tech_demand_gap_backfill.py` | refine 후 projection 호출 · 분포 출력 |
| `scripts/gap_chunk_test.py` | `project_to_gold` 미호출 전제로 단언 갱신 |
| `scripts/gap_projection_test.py` | **신규** — projection 단위 테스트 |

## 7. 검증 (task ③ 포함)

- **단위** — `gap_chunk_test.py`(refine 사영 미호출) · `gap_projection_test.py`(두 pv·fit_min 1회 사영) · `tech_demand_gap_parse_test.py`(파서 무변경) 통과.
- **소규모 재추출** — `tech_demand_gap_backfill.py` 로 v2 재추출(45건 규모) 후 youth_fit 분포 재확인. 0.5 미만이 실제로 생겨 게이트가 일부를 거르는지 확인:
  ```sql
  SELECT min(youth_fit_score), max(youth_fit_score), avg(youth_fit_score),
         count(*) FILTER (WHERE youth_fit_score < 0.5) AS below
  FROM refined_gap_insights WHERE data_role = 'TECH_DEMAND_SIGNAL' AND prompt_version = 'v2';
  ```
- **Gold 통합** — `issue_evidences` 에 `evidence_type` 별 분포 확인, discourse(NEWS) + tech_demand(TECH_DEMAND) 공존.
- **무회귀** — discourse `DISCOURSE_SIGNAL` Gold 반영 불변, `/gap/refine` 응답에 issues 포함.
- **재튜닝** — 분포 보고 필요시 `TECH_DEMAND_YOUTH_FIT_MIN` 만 조정 후 `/gap/project`(또는 백필 projection) 재실행 — LLM 재실행 불필요.

## 8. 리스크 / 완화

- **프롬프트가 여전히 안 갈림** — 재추출 분포가 또 좁으면 few-shot 예시 추가·temperature 재검토. 입력(KIAT title+keyword)이 얇은 경우 abstract 비중 확인.
- **사영 분리 누락 호출부** — `project_to_gold` 호출부를 grep 으로 전수(`gap_refine_service`·`tech_demand_gap_service`만 해당, causal·chance 는 별도 repo 라 무관) 확인 후 이관.
- **구 v1 tech_demand Silver 잔존** — Gold 에서 배제되므로 무해. 정리는 후속(선택).
- **단일 사영 잡 실패 시 Gold 미갱신** — 멱등이라 재실행으로 복구. refine Silver 는 이미 커밋됨.
