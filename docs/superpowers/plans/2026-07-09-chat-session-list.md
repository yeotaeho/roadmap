# 코치·상담 새 채팅 + 세션 목록 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]` tracking.

**Goal:** AI 코치(/coach)와 AI 상담실(/consult) 두 탭에 ChatGPT식 세션 목록·전환·새 채팅을 추가한다.

**Architecture:** 백엔드는 이미 사용자당 다중 세션을 담을 수 있는 스키마(coach_sessions·consult_sessions, 미사용 `title` 컬럼)를 가지고 있으나 API 표면이 "최근 active 1개 재사용"만 노출한다. 여기에 세션 목록 조회·강제 생성 API + 첫 메시지 자동 제목을 더하고, 프론트는 로드맵의 `RoadmapNavContext` 패턴을 복제한 Nav Context로 사이드바↔뷰가 세션 상태를 공유한다. 코치·상담은 백엔드가 완전 대칭이라 동일 패치를 양쪽에 적용한다.

**Tech Stack:** FastAPI/SQLAlchemy(text SQL), Next.js/React Context, TanStack 아님(세션 목록은 Context 로컬 상태로 충분).

## Global Constraints

- 새 소스 파일 첫 줄 한국어 주석. 한국어 문장 종결 `.` `?` `!` 만.
- 기존 스타일 유지: 리포지토리는 모듈 상수 `text()` SQL + `CAST(:x AS UUID)`, 라우터는 `{"success": True, ...}` 래핑 + `get_authenticated_user_id` 인증.
- 테스트는 pytest 아님 — `backend/scripts/<name>_test.py` 스탠드얼론(`check(name, cond)` PASS/FAIL, 실패 시 exit 1, `sys.stdout.reconfigure(encoding="utf-8")`). 실 Neon DB 사용 스크립트는 생성 행을 스스로 정리.
- 프론트 검증은 `pnpm exec tsc --noEmit`(exit 0). **`pnpm lint`는 리포 선재 파손이라 실행 금지.**
- 커밋 트레일러: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- **git add는 각 태스크 명시 파일만**(리포에 무관 dirty 파일 다수). `git add .` 금지.
- 마이그레이션 불필요(`title` 컬럼은 이미 존재, 신규 테이블·컬럼 없음).
- 코치·상담 대칭: 한 도메인에 넣은 변경은 다른 도메인에도 동일 형태로.

## 현행 기준점 (탐색 확정)

- 세션 테이블: `coach_sessions`/`consult_sessions` 모두 `id, user_id, status('active'|'ended'), started_at, ended_at, title(nullable·미사용), context_summary, summarized_until, created_at` (상담은 +`extracted_until, extracted_at`). user_id 유니크 제약 없음(다중 세션 가능).
- 리포: `create_session`(강제 신규 존재), `get_latest_active_session`(status='active' 최신 1건), `fetch_messages`, `count_messages`, `end_session`, `get_session` — [coach_session_repository.py](backend/domain/ai_coach/hub/repositories/coach_session_repository.py), 상담 대칭.
- 서비스: `get_or_create_session`(재사용 우선), `verify_owner`, `get_messages`, `end_session`, `stream_sse`(첫 줄에서 user 메시지 저장) — [coach_service.py:198](backend/domain/ai_coach/hub/services/coach_service.py).
- 라우터: `POST /sessions`(get-or-create), `POST /stream`, `POST /sessions/{id}/end`, `GET /sessions/{id}/messages` — [coach_routor.py](backend/api/v1/coach/coach_routor.py), 상담 대칭(`consult_routor.py`).
- 프론트 API: `createCoachSession`/`fetchCoachMessages`/`streamCoach`([coach.ts](www.yeotaeho.kr/src/lib/api/coach.ts)), 상담은 +`endConsultSession`·streamConsult(onSelfModelUpdated/onCoverage 콜백).
- 뷰: `CoachView`/`ConsultView`가 `sessionId`를 자체 useState로 보유, 마운트 시 get-or-create+히스토리 로드([CoachView.tsx:42-77](www.yeotaeho.kr/src/components/features/coach/CoachView.tsx)).
- 사이드바: `CoachSidebar`/`ConsultSidebar`는 플레이스홀더 버튼 1개. `MainLayout`이 pathname 분기로 마운트([MainLayout.tsx:80-83](www.yeotaeho.kr/src/components/layout/MainLayout.tsx)). 로드맵만 `RoadmapNavProvider`로 감쌈([:78-79]).
- 공유 상태 패턴: `RoadmapNavContext`(Provider가 shell 전체를 감싸 사이드바+뷰가 같은 context 소비). `SideNav`/`SideNavButton`(icon?/label/active/onClick) 재사용 프리미티브.

