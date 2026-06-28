# 미달 7개 섹터 활성화 전략 — Pulse 신호 밀도 확충

> 도메인: market_insight · 대상: Pulse 탭(12 섹터 트렌드 점수)
> 관련: [SILVER_PULSE_STRATEGY.md](SILVER_PULSE_STRATEGY.md) §8(차기) 의 "매핑 확장·시장축" 구체 실행안
> 작성: 2026-06-28 · 상태: 전략 확정(구현 대기)

## 1. 배경 / 문제

Pulse 탭 12 섹터 중 **AI·반도체·바이오·에너지·식품 5개만 정상 작동**하고, **핀테크·모빌리티·콘텐츠·에듀테크·물류·사회서비스·뷰티패션 7개는 "데이터 수집 중"(회색)** 으로 막혀 있다. 청년 사용자에게 절반 이상이 빈칸이면 탐색 가치와 신뢰도가 떨어진다. 본 전략은 7개 섹터를 **단계적으로(균형)** 활성화하되, 가짜 활성화(노이즈)를 만들지 않고 진짜 신호 밀도를 끌어올리는 것을 목표로 한다.

## 2. 진단 — "데이터 없음"이 아니라 "조밀한 소스가 분류 경로로 안 들어감"

### 2.1 활성/비활성을 가르는 메커니즘
"데이터 수집 중"은 별도 상태 컬럼이 아니라 **파생 플래그**다.
- [pulse_pipeline.py](../hub/services/pulse_pipeline.py) `compute_silver` — 롤링 20일 윈도우 안에 **비영(非零) 신호 < `min_history`(운영 5)** 면 score를 50(중립)으로 강제한다.
- [pulse_overview.py](../hub/services/pulse_overview.py) `_heatmap` — 히트맵 비-null 셀이 전부 50이면 `data_status="insufficient"` → UI "데이터 수집 중".
- 이 게이트는 희소 섹터의 **거짓 급등(태풍급) 노이즈를 막으려 의도적으로** 넣은 안전장치다. 그냥 낮추면 노이즈가 되살아난다.

### 2.2 Pulse 축은 두 종류 — 7섹터는 '정적 매핑 축'에서만 탈락한다
[pulse_repository.py](../hub/repositories/pulse_repository.py) `fetch_axis_signals` 기준.

| 종류 | 축 | 매핑 방식 | 7섹터가 막히는 이유 |
|---|---|---|---|
| **정적 매핑** | innovation·economic·people·market | `sector_source_map`·`_SECTOR_CODE_MAP`·`_MARKET_SOURCE_MAP` — 소스가 **고정 분류코드/티커를 방출해야** 섹터에 꽂힘 | 서비스/디지털 섹터는 깨끗한 HS코드·ArXiv 카테고리·ETF 티커가 없어 탈락 |
| **LLM 분류 텍스트** | economic_text·discourse·**tech_demand** | [text_sector_classify_service.py](../hub/services/text_sector_classify_service.py) 가 자유 텍스트를 **12 섹터 어디로든** 분류(`refined_text_sector_class`) | **정적 분류표가 필요 없음 → 7섹터의 구조적 해법은 이 경로다** |

즉 잘 되는 5개 섹터는 하드웨어·과학이라 정적 분류표(HS코드·ArXiv·ETF)에 깔끔히 매핑되고, 7개는 그 분류표가 없어 막힌다. 해법은 **(a) 조밀한 소스를 LLM 텍스트 축으로 흘려보내거나, (b) 그 섹터에 유효한 시장 티커를 정적 맵에 추가**하는 것이다.

### 2.3 이미 한 일 / 안 한 일 (중요 — 중복 작업 방지)
- ✅ **KIAT `tech_demand` 축은 이미 구현·가동 중**(2026-06-27, 커밋 `9b50796`·`558229e`·`6c0e76d`). `raw_innovation_data` 의 KIAT 11,226건(innovation Bronze의 96%, 과거 dead data)을 LLM 분류해 `tech_demand` 축(weight 0.5)으로 소비한다. `_TARGET_TABLES`·`_FETCH_UNCLASSIFIED_INNOVATION`·`_TEXT_SECTOR_AXIS_SQL` UNION 모두 현행 코드 존재. **남은 것은 구현이 아니라 전체 백필 완료·가중치 튜닝.**
- ✅ economic_text·discourse 텍스트 축도 가동 중(naver 경제뉴스·뉴스 RSS LLM 분류).
- ❌ **시장축은 16티커 전부 5개 작동 섹터 전용**([_MARKET_SOURCE_MAP](../hub/repositories/pulse_repository.py)). 7섹터에는 티커가 0개 → 가장 조밀한(일별) 축이 통째로 비어 있다.
- ❌ 7섹터를 직접 겨냥한 조밀한 뉴스 RSS·도메인 공개 API 미연결.

## 3. 전략 — 균형(단계적) 4-Phase

