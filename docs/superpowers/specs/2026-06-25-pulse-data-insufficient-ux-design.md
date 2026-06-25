# Pulse 데이터-부족 섹터 시각 구분 — 설계 (Spec)

> 작성 2026-06-25. market_insight 도메인. 희소-0 게이트로 전 구간 중립화된(score=50·0%·보합) 섹터가 *진짜 중립*처럼 보이는 오해를 없애기 위해, "데이터 수집 중" 표식으로 시각 구분한다. 배경 진단: 12섹터 중 7개(핀테크·뷰티·콘텐츠·교육·물류·모빌리티·사회서비스)가 Bronze 신호 빈약으로 전부 50.

## 0. 목표 & 성공 기준
- overview 응답이 섹터별 `data_status`("active"|"insufficient")를 노출한다.
- 프론트 PulseTab의 **섹터 카드**·**히트맵 행**에서 insufficient 섹터에 "데이터 수집 중" 배지 + 회색 음영(점수는 흐리게 유지)이 보인다.
- 속도계·점유율 **수치는 변경하지 않는다**(시각 표식만).
- `pulse_overview_test.py` 무DB 테스트 `FAIL=0`, `tsc` 통과, 라이브 렌더 확인.

## 1. 접근
서빙 휴리스틱(마이그레이션 0). 희소-0 게이트가 정확히 `score=50`을 찍으므로, 윈도우 전부 50 = 실신호 없음으로 판별. "즉석 집계·무마이그레이션" 기존 방침과 일치. (대안: 파이프라인 충분성 플래그를 Gold에 적재 — 마이그레이션 필요해 보류.)

## 2. 탐지 규칙 (순수함수 `assemble_overview._heatmap`)
각 히트맵 행에 `data_status` 추가:
- 비-null 셀이 ≥1개이고 그 셀들이 **전부 50** → `"insufficient"`.
- 50이 아닌 셀이 하나라도 있음 → `"active"`.
- (검증: ai-data[47,100,…]→active / fintech·beauty[전부 50]→insufficient.)

## 3. 응답
`GET /api/insight/pulse/overview` 의 `heatmap.rows[]` 각 항목에 `data_status: "active"|"insufficient"` 필드 추가. 새 엔드포인트·쿼리·마이그레이션 없음.

## 4. 프론트 (PulseTab)
- `insufficientSlugs = Set(heatmap.rows where data_status==="insufficient").sector_slug)`.
- **섹터 카드**(분야별 트렌드 속도 현황): 슬러그가 insufficientSlugs에 있으면 "데이터 수집 중" 배지 + 회색 음영, 점수·모멘텀은 opacity로 흐리게 유지.
- **히트맵 행**: insufficient 행의 섹터명 옆 배지 + 라벨 음영.
- 점유율·속도계 수치/표시 불변.

## 5. 테스트
- `pulse_overview_test.py`에 `test_heatmap_data_status()` 추가: (1) 전부-50 행→insufficient, (2) 비-50 포함→active, (3) None+50 혼합→insufficient. `main()` 등록. `FAIL=0`.
- 프론트 `tsc` + 라이브 렌더(앱 엔드포인트, Pulse 선례).

## 6. 비범위
- 속도계 weekly_index·점유율에서 insufficient 섹터 제외(수치 재계산) — 별도.
- 파이프라인 충분성 플래그·마이그레이션 — 별도.
- 데이터 백필·신규 Bronze 소스 — 별도 프로젝트(#1).