## 핵심 설계 결정

1. **빈 세션 방지(지연 생성)**: "새 채팅"은 DB 행을 즉시 만들지 않는다. 프론트에서 `sessionId=null`(빈 인사말)로만 두고, **첫 메시지 전송 시** 강제 생성 API로 세션을 만든다. → 제목 없는 빈 세션이 목록에 쌓이지 않음.
2. **자동 제목**: `stream_sse`가 user 메시지를 저장한 직후 `set_title_if_empty(session_id, 첫40자)` 호출. `WHERE title IS NULL` 가드로 멱등 — 첫 메시지만 제목이 되고 이후 no-op.
3. **목록 필터**: `EXISTS(메시지)` 세션만 반환(레거시 title=NULL 세션도 포함), 프론트에서 `title ?? "대화"` 폴백. created_at DESC.
4. **race 방지(navToken)**: 뷰의 히스토리 로드는 sessionId watcher가 아니라 Context의 `navToken`(네비게이션 시에만 증가) 변화로 트리거. 전송 중 강제 생성으로 sessionId가 바뀌는 것은 `adoptSession`(navToken 미증가)으로 처리해, 낙관적 추가한 user 메시지를 히스토리 재로드가 덮어쓰는 레이스를 원천 차단(C-1에서 겪은 함정).
5. **범위 밖(후속)**: 세션 삭제·이름 변경, LLM 요약 제목, 마지막 활동시각 정렬.

---

### Task 1: 백엔드 — 세션 목록·강제생성·자동제목 (코치+상담 대칭)

**Files:**
- Modify: `backend/domain/ai_coach/hub/repositories/coach_session_repository.py`, `backend/domain/user_intelligence/hub/repositories/consult_session_repository.py`
- Modify: `backend/domain/ai_coach/hub/services/coach_service.py`, `backend/domain/user_intelligence/hub/services/consult_service.py`
- Modify: `backend/api/v1/coach/coach_routor.py`, `backend/api/v1/consult/consult_routor.py`
- Test: `backend/scripts/chat_session_list_test.py`

**Interfaces (Produces):**
- Repo: `list_sessions(user_id) -> list[dict]`(각 `{id, title, created_at}`), `set_title_if_empty(session_id, title) -> None`.
- Service: `create_new_session(user_id) -> str`, `list_sessions(user_id) -> list[dict]`(각 `{id, title, createdAt}` — 라우터가 camelCase 직렬화). `stream_sse`에 제목 훅.
- HTTP: `GET /coach/sessions`·`GET /consult/sessions`, `POST /coach/sessions/new`·`POST /consult/sessions/new`.

- [ ] **Step 1: 리포지토리에 2개 메서드 추가 (코치)**

`coach_session_repository.py` 모듈 상수 영역에 추가:

```python
_LIST = text(
    "SELECT s.id, s.title, s.created_at FROM coach_sessions s "
    "WHERE s.user_id = CAST(:uid AS UUID) "
    "AND EXISTS (SELECT 1 FROM coach_messages m WHERE m.session_id = s.id) "
    "ORDER BY s.created_at DESC"
)
_SET_TITLE_IF_EMPTY = text(
    "UPDATE coach_sessions SET title = :title "
    "WHERE id = CAST(:id AS UUID) AND title IS NULL"
)
```

클래스에 메서드 추가:

```python
    async def list_sessions(self, user_id: str) -> list[dict]:
        rows = (await self.session.execute(_LIST, {"uid": user_id})).all()
        return [
            {"id": str(r.id), "title": r.title, "created_at": r.created_at.isoformat()}
            for r in rows
        ]

    async def set_title_if_empty(self, session_id: str, title: str) -> None:
        await self.session.execute(_SET_TITLE_IF_EMPTY, {"id": session_id, "title": title})
        await self.session.commit()
```

