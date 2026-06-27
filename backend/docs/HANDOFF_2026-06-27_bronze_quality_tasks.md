# Bronze 데이터 품질 개선 — 작업 인수인계 (2026-06-27)

## 컨텍스트

이 세션에서 market_insight·master 도메인의 Bronze 수집 품질을 진단·개선했다.
도구 호출 형식 오류가 반복되어 새 채팅에서 이어간다. 아래에 완료 작업과 남은 Task를 정리한다.

---

## 완료 작업 (커밋됨)

| 작업 | 커밋 | 검증 |
|---|---|---|
| KIAT → Pulse `tech_demand` 축 연결 (Phase 1) | `9b50796`·`558229e`·`6c0e76d`·`decf080` (main 머지) | pulse_scoring 33·chunk 5·통합 3 PASS, tech_demand 0→8건 |
| content_body 보강 (news_rss `extract_article_body` + 기존 149건 UPDATE 백필) | 코드 머지 + 데이터 백필 | discourse content_body 결측 36.2%→0.2%, 한국경제 100%→0.6% |
| gov_report RSS 수집기 구현·스케줄러 등록 | `1ea91c3` | korea.kr 정책브리핑 RSS, 실 ingest 0→50건 |
| K-Startup 공고 본문 보강 (상세 fetch + `.information_list`) | `d4daee7` | bronze_expansion_parse_test 58 PASS |
| LLM refine 4서비스 + embed 청크 커밋 (idle timeout 방지) | `f98b967`·`fc7efde` | (사용자 직접 구현) |

---

## ⚠️ 미커밋 (워킹트리에 남음 — 첫 작업으로 처리)

### Task A. ArXiv 페이지네이션 커밋 (최우선)

- **상태** — `backend/domain/master/hub/services/collectors/innovation/arxiv/arxiv_papers_collector.py` 수정됐으나 **커밋 안 됨** (`git status` 에서 ` M`).
- **무엇** — `collect()` 에 카테고리별 페이지네이션 추가. `start=0` 1페이지(~40건/카테고리)만 받던 것을, 실제 반환 수만큼 `start` 전진 + `per_category_cap`(기본 300) 상한 + `max_results` 50→100.
- **검증 완료** — cs.AI 단일 카테고리 40건 → 200건 확인. `submittedDate` 쿼리는 정상이며 원인 아니었음(totalResults 840).
- **할 일** — 커밋만:
  ```bash
  git add backend/domain/master/hub/services/collectors/innovation/arxiv/arxiv_papers_collector.py
  git commit -m "fix(master): arXiv 수집기 카테고리별 페이지네이션 추가(수집량 40→200)"
  ```

---

## 남은 Task

### Task B. ArXiv `per_category_cap` 튜닝

- **무엇** — 현재 `per_category_cap=300`, `max_results=100`. cs.AI 는 cap 120에도 200건 수집(페이지 100 단위라 cap 초과). 11개 카테고리 × 300 = 주당 최대 ~3,300건 → Silver LLM 비용·노이즈 부담 검토.
- **어디** — `arxiv_papers_collector.py` `collect()` 기본값, 스케줄러 `_job_arxiv_papers`(`core/scheduler.py`).
- **검증 기준** — 카테고리별 적정 cap(예 100~150) 설정 후 주 1회 수집량이 합리적 범위인지.

### Task C. People `search_volume` 연결 (사람인 키 발급 대기)

- **무엇** — `raw_people_data.search_volume_or_count` 98.8% NULL. WorkNet 은 직업 분류(taxonomy)만, 실제 수요 수치 미수집. 사람인 API 키 **신청 중(미발급)**.
- **할 일** — 키 발급 후 `saramin_recruit_collector` 실수집 연결 → 직무 수요 신호 채움. 키 발급 전까지 보류.
- **어디** — `backend/domain/master/hub/services/collectors/people/saramin/saramin_recruit_collector.py`.

### Task D. KIAT Phase 2 — Gap 기회 신호

- **무엇** — Phase 1 에서 KIAT 를 `refined_text_sector_class` 로 분류·Pulse 연결 완료. Phase 2 는 그 분류를 재사용해 `gap_refine_service` 가 "기업 미확보 기술 → 청년 기회" 추출 + 적합도 필터(B2B 설비기술 등 청년 무관 항목 배제).
- **어디** — `backend/domain/market_insight/hub/services/gap_refine_service.py`. 설계: `backend/docs/specs/2026-06-27-kiat-pulse-tech-demand-design.md` §8.
- **할 일** — 별도 spec 작성 후 구현(brainstorming → writing-plans).

### Task E. gov_report 헤드라인 HTML 엔티티 정리 (미세)

- **무엇** — gov_report `headline` 에 `&middot;`·`&quot;` 등 HTML 엔티티 잔존(본문·부처·수집은 정상). API summary 는 `_html_to_text` 로 풀리나 제목은 raw.
- **어디** — `backend/domain/master/hub/services/collectors/discourse/gov_report/gov_report_collector.py` `parse_gov_rss` — `html.unescape(headline)` 추가 + 테스트.

### Task F. main 직접 커밋 정리 / push

- **무엇** — 이 세션 후반 작업이 `main` 에 직접 커밋됨(gov_report `1ea91c3`, K-Startup `d4daee7`, refine `f98b967`, ArXiv Task A 등). **push 안 됨** (로컬 main 이 origin 보다 앞섬).
- **할 일** — push 또는 브랜치 정리 전략 결정. 원격 반영 시 검토.

### Task G. innovation GitHub/Techblog 수집량 점검 (선택)

- **무엇** — GitHub 282·Techblog 108 건으로 KIAT 대비 적으나 ArXiv/Customs 보다는 양호. 수집 범위·주기 적정성 확인(필수 아님).

---

## 진단 결과 요약 (참고)

- **raw_economic_data** — `investor_name` 84% 차나 의미가 "공시 제출 기업"(투자 주체 아님), `target_company` 90.9% NULL. DART 공시 구조상 한계. Silver `refined_investment_flows` 가 headline 에서 LLM 으로 보완(설계 양호, 단 마이그레이션 `c5f9a3b7d1e2` 적용 확인 필요).
- **raw_innovation_data** — KIAT 96%(11,226), 비-KIAT 소수. ArXiv 29(Task A 로 해결), Customs 26(**정상** — HS 그룹 월간 집계라 본질적 소량).
- **raw_discourse_data** — content_body 해소(0.2%). gov_report 50건 신규.
- **raw_opportunity_data** — K-Startup 보강 완료(`d4daee7`). narajangteo 100% NULL 은 **구조적 정상**(입찰=메타데이터). SMES 양호.
- **raw_people_data** — `search_volume` 98.8% NULL(Task C, 키 대기).
- **verified_company_master** — `business_number`·설립일 100% NULL(익명화 공개셋, 소스 한계).
- **raw_market_timeseries** — 0% NULL(API 기반 모범).

## Silver 정제 입력 매핑 (참고)

- `refined_text_sector_class` ← economic `raw_title`+content_text / discourse `headline`+`content_body` / KIAT `title`+`abstract`+`keyword`
- `refined_gap_insights` ← discourse `headline`+`content_body`
- `refined_chance_insights` ← opportunity `raw_title`+`raw_content`+`raw_metadata`
- `refined_investment_flows` ← economic `raw_title`+`target_company_or_fund`(힌트, LLM 재추출 보완)
- **핵심** — content_body·raw_content 같은 "본문" 결손이 text_classify·gap·chance·causal Silver 입력 품질을 동시에 좌우. 본문 보강이 가장 임팩트 큼(content_body·K-Startup 완료).