### Phase 0 — 계측 (먼저 측정한다)
어느 섹터가 어느 축에서 게이트(5/20일)에 얼마나 못 미치는지 수치로 확인해야 투자 우선순위가 선다.
- 기존 [bronze_null_audit.py](../../../../scripts/bronze_null_audit.py) 패턴을 확장한 **섹터×축 20일 신호밀도 진단 스크립트**: 각 섹터별 최근 윈도우의 축별 비영 신호 건수와 "게이트까지 남은 거리"를 출력.
- KIAT 백필이 7섹터에 실제로 얼마나 도달했는지(`refined_text_sector_class` 의 `raw_innovation_data` 섹터 분포)도 함께 측정.
- 산출물: 7섹터 각각의 최저비용 활성화 축. 이후 Phase의 ROI 근거.

### Phase 1 — 시장축 티커 확장 + KIAT 백필 마무리 (코드/설정만, 외부 신규 의존 없음)
- **시장축 티커 추가(최고 레버리지).** [yahoo_finance_collector](../../../master/hub/services/collectors/economic/yahoo) 는 `yfinance` 기반이라 **티커 문자열 한 줄 + `_MARKET_SOURCE_MAP` 시드 한 줄**로 매일 갱신되는 신호가 생긴다. **검증 결과 7개 중 6개 섹터에 유효한 일별 티커가 존재**(§4) → 거의 0비용으로 수일 내 게이트 통과.
- **KIAT `tech_demand` 백필 완료·튜닝.** 전체 11,226건 분류 완료 여부 확인(daily 잡 점진 처리), 7섹터 도달 분포 확인, weight 0.5 실데이터 튜닝.
- ⚠️ 시장축 주의 — ETF는 글로벌/미국 상장분이 다수라 '한국 선행지표'로 해석한다. 개별주는 기업 특이 리스크가 커 `_MARKET_AXIS_SQL` 의 거래대금(turnover) 상대유량 신호로 다루고 개별주 threshold를 적용한다(기존 통화중립 패턴 준수).

### Phase 2 — 조밀한 신규 Bronze 소스 (신규 수집기 → 텍스트 축 자동 합류)
정적 코드가 없어도 LLM 텍스트 축이 받아주므로, 조밀하게 갱신되는 한국어 텍스트·통계 소스를 새로 붙인다.
- **토픽별 한국어 뉴스 RSS** — 기존 [news_rss_collector](../../../master/hub/services/collectors/discourse/news_rss) 에 금융·모빌리티·문화연예·유통·복지 피드 추가. discourse 축은 이미 12섹터 LLM 분류라 추가 매핑 불필요.
- **도메인 공개 API** — 일별/주별 갱신 공공 OpenAPI를 신규 수집기로(예: KOBIS 박스오피스=일별→콘텐츠). 적절한 raw 테이블(`raw_discourse_data`/`raw_economic_data`)로 적재 → 기존 LLM 분류 → 텍스트 축 자동 합류.

### Phase 3 — UX 정직성 + 게이트 보정 + 사회서비스 전용 트랙 (증거 기반·최후)
- **정직한 UX** — 여전히 희소한 섹터는 "데이터 수집 중"을 솔직히 노출하되 부분 신호(예: 채용 수요만)는 보여줘 빈칸감을 줄인다.
- **사회서비스 전용** — 깨끗한 시장 티커가 없는 구조적 예외(§4). discourse RSS·지원사업(opportunity) API 중심으로 가장 느린 트랙. 프록시 ETF(AGNG)는 신중 적용.
- **게이트 보정은 증거가 있을 때만** — `min_history=5/20일` 은 노이즈 방지 장치다. Phase 0 계측·Phase 1~2 투입 후에도 "진짜 신호가 있는데 게이트에 걸린다"가 입증된 섹터에 한해 per-축/per-섹터 캘리브레이션 검토. 함부로 낮춰 가짜 활성화를 만들지 않는다.

## 4. 소스 카탈로그 (웹조사·적대적 검증)

> 웹조사 워크플로(7섹터 + 3 교차 스윕 → 140 후보 → 전수 적대적 검증). recommend 78·maybe 34. 실재·접근성·갱신밀도가 검증된 핵심만 등재.

**🔑 헤드라인 — 7개 중 6개 섹터(사회서비스 제외)에 검증된 '일별' 시장 티커가 존재.** Phase 1 시장축 확장만으로 6섹터를 거의 즉시 점등 가능.