- [ ] **Step 2: 상담 리포지토리에 동일 추가**

`consult_session_repository.py`에 위와 동일하되 테이블명을 `consult_sessions`/`consult_messages`로. (상담 메시지 테이블명은 파일을 열어 확인 — coach_messages 대응. 상수·메서드 형태는 코치와 byte-동일.)

- [ ] **Step 3: 코치 서비스에 메서드 + 제목 훅**

`coach_service.py`에 제목 유도 순수 함수(모듈 레벨) 추가:

```python
def _derive_title(message: str) -> str:
    """첫 사용자 메시지에서 세션 제목 유도 — 한 줄, 최대 40자."""
    line = (message or "").strip().splitlines()[0] if (message or "").strip() else ""
    return line[:40] if line else "새 대화"
```

`CoachService`에 메서드 추가:

```python
    async def create_new_session(self, user_id: str) -> str:
        return await CoachSessionRepository(self.session).create_session(user_id)

    async def list_sessions(self, user_id: str) -> list[dict]:
        return await CoachSessionRepository(self.session).list_sessions(user_id)
```

`stream_sse`의 user 메시지 저장 블록(198-201행 부근)을 제목 세팅까지 하도록 교체:

```python
        async with AsyncSessionLocal() as db:
            repo = CoachSessionRepository(db)
            await repo.add_message(session_id, "user", message)
            await repo.set_title_if_empty(session_id, _derive_title(message))
```

- [ ] **Step 4: 상담 서비스에 동일 추가**

`consult_service.py`에 `_derive_title`(동일), `create_new_session`(상담은 이미 `create_session` public 메서드 존재 — 없으면 추가, 있으면 재사용해 `create_new_session` 래퍼 정의), `list_sessions` 추가. 상담 `stream_sse`의 user 메시지 저장 지점에 동일하게 `set_title_if_empty` 호출 추가(상담 리포 인스턴스명에 맞춰).

- [ ] **Step 5: 라우터에 2개 엔드포인트 추가 (코치)**

`coach_routor.py`에 추가(기존 엔드포인트 무수정):

```python
@router.get("/sessions")
async def list_sessions(
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """사용자의 코치 대화 세션 목록(메시지 있는 세션, 최신순)."""
    sessions = await CoachService(db).list_sessions(user_id)
    return {
        "success": True,
        "sessions": [
            {"id": s["id"], "title": s["title"], "createdAt": s["created_at"]}
            for s in sessions
        ],
    }


@router.post("/sessions/new")
async def create_new_session(
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """항상 새 코치 세션 생성(기존 active 재사용 안 함)."""
    session_id = await CoachService(db).create_new_session(user_id)
    return {"success": True, "sessionId": session_id}
```

주의: `GET /sessions`는 기존 `GET /sessions/{session_id}/messages`보다 **위 또는 아래 어디든** 등록돼도 FastAPI가 경로를 정확 매칭하지만, `POST /sessions/new`는 `POST /sessions`와 구분되는 별도 경로다(문제 없음).

- [ ] **Step 6: 상담 라우터에 동일 추가**

`consult_routor.py`에 위와 동일하되 `CoachService`→상담 서비스 클래스명, docstring "상담"으로.

- [ ] **Step 7: 테스트 작성**

`backend/scripts/chat_session_list_test.py` (실 Neon — 생성 세션·메시지 정리):

