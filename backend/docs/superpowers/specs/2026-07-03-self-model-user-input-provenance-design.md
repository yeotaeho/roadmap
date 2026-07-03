# SP-7② — 자기모델 사용자 입력 UI + 축별 provenance 설계

2026-07-03 확정. 사용자가 AI의 자기모델 판단을 교정·확정하는 입력 경로를 만들고, 출처를 **축별로** 기록해
사용자가 확정한 축은 코치 대화 추출이 잠식하지 않게 한다(SP-5에서 이연했던 P2 근본 해소).

## 확정 결정 (사용자 확답)

| 결정 | 선택 |
|---|---|
| 편집 단위 | 축당 **3단계(낮음 25·중간 50·높음 75)** + **AI판단(auto)** |
| user_form 의미 | **사용자 확정 = 고정** — 그 축은 코치 추출이 안 건드림(다른 축은 계속 누적). 사용자가 언제든 재편집·AI에게 다시 맡기기 |
| UI 위치 | `SelfModelPanel`의 "수정" 버튼 → 모달 |
| 편집 대상 | RIASEC 6축 · Big Five 5축 · 서사 한 줄 |

## 배경 (P2)

`user_self_model.source`가 **행당 단일 필드**라 "RIASEC은 사용자 확정, Big Five는 AI 추출" 혼합을 표현 못 한다.
그래서 사용자가 한 축을 확정해도 행 전체가 user_form이 되고, 다음 추출이 다른 축까지 "사용자 입력"으로 오인해
누적을 멈춘다(SP-5 Codex P2). **출처를 축별로** 기록해 해소한다.

## A. 스키마 (마이그레이션 1건 · Neon)

`user_self_model`에 `axis_source JSONB NULL` 추가(`axis_confidence` 패턴 그대로).
- 값: **user_form으로 확정한 축만** 키로 담는다. 예 `{"riasec":"user_form", "narrative_summary":"user_form"}`.
  키에 없는 축·NULL·`{}` = 코치 소유(현 동작). auto 처리 = 그 키 제거.
- 기존 행은 NULL → "user_form 축 없음" → 코치가 전 축 blend(하위호환). 행 단위 `source`는 요약용으로 유지.

## B. 병합 — 축별 가드 (extraction 경로)

`merge_structured`(대화 추출용)의 **잠식 방지 가드를 행 source → 축별 `axis_source`로** 바꾼다.
- riasec·big_five blend 분기: `if axis_source.get(axis) == "user_form": continue`(그 축 blend 스킵). 나머지 축은 blend.
- narrative 등 일반 축: 동일하게 `axis_source.get(axis) == "user_form"`이면 보존.
- `merge_structured`는 기존 `axis_source`를 **그대로 result에 실어** 보존한다(추출은 provenance를 바꾸지 않음).
- `write_self_model`·`fetch_self_model`에 `axis_source` 파라미터·컬럼 추가.

## C. 사용자 편집 쓰기 — `apply_user_edits` + `PUT /api/user/self-model`

병합(blend)과 분리된 신규 서비스 메서드 `SelfModelService.apply_user_edits(user_id, edits) -> dict`.
- **입력** `edits`: 축별 상태. 예 `{"riasec": {"R":"low","I":"high",...}, "big_five": {"O":"high",...,"stability":"high"},
  "narrative": "탐구를 좋아하는 빌더" | None, "auto": ["big_five"]}`. (정확한 계약은 플랜에서 확정.)
- **레벨→점수**: `low=25, mid=50, high=75`. RIASEC·Big Five 각 축에 적용.
- **정서안정성 flip**: UI는 신경성을 **정서안정성**으로 받는다. 저장은 canonical `N = 100 − 안정성점수`(SP-5 정책).
- **고정 축 형태**: user_form 축은 `{scores(레벨매핑), raw=scores, weights=축 완전표현값, top_codes(riasec는 파생)}` 로
  저장하고 `axis_source[axis]="user_form"`. 얼려 있는 동안 표시엔 scores 사용, 해제 시 raw/weights로 blend 재개.
- **auto(=AI판단)**: 그 축을 `axis_source`에서 제거(코치 재개). 값은 유지(마지막 상태에서 blend 이어감).
- **서사**: 자유 텍스트. 설정 시 axis_source["narrative_summary"]="user_form", auto면 제거.
- 기존 `upsert_structured`(추출용)는 그대로. `apply_user_edits`는 fetch→축별 적용→`write_self_model`(axis_source 포함).

## D. 프론트 — 편집 모달

- `get_self_model` 응답에 `axisSource` 추가(UI가 어느 축이 사용자 고정인지 표시).
- `SelfModelPanel`에 "수정" 버튼 → 모달. 각 축을 **낮음·중간·높음·AI판단** 세그먼트 컨트롤로, 서사는 텍스트박스.
  현재 값(AI 추정 or 사용자 고정)을 기본 선택으로. 신경성은 "정서안정성"으로 표기.
- 저장 → `PUT /api/user/self-model`(신규 `lib/api/selfModel.ts` `updateSelfModel`) → 성공 시 `["self-model", profile.id]` 무효화·리페치.
- 고정된 축은 "내가 확정" 배지 등으로 구분(선택).

## E. 테스트

- 백엔드 순수/통합: (1) merge 축별 가드 — user_form 축은 추출 blend가 보존, 코치 소유 축은 계속 blend, auto 해제 후 재개.
  (2) `apply_user_edits` — 레벨→점수 매핑, 정서안정성 flip 저장(canonical N), 고정 축 형태·axis_source 표시, auto 제거.
  (3) 엔드포인트 — PUT 인증·검증·저장. (4) 회귀 — self_model_extraction·merge·recommend·embed(riasec.top_codes 계약 유지).
- 프론트 `pnpm exec tsc --noEmit` 0 에러.

## F. 범위 밖 (후속)

- ③ 규준집단 백분위. 정식 검사 결과 import(외부 검사 연동). 편집 이력·되돌리기. 세밀 슬라이더(현재 3단계).

## 파일 지도

| 영역 | 파일 |
|---|---|
| 스키마·마이그 | `backend/domain/user_intelligence/models/bases/user_self_model.py` · `backend/alembic/versions/<new>` |
| 리포 | `backend/domain/user_intelligence/hub/repositories/self_model_repository.py`(axis_source read/write) |
| 서비스 | `backend/domain/user_intelligence/hub/services/self_model_service.py`(`merge_structured` 가드·`apply_user_edits`·`get_self_model` axisSource) |
| API | `backend/api/v1/user/user_routor.py`(`PUT /self-model`) |
| 프론트 | `www.yeotaeho.kr/src/lib/api/selfModel.ts` · `src/components/features/consult/SelfModelPanel.tsx` · 신규 편집 모달 컴포넌트 |