| 섹터 | 시장 티커(즉시·일별) | discourse RSS | 도메인 API |
|---|---|---|---|
| **핀테크** | `FINX`·`IPAY`·카카오페이 `377300.KS`·카카오뱅크 `323410.KS`·KODEX 은행 `091170.KS`·증권 `102970.KS` *(보조 `ARKF`·NHN한국사이버결제 `060250.KQ`)* | 전자신문 금융·금융위 보도자료·Platum/벤처스퀘어 핀테크 태그 | 네이버 데이터랩 검색트렌드·한국은행 ECOS 간편결제 |
| **모빌리티** | `KARS`·`DRIV`·`IDRV`·현대차 `005380.KS`·기아 `000270.KS`·KODEX 2차전지 `305720.KS`·TIGER 2차전지TOP10 `364980.KS` | 모터그래프·데일리카 | KIPRIS 특허 MOBILITY/IPC(`B60L`·`B60W`) 확장·국토부 자동차등록 |
| **콘텐츠** | `XLC`·KODEX 웹툰&드라마 `395150.KS`·TIGER K게임 `300610.KS`·ACE KPOP `475050.KS`·`ESPO`·`SOCL` | 전자신문 게임·방송 | **KOBIS 일별 박스오피스(영진위)**·YouTube Data API v3(KR)·KOPIS 공연 |
| **에듀테크** | 메가스터디교육 `215200.KQ`·디지털대성 `068930.KQ`·웅진씽크빅 `095720` 등 | 에듀플러스·네이버 뉴스검색 | 네이버 데이터랩·HRD-Net 직업훈련/이러닝 |
| **물류** | KODEX 운송·CJ대한통운 `000120.KS`·현대글로비스·한진·`IYT` | 물류신문 | KOSIS 운수업/택배·온라인쇼핑동향 `DT_1KE10071` |
| **사회서비스** | ❌ 없음(프록시 `AGNG` 보조) | 웰페어뉴스·복지타임즈·정책브리핑 복지부(`dept_mw.xml`) | 기업마당(bizinfo) 지원사업·사회보장정보원 지자체복지 |
| **뷰티·패션** | TIGER 화장품 `228790.KS`·HANARO K-Beauty `479850.KS`·LG생활건강 `051900.KS`·아모레퍼시픽 `090430.KS`·F&F `383220.KS` | 뷰티경제·뷰티누리/CMN·Newswire 화장품 | 네이버 데이터랩 쇼핑인사이트·MFDS 기능성화장품·KOSIS 온라인쇼핑 |

## 5. 변경 파일 (대표 경로)

| Phase | 파일 | 변경 |
|---|---|---|
| 0 | `backend/scripts/sector_axis_density_audit.py` (신규) | 섹터×축 20일 신호밀도·게이트 부족분 진단 |
| 1 | [pulse_repository.py](../hub/repositories/pulse_repository.py) `_MARKET_SOURCE_MAP` | 검증 티커 → 섹터 시드 추가 |
| 1 | `domain/master/hub/services/collectors/economic/yahoo/` | 수집 티커 목록 확장 |
| 2 | `domain/master/hub/services/collectors/discourse/news_rss/` | 토픽 RSS 피드 추가 |
| 2 | `domain/master/hub/services/collectors/<axis>/<신규>/` | 신규 도메인 API 수집기(소스 카탈로그 기준) |

## 6. 검증 / 성공 기준

- **Phase 0** — 진단 스크립트가 7섹터 각각의 축별 밀도·게이트 부족분 출력. 순수 집계 로직 `pytest` 회귀.
- **Phase 1** — 티커 추가 후 Pulse refine 재실행 → 대상 섹터 `data_status` 가 `insufficient`→`active` 전환, 실신호 분포(전부 50 아님) 확인. 기존 `pulse_scoring_test`·`pulse_axis_normalize_test` 무회귀. KIAT 백필 도달률 재측정.
- **Phase 2** — 신규 수집기 통합 테스트(live fetch·적재 건수) → LLM 분류 후 텍스트 축 집계 반영 확인.
- **공통** — 활성화는 "20일 윈도우 비영 신호 ≥5 연속 충족"으로 측정. 우연한 1셀 ≠50 이 아닌 진짜 신호 분포인지 육안 확인.

## 7. 리스크 / 완화

- **ETF 한국 대표성** — 글로벌/미국 상장 ETF는 한국 선행지표로만 해석. 가능하면 한국 상장 ETF(KODEX·TIGER·ACE·HANARO)·대표주 병행.
- **개별주 노이즈** — 기업 특이 리스크 → 거래대금 상대유량 + 개별주 threshold(기존 통화중립 패턴) 적용.
- **사회서비스 구조적 공백** — 시장 티커 없음 → 가장 느린 트랙, discourse/opportunity 의존. 활성화 기대치 별도 관리.
- **게이트 임의 완화 금지** — 노이즈 방지장치를 약화하면 거짓 급등 재발. 증거 기반으로만 캘리브레이션.

> 참고: [SILVER_PULSE_STRATEGY.md](SILVER_PULSE_STRATEGY.md) · [audit_trail.md](audit_trail.md) · ERD [`backend/docs/erd.md`](../../../docs/erd.md) §5·§6 · 검증 로그 `tasks/w87z94v18.output`(140건)