```python
# 코치·상담 세션 목록·강제생성·자동제목 테스트 — 실 DB(생성 행 정리)
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_pass = 0
_fail = 0


def check(name: str, cond: bool) -> None:
    global _pass, _fail
    if cond:
        _pass += 1
        print(f"PASS {name}")
    else:
        _fail += 1
        print(f"FAIL {name}")


async def _run_domain(label, repo_cls, msg_table, sess_table) -> None:
    from sqlalchemy import text

    from core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        uid = (await db.execute(text("SELECT id FROM users ORDER BY created_at DESC LIMIT 1"))).first()
        user_id = str(uid[0])

    async with AsyncSessionLocal() as db:
        repo = repo_cls(db)
        # 강제 생성 2회 → 서로 다른 세션.
        s1 = await repo.create_session(user_id)
        s2 = await repo.create_session(user_id)
        check(f"{label} create_new 서로 다름", s1 != s2)

        # 메시지 없으면 목록 제외.
        empty_list = await repo.list_sessions(user_id)
        check(f"{label} 빈 세션 목록 제외", all(x["id"] not in (s1, s2) for x in empty_list))

        # s1 에 메시지 + 제목.
        await repo.add_message(s1, "user", "데이터 분석가로 진로를 잡고 싶은데 무엇부터 할까요")
        await repo.set_title_if_empty(s1, "데이터 분석가로 진로를 잡고 싶은데 무엇부터 할까요"[:40])
        await repo.set_title_if_empty(s1, "덮어쓰면안됨")  # 멱등 — no-op.
        lst = await repo.list_sessions(user_id)
        found = next((x for x in lst if x["id"] == s1), None)
        check(f"{label} 메시지 세션 목록 포함", found is not None)
        check(f"{label} 제목 첫 메시지 고정", found and found["title"].startswith("데이터 분석가"))

        # 정리.
        await db.execute(text(f"DELETE FROM {msg_table} WHERE session_id IN (CAST(:a AS UUID), CAST(:b AS UUID))"), {"a": s1, "b": s2})
        await db.execute(text(f"DELETE FROM {sess_table} WHERE id IN (CAST(:a AS UUID), CAST(:b AS UUID))"), {"a": s1, "b": s2})
        await db.commit()


async def main() -> int:
    from domain.ai_coach.hub.repositories.coach_session_repository import CoachSessionRepository
    from domain.user_intelligence.hub.repositories.consult_session_repository import (
        ConsultSessionRepository,
    )

    await _run_domain("coach", CoachSessionRepository, "coach_messages", "coach_sessions")
    await _run_domain("consult", ConsultSessionRepository, "consult_messages", "consult_sessions")

    print(f"\nRESULT: PASS {_pass} / FAIL {_fail}")
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

주의: 상담 리포 클래스명·메시지 테이블명은 실제 파일을 열어 확인 후 맞춘다(ConsultSessionRepository/consult_messages 가정).

- [ ] **Step 8: 실행·커밋**

```bash
cd /c/project/roadmap/backend && python scripts/chat_session_list_test.py
```
Expected: `RESULT: PASS 8 / FAIL 0`.

```bash
cd /c/project/roadmap && git add backend/domain/ai_coach/hub/repositories/coach_session_repository.py backend/domain/user_intelligence/hub/repositories/consult_session_repository.py backend/domain/ai_coach/hub/services/coach_service.py backend/domain/user_intelligence/hub/services/consult_service.py backend/api/v1/coach/coach_routor.py backend/api/v1/consult/consult_routor.py backend/scripts/chat_session_list_test.py
git commit -m "feat(chat): 코치·상담 세션 목록·강제생성 API + 첫 메시지 자동 제목

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: 프론트 — API 클라이언트 + Nav Context + MainLayout 배선 (코치+상담)

**Files:**
- Modify: `www.yeotaeho.kr/src/lib/api/coach.ts`, `www.yeotaeho.kr/src/lib/api/consult.ts`
- Create: `www.yeotaeho.kr/src/components/features/coach/CoachNavContext.tsx`, `www.yeotaeho.kr/src/components/features/consult/ConsultNavContext.tsx`
- Modify: `www.yeotaeho.kr/src/components/layout/MainLayout.tsx`

**Interfaces:**
- Consumes: Task 1 `GET /sessions`, `POST /sessions/new`.
- Produces: `listCoachSessions()`/`createNewCoachSession()` (+consult), `SessionSummary` 타입, `CoachNavProvider`/`useCoachNav()` (+consult) — context 값 `{ sessionId, sessions, navToken, loadingSessions, selectSession, startNewChat, adoptSession, refreshSessions }`.

- [ ] **Step 1: coach.ts에 목록·강제생성 함수 추가**

`coach.ts` 상단 타입 + 함수 추가(기존 `createCoachSession` 등 무수정):

