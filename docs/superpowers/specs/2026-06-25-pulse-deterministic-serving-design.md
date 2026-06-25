# Pulse 결정론 부가 서빙 — 설계 (Spec)

> 작성 2026-06-25. market_insight 도메인. 제거됐던 PulseTab 섹션(모멘텀 차트·속도계/주간지수·히트맵)을 **실데이터 결정론 산출물**로 복원한다. 관련: [MARKET_INSIGHT_IMPLEMENTATION_STATUS.md](../../../backend/domain/market_insight/docs/MARKET_INSIGHT_IMPLEMENTATION_STATUS.md) §5-A.

## 0. 목표 & 성공 기준

`pulse_metrics_log`(Gold)에 이미 적재된 섹터×일자 시계열을 **즉석 집계**해, 프론트 Pulse 탭의 제거된 시각화를 복원한다. LLM·새 테이블·새 스케줄러 잡 없이 결정론으로만 산출한다.

**성공 기준**
- `GET /api/insight/pulse/overview`·`GET /api/insight/pulse/{sector}/history` 가 명세대로 응답한다.
- 순수 조립 함수 `assemble_overview()` 의 무네트워크 단위 테스트가 `FAIL=0`.
- 프론트 PulseTab이 **실제 12섹터** 라이브 데이터로 속도계/주간지수·연간 모멘텀 차트·섹터×시간 히트맵·관심 점유율을 렌더(mock 폴백 없음).
- `tsc` 통과 + `uvicorn`+`pnpm dev` 풀 렌더 검증.

## 1. 아키텍처

읽기 전용 즉석 집계. 기존 `Router → Repository` 흐름을 따르고, 비자명한 조립 로직만 순수함수로 분리한다(기존 `pulse_pipeline.py` 패턴과 동일 철학).

```
GET /api/insight/pulse/overview         → PulseRepository.fetch_overview()
GET /api/insight/pulse/{sector}/history → PulseRepository.fetch_history()
        └ raw SQL 집계(pulse_metrics_log) → assemble_overview()(순수) → JSON
프론트: lib/api/dashboard.ts → hooks/useDashboard.ts → PulseTab.tsx 섹션 복원
```

### 변경 파일
| 파일 | 변경 |
|---|---|
| `backend/domain/market_insight/hub/services/pulse_overview.py` | 신규 — 순수 조립 함수 `assemble_overview()` |
| `backend/domain/market_insight/hub/repositories/pulse_repository.py` | 메서드 2개 추가: `fetch_overview()`·`fetch_history()` + 집계 SQL 상수 |
| `backend/api/v1/insight/insight_routor.py` | 엔드포인트 2개 추가 |
| `backend/scripts/pulse_overview_test.py` | 신규 — 무네트워크 단위 테스트 |
| `www.yeotaeho.kr/src/lib/api/dashboard.ts` | `fetchPulseOverview()`·`fetchPulseHistory()` 추가 |
| `www.yeotaeho.kr/src/hooks/useDashboard.ts` | `usePulseOverview()`·`usePulseHistory()` 추가 |
| `www.yeotaeho.kr/src/components/features/dashboard/PulseTab.tsx` | 4개 섹션 복원, 라이브 바인딩 |

## 2. API 계약

### 2.1 `GET /api/insight/pulse/overview?heatmap_weeks=8&momentum_months=12`
쿼리 파라미터(옵션): `heatmap_weeks`(기본 8, 1~52), `momentum_months`(기본 12, 1~36).

```jsonc
{
  "success": true,
  "gauge": {
    "weekly_index": 72,        // 전 섹터 최신 score 단순평균(0~100, 반올림)
    "speed_kmh": 130,          // round(weekly_index * 1.8) → 0~180
    "day_delta_pct": 3.1,      // (오늘 평균−직전일 평균)/직전일 평균×100, 날짜<2면 null
    "top_mover": { "sector_slug": "ai-data", "sector_name": "AI·데이터", "momentum_pct": 41.2 } // 없으면 null
  },
  "momentum_series": [ { "bucket": "2026-06", "value": 71 } ],   // 월 버킷, 최근 momentum_months개, 과거→현재
  "heatmap": {
    "buckets": ["2026-W18", "...", "2026-W25"],                  // 최근 heatmap_weeks개 ISO주, 과거→현재
    "rows": [
      { "sector_slug": "ai-data", "sector_name": "AI·데이터", "accent_color": "#6366f1",
        "cells": [ { "bucket": "2026-W18", "score": 68 }, { "bucket": "2026-W19", "score": null } ] }
    ]
  },
  "share": [ { "sector_slug": "ai-data", "sector_name": "AI·데이터", "pct": 12.4 } ]  // 최신 score 비중
}
```

### 2.2 `GET /api/insight/pulse/{sector}/history?weeks=26`
쿼리 파라미터(옵션): `weeks`(기본 26, 1~104).

```jsonc
{
  "success": true,
  "sector_slug": "ai-data",
  "sector_name": "AI·데이터",
  "points": [ { "recorded_date": "2026-06-01", "score": 64, "momentum_pct": 5.2, "status_badge": "상승" } ] // 날짜 오름차순, 최근 weeks*7일
}
```
존재하지 않는 섹터 슬러그 → `404`.

## 3. 집계 정의 (결정론)

모두 `pulse_metrics_log`(컬럼: `sector_slug`·`recorded_date`·`score`·`status_badge`·`momentum_pct`)에서 산출. 섹터 메타(`name_ko`·`accent_color`)는 `sectors` JOIN.