```ts
export interface SessionSummary {
  id: string;
  title: string | null;
  createdAt: string;
}

export async function listCoachSessions(): Promise<SessionSummary[]> {
  const token = getStore().getState().token;
  const res = await fetch(`${API_BASE_URL}/api/coach/sessions`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    credentials: 'include',
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data?.sessions ?? [];
}

export async function createNewCoachSession(): Promise<string | null> {
  const token = getStore().getState().token;
  const res = await fetch(`${API_BASE_URL}/api/coach/sessions/new`, {
    method: 'POST',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    credentials: 'include',
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data?.sessionId ?? null;
}
```

- [ ] **Step 2: consult.ts에 동일 추가**

`consult.ts`에 `SessionSummary`(이미 coach.ts에 있으니 consult는 재-export 대신 자체 정의 or import; 간단히 자체 정의) + `listConsultSessions`/`createNewConsultSession`을 `/api/consult/...` 경로로 추가.

- [ ] **Step 3: CoachNavContext 작성**

`www.yeotaeho.kr/src/components/features/coach/CoachNavContext.tsx`:

```tsx
"use client";

// 코치 사이드바(셸)와 CoachView 가 공유하는 세션 상태 Context — 세션 목록·전환·새 채팅.

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  createCoachSession,
  createNewCoachSession,
  listCoachSessions,
  type SessionSummary,
} from "@/lib/api/coach";
import { useStore } from "@/store";

interface CoachNavValue {
  sessionId: string | null;
  sessions: SessionSummary[];
  navToken: number;
  loadingSessions: boolean;
  selectSession: (id: string) => void;
  startNewChat: () => void;
  adoptSession: (id: string) => void;
  refreshSessions: () => Promise<void>;
}

const CoachNavContext = createContext<CoachNavValue | null>(null);

export function CoachNavProvider({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useStore((s) => s.isAuthenticated);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [navToken, setNavToken] = useState(0);

  const refreshSessions = useCallback(async () => {
    setLoadingSessions(true);
    try {
      setSessions(await listCoachSessions());
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  // 마운트/인증 전환: 최근 active 세션으로 초기화 + 목록 로드.
  useEffect(() => {
    if (!isAuthenticated) {
      setSessionId(null);
      setSessions([]);
      setNavToken((n) => n + 1); // 뷰가 인사말로 리셋.
      return;
    }
    let cancelled = false;
    (async () => {
      const sid = await createCoachSession(); // get-or-create(최근 active)
      if (cancelled) return;
      setSessionId(sid);
      setNavToken((n) => n + 1); // 뷰가 sid 히스토리 로드.
      await refreshSessions();
    })();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, refreshSessions]);

  const selectSession = useCallback((id: string) => {
    setSessionId(id);
    setNavToken((n) => n + 1);
  }, []);

  const startNewChat = useCallback(() => {
    setSessionId(null);
    setNavToken((n) => n + 1);
  }, []);

  // 전송 중 강제 생성한 세션 채택 — navToken 미증가(히스토리 재로드로 낙관적 메시지를 덮지 않음).
  const adoptSession = useCallback((id: string) => {
    setSessionId(id);
  }, []);

  const value = useMemo(
    () => ({
      sessionId,
      sessions,
      navToken,
      loadingSessions,
      selectSession,
      startNewChat,
      adoptSession,
      refreshSessions,
    }),
    [sessionId, sessions, navToken, loadingSessions, selectSession, startNewChat, adoptSession, refreshSessions],
  );
  return <CoachNavContext.Provider value={value}>{children}</CoachNavContext.Provider>;
}

export function useCoachNav(): CoachNavValue {
  const ctx = useContext(CoachNavContext);
  if (!ctx) throw new Error("useCoachNav must be used within a CoachNavProvider");
  return ctx;
}
```

- [ ] **Step 4: ConsultNavContext 작성**

동일 구조를 `consult` 경로·API(`createConsultSession`/`createNewConsultSession`/`listConsultSessions`)로. 파일 `www.yeotaeho.kr/src/components/features/consult/ConsultNavContext.tsx` (consult 뷰 폴더 경로는 실제 위치 확인 후 맞춤).

- [ ] **Step 5: MainLayout 배선**

`MainLayout.tsx`에 import 추가 후 분기 교체:

```tsx
  } else if (pathname === "/consult") {
    body = <ConsultNavProvider>{shell(<ConsultSidebar />, "max-w-none")}</ConsultNavProvider>;
  } else if (pathname?.startsWith("/coach")) {
    body = <CoachNavProvider>{shell(<CoachSidebar />, "max-w-none")}</CoachNavProvider>;
```

- [ ] **Step 6: tsc 검증·커밋**

```bash
cd /c/project/roadmap/www.yeotaeho.kr && pnpm exec tsc --noEmit
```
Expected: exit 0.

```bash
cd /c/project/roadmap && git add www.yeotaeho.kr/src/lib/api/coach.ts www.yeotaeho.kr/src/lib/api/consult.ts www.yeotaeho.kr/src/components/features/coach/CoachNavContext.tsx www.yeotaeho.kr/src/components/features/consult/ConsultNavContext.tsx www.yeotaeho.kr/src/components/layout/MainLayout.tsx
git commit -m "feat(chat): 세션 목록 API 클라이언트 + 코치·상담 Nav Context·MainLayout 배선

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: 프론트 — 뷰 리팩터 + 사이드바 세션 목록 UI (코치+상담)

**Files:**
- Modify: `www.yeotaeho.kr/src/components/features/coach/CoachView.tsx`, `www.yeotaeho.kr/src/components/features/coach/CoachSidebar.tsx`
- Modify: 상담 뷰(`ConsultView.tsx`), 상담 사이드바(`ConsultSidebar.tsx`)

**Interfaces:**
- Consumes: Task 2 `useCoachNav()`/`useConsultNav()`.

- [ ] **Step 1: CoachView 리팩터 — 세션 소유권을 Context로 이관**

`CoachView.tsx`에서: 기존 `sessionId` useState와 마운트 get-or-create useEffect(34, 42-77행)를 제거하고 `const { sessionId, navToken, adoptSession, refreshSessions } = useCoachNav();`로 대체. 메시지 로드는 `navToken`을 키로:

```tsx
  // navToken 변화(네비게이션)에만 히스토리 로드 — 전송 중 세션 채택은 재로드하지 않음.
  useEffect(() => {
    if (!isAuthenticated) {
      setMessages([GREETING]);
      setToolActivity(null);
      setSessionError(false);
      return;
    }
    let cancelled = false;
    setMessages([GREETING]);
    setToolActivity(null);
    setSessionError(false);
    if (!sessionId) return; // 새 채팅(빈 세션) — 인사말만.
    (async () => {
      try {
        const msgs = await fetchCoachMessages(sessionId);
        if (cancelled) return;
        if (msgs.length > 0) {
          setMessages(msgs.map((m) => ({ id: uid(), role: m.role, text: m.content })));
        }
      } catch {
        /* 히스토리 로드 실패는 대화를 막지 않는다. */
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navToken, isAuthenticated]);
```

`send`를 첫 전송 시 강제 생성하도록 수정:

```tsx
  const send = useCallback(async () => {
    const message = input.trim();
    if (!message || isLoading || !isAuthenticated) return;
    let sid = sessionId;
    if (!sid) {
      sid = await createNewCoachSession();
      if (!sid) {
        setSessionError(true);
        return;
      }
      adoptSession(sid); // navToken 미증가 — 아래 낙관적 메시지 유지.
    }
    setInput("");
    setIsLoading(true);
    const assistantId = uid();
    setMessages((prev) => [
      ...prev,
      { id: uid(), role: "user", text: message },
      { id: assistantId, role: "assistant", text: "" },
    ]);
    const appendDelta = (text: string) =>
      setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, text: m.text + text } : m)));
    try {
      await streamCoach(sid, message, {
        onDelta: (t) => { setToolActivity(null); appendDelta(t); },
        onToolCall: (_n, label) => setToolActivity(label),
        onToolResult: () => setToolActivity(null),
        onError: (msg) => appendDelta(`\n(${msg})`),
      });
    } catch {
      appendDelta("\n(연결에 문제가 생겼어요. 잠시 후 다시 시도해 주세요.)");
    } finally {
      setToolActivity(null);
      setIsLoading(false);
      void refreshSessions(); // 새 세션 제목이 목록에 나타나도록 갱신.
    }
  }, [input, isLoading, isAuthenticated, sessionId, adoptSession, refreshSessions]);