- **weekly_index** = 최신일 기준 섹터별 1행(`DISTINCT ON (sector_slug) … ORDER BY recorded_date DESC`)의 `score` 단순평균, 반올림.
- **speed_kmh** = `round(weekly_index × 1.8)` (지수 100 → 180km/h, 기존 mock 상한과 일치).
- **day_delta_pct** = 전 섹터 **일평균 score**의 최근 2개 날짜 비교 `(d0−d1)/d1×100`. 날짜 2개 미만 또는 d1=0 → `null`.
- **top_mover** = 최신일 `momentum_pct` 최대 섹터. 전부 null이거나 데이터 없음 → `null`.
- **momentum_series** = `to_char(recorded_date,'YYYY-MM')` 버킷별 `round(avg(score))`, 최근 `momentum_months`개, 과거→현재.
- **heatmap.buckets** = 최근 `heatmap_weeks`개 ISO주 라벨(`to_char(date_trunc('week',recorded_date),'IYYY-"W"IW')`), 과거→현재.
- **heatmap.rows[].cells** = (섹터 × 주) 그 주 *마지막* score(`DISTINCT ON (sector, week) … ORDER BY recorded_date DESC`). 데이터 없는 칸 `score: null`. 행은 최신 score 내림차순.
- **share[].pct** = 섹터 최신 score ÷ Σ(최신 score) × 100, 소수 1자리. 최신 score 내림차순. Σ=0 → 빈 배열.

## 4. 리포지토리 / 순수함수 분리

- `PulseRepository.fetch_overview(heatmap_weeks, momentum_months)` — 4개 가벼운 raw SQL 실행 후 `assemble_overview(...)`에 위임.
  1. 최신 섹터 행(기존 `_LATEST_GOLD_SQL` 재사용 가능) — weekly_index·top_mover·share·히트맵 행 라벨.
  2. 월 평균 시계열.
  3. 주별 섹터 마지막 score.
  4. 최근 2개 날짜 일평균.
- `assemble_overview(latest, monthly, weekly, daily_avgs, heatmap_weeks, momentum_months) -> dict` — **DB 비의존 순수함수**(신규 `pulse_overview.py`). buckets 정렬·null 채움·gauge 계산·share 비중을 조립. 단위 테스트 대상.
- `PulseRepository.fetch_history(sector_slug, weeks) -> dict | None` — 단일 섹터 시계열. 섹터 미존재 시 `None`(라우터가 404).

SQL은 `_LATEST_GOLD_SQL` 패턴 준수: `text()` raw SQL, `JOIN sectors`, `idx_pulse_metrics_date_sector` 활용, asyncpg-safe(파라미터 `CAST` 처리, nullable 비교 시 `CAST(:p AS …) IS NULL`).

## 5. 프론트 복원 (실제 12섹터)

- `dashboard.ts`: `fetchPulseOverview()`·`fetchPulseHistory(sector)` 추가, 기존 axios 클라이언트·base URL 규약.
- `useDashboard.ts`: `usePulseOverview()`·`usePulseHistory(sector)` 추가(staleTime 5분·gcTime 10분·retry 1 등 기존 규약).
- `PulseTab.tsx`: 제거됐던 **속도계/주간지수 카드 · 연간 모멘텀 area 차트 · 섹터×시간 히트맵 · 관심 점유율** 복원. 기존 SVG 컴포넌트 구조를 재활용하되 **라이브 데이터 + 실제 12섹터**에 바인딩, `accent_color`로 색 지정. mock 6섹터 분류(`pulseSectors.ts` 잔재)는 사용하지 않음.
- 히트맵 색조는 score 구간별 톤(기존 `getHeatTone` 재활용), `null` 칸은 중립 회색.

### 복원하지 않음 (이 묶음 밖)
인과사슬(causal_chains)·세대교체 크로스오버(crossover_metrics)·키워드 티커/클라우드(trending_keywords)·3줄 브리핑(economic_briefings).

## 6. 에러 처리 & 엣지 케이스

- **이력 희소**(파이프라인 초기): `momentum_series`가 `momentum_months` 미만, 히트맵 칸 다수 `null` — 있는 만큼 반환(정직). 프론트는 짧은 시계열 렌더.
- **단일 날짜**: `day_delta_pct: null`.
- **데이터 전무**: 빈 배열 + gauge 필드 null → 프론트 기존 `PanelStatus` 빈/에러 규약(mock 폴백 없음).
- 라우터는 기존 try/except + `HTTPException(500)`(overview)·`HTTPException(404)`(history 미존재) 패턴.

## 7. 테스트

- **백엔드 단위(무네트워크)**: `scripts/pulse_overview_test.py` — `assemble_overview()` 합성 입력으로 (1) 정상 다섹터·다월, (2) 희소(<12개월·히트맵 null 칸), (3) 단일 날짜(day_delta null), (4) 전무(빈 배열·gauge null) 케이스 검증. 기존 스크립트 규약대로 `FAIL=0` 출력.
- **프론트**: `tsc` 통과 + `uvicorn main:app` + `pnpm --dir www.yeotaeho.kr dev`(:3000) 풀 렌더 검증(preview 도구로 4개 섹션 확인).

## 8. 비범위 & 선결

- **비범위**: causal_chains·crossover_metrics·trending_keywords·economic_briefings·섹터×축 히트맵·Redis 캐시·Gold 집계 테이블 — 각각 별도 스펙.
- **선결 확인**: Neon에 `pulse_metrics_log`가 실제 마이그레이션(head `f8c2e6a0d3b7`)됐는지 점검. 미적용이면 기존 `/api/insight/pulse`도 실패하므로, 구현 1단계에서 `alembic current` 또는 실 응답으로 확인.