```

입력 disabled 조건에서 `!sessionId`를 제거(새 채팅 상태에서 입력 가능해야 함): `disabled={!isAuthenticated || isLoading}`. import에 `createNewCoachSession` 추가.

- [ ] **Step 2: CoachSidebar — 새 채팅 + 세션 목록**

`CoachSidebar.tsx` 교체:

```tsx
"use client";

// 코치 좌측 사이드바 — 새 채팅 + 세션 목록(전환).

import { MessageSquarePlus, MessageCircle } from "lucide-react";
import { SideNav, SideNavButton } from "@/components/layout/SideNav";
import { useCoachNav } from "./CoachNavContext";

export function CoachSidebar() {
  const { sessionId, sessions, selectSession, startNewChat } = useCoachNav();
  return (
    <SideNav>
      <SideNavButton icon={MessageSquarePlus} label="새 채팅" onClick={startNewChat} active={sessionId === null} />
      {sessions.map((s) => (
        <SideNavButton
          key={s.id}
          icon={MessageCircle}
          label={s.title ?? "대화"}
          active={sessionId === s.id}
          onClick={() => selectSession(s.id)}
        />
      ))}
    </SideNav>
  );
}
```

- [ ] **Step 3: ConsultView 리팩터**

CoachView와 동일 패턴으로 상담 뷰를 Context 소비로 전환. 상담 고유 사항:
- `sessionIdRef`도 context sessionId를 미러링하도록 유지(streamConsult가 ref를 쓰면).
- 첫 전송 강제 생성은 `createNewConsultSession` 사용.
- **coverage 리셋**: 기존 `profile?.id` 변경 시 coverage 리셋 effect에 `navToken` 의존성을 더해, 세션 전환·새 채팅 시 커버리지 진행률도 초기화(세션마다 extracted_until=0).
- SelfModelPanel invalidate 등 나머지 로직 보존.

- [ ] **Step 4: ConsultSidebar — 새 채팅 + 세션 목록**

CoachSidebar와 동일 구조로 `useConsultNav()` 소비.

- [ ] **Step 5: tsc 검증·커밋**

```bash
cd /c/project/roadmap/www.yeotaeho.kr && pnpm exec tsc --noEmit
```
Expected: exit 0.

```bash
cd /c/project/roadmap && git add www.yeotaeho.kr/src/components/features/coach/CoachView.tsx www.yeotaeho.kr/src/components/features/coach/CoachSidebar.tsx www.yeotaeho.kr/src/components/features/consult/ConsultView.tsx www.yeotaeho.kr/src/components/features/consult/ConsultSidebar.tsx
git commit -m "feat(chat): 코치·상담 뷰 세션 전환 리팩터 + 사이드바 세션 목록·새 채팅 UI

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: 검증 (preview) + 문서

**Files:**
- (선택) 감사 기록 md — 경로는 사용자 승인 후.

- [ ] **Step 1: 프리뷰 기동·수동 검증**

`preview_start`로 dev 서버 기동 후 로그인 상태로 /coach 진입 → (1) 사이드바에 기존 세션 목록·"새 채팅" 표시, (2) "새 채팅" 클릭 → 인사말만, (3) 첫 메시지 전송 → 응답 스트리밍, 목록에 새 세션(제목=메시지) 추가, (4) 다른 세션 클릭 → 히스토리 전환, (5) /consult 동일 확인. `preview_screenshot`로 증거.

- [ ] **Step 2: 회귀 확인**

```bash
cd /c/project/roadmap/backend && python scripts/coach_endpoint_test.py && python scripts/chat_session_list_test.py
cd /c/project/roadmap/www.yeotaeho.kr && pnpm exec tsc --noEmit
```

- [ ] **Step 3: (선택) 감사 기록**

경로 승인 후 관련 도메인 audit_trail 갱신.

## 검증 전략

- 백엔드 단위: `chat_session_list_test.py`(코치·상담 각 4체크 — 강제생성 분리·빈 세션 제외·목록 포함·제목 멱등).
- 회귀: `coach_endpoint_test.py`(기존 라우트 등록·인증) green 유지.
- 프론트: `tsc --noEmit` exit 0, preview 수동 플로우(새 채팅→전송→목록 추가→전환).
- race 회귀: 새 채팅 첫 전송 시 낙관적 user 메시지가 유지되는지(navToken 미증가 확인) preview에서 육안 확인.
