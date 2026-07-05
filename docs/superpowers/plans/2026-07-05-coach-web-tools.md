# C-2 코치 웹 tool 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 코치 채팅에 웹 tool 2종(web_search=Tavily 검색, fetch_url=WaterCrawl 본문 추출)을 붙여 훈련 컷오프 이후의 최신 정보를 출처와 함께 답변에 반영하게 한다.

**Architecture:** C-1의 tool 레이어(`ai_coach/spokes/agents/tools/`)에 `web_tools.py` 모듈을 추가하고, `CoachService._build_tools`가 내부 6종 + 웹 2종을 합성한다. 키가 없는 tool은 목록에서 제외(모델이 호출 시도조차 안 하게)하고, 호출 실패는 error dict 관찰로 되돌려 대화를 끊지 않는다. 시스템 프롬프트에 웹 라우팅·출처 표기 지침을 추가한다.

**Tech Stack:** Tavily Search API(raw HTTP, httpx) · watercrawl-py 0.9.2(동기 requests 기반 → `asyncio.to_thread`) · LangChain `@tool`

**스펙:** `docs/superpowers/specs/2026-07-05-ai-coach-roadmap-agent-design.md` §2-⑥, §4 (C-2 범위만. render_widget·deepagents는 범위 밖)

## Global Constraints

- 새 소스 파일 첫 줄: 한 줄 한국어 주석. 한국어 문장 종결은 `.` `?` `!` 만.
- 테스트 컨벤션: `backend/scripts/<name>_test.py` 단독 스크립트 — `check(name, cond)` PASS/FAIL 패턴, exit 0 성공.
- tool 전부 read-only. **출처 URL 필수 반환** — web_search 결과 행마다 `url`, fetch_url 반환에 `url` 포함.
- 가드(스펙 §4): 검색 결과 최대 5건·스니펫 300자, 본문 8000자 상한(+잘림 표시), 검색 타임아웃 15s, 본문 추출 45s.
- provider 플러거블 원칙: Tavily/WaterCrawl 호출부는 `web_tools.py` 한 파일에 격리 — 향후 보조 provider(Naver 등) 재도입 시 이 파일만 교체.
- **한 프로세스에서 asyncio.run() 1회** 원칙 유지(기존 임베딩 클라이언트 싱글턴 제약). httpx AsyncClient는 요청마다 생성(루프 바인딩 회피 — 웹 호출은 저빈도라 커넥션 풀 재사용 이득이 없음).
- Tavily 계약(공식 문서 확인): `POST https://api.tavily.com/search`, 헤더 `Authorization: Bearer <key>`, body `{"query", "max_results"}`, 응답 `{"results": [{"title","url","content","score"}]}`.
- WaterCrawl 계약(공식 문서·PyPI 확인): `watercrawl-py>=0.9.2`(의존성 requests), `WaterCrawlAPIClient(api_key).scrape_url(url)` 동기 호출, 반환은 `{"result": {"markdown": ...}}` 또는 result 객체 직접 — **셰이핑에서 양쪽 모두 방어**.
- env 키는 프로젝트 루트 `.env`에 이미 등록됨: `TAVILY_API_KEY`, `WATERCRAWL_API_KEY`.
- 커밋: 태스크당 1커밋, semantic prefix, 끝에 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: 설정 + web_tools 모듈 + 단위 테스트

**Files:**
- Modify: `backend/requirements.txt` (2줄 추가)
- Modify: `backend/core/config/settings.py` (LLM 필드 블록에 2필드 추가)
- Create: `backend/domain/ai_coach/spokes/agents/tools/web_tools.py`
- Test: `backend/scripts/coach_web_tools_test.py`

**Interfaces:**
- Consumes: 없음 (독립).
- Produces:
  - `WEB_TOOL_LABELS: dict[str, str]` — `{"web_search": "웹 검색", "fetch_url": "웹 페이지 읽기"}`.
  - `build_web_tools(settings=None) -> list[StructuredTool]` — settings 미지정 시 `get_settings()`. 키가 등록된 tool만 반환(0~2개).
  - 순수 함수 `shape_search_results(data: dict) -> dict`, `shape_page(url: str, result: dict) -> dict`.
  - settings 필드 `tavily_api_key: Optional[str]`(alias `TAVILY_API_KEY`), `watercrawl_api_key: Optional[str]`(alias `WATERCRAWL_API_KEY`).

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/scripts/coach_web_tools_test.py`:

```python
# 코치 웹 tool 팩토리·셰이핑 단위 테스트(무DB·무네트워크) — 키 없으면 tool 제외·상한·출처 계약

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.ai_coach.spokes.agents.tools.web_tools import (
    WEB_TOOL_LABELS,
    build_web_tools,
    shape_page,
    shape_search_results,
)

PASS = 0
FAIL = 0


def check(n: str, c: bool, e: str = "") -> None:
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"[PASS] {n}")
    else:
        FAIL += 1
        print(f"[FAIL] {n} {e}")


def run() -> int:
    # 셰이핑 — 검색 결과
    data = {
        "results": [
            {"title": f"t{i}", "url": f"https://ex.com/{i}", "content": "x" * 500}
            for i in range(7)
        ]
        + [{"title": "no-url", "content": "y"}]
    }
    out = shape_search_results(data)
    check("검색 결과 최대 5건", len(out["results"]) == 5)
    check("스니펫 300자 상한", all(len(r["snippet"]) <= 300 for r in out["results"]))
    check("행마다 출처 url", all(r["url"].startswith("https://") for r in out["results"]))
    check("빈 응답 안전", shape_search_results({}) == {"results": []})

    # 셰이핑 — 페이지 본문 (중첩/평면 양쪽 방어)
    nested = {"result": {"markdown": "z" * 9000}}
    p1 = shape_page("https://ex.com", nested)
    check("본문 8000자 상한", len(p1["content"]) == 8000)
    check("잘림 표시", p1["truncated"] is True)
    check("url 포함", p1["url"] == "https://ex.com")
    flat = {"markdown": "짧은 본문."}
    p2 = shape_page("https://ex.com", flat)
    check("평면 응답 방어", p2["content"] == "짧은 본문." and p2["truncated"] is False)
    check("빈 응답 안전(페이지)", shape_page("https://ex.com", {})["content"] == "")

    # 팩토리 — 키 유무에 따른 tool 구성
    both = build_web_tools(SimpleNamespace(tavily_api_key="tk", watercrawl_api_key="wk"))
    names = {t.name for t in both}
    check("키 2개 → tool 2종", names == {"web_search", "fetch_url"}, str(names))
    check("전부 비동기", all(t.coroutine is not None for t in both))
    check("전부 설명 보유", all((t.description or "").strip() for t in both))

    none = build_web_tools(SimpleNamespace(tavily_api_key=None, watercrawl_api_key=None))
    check("키 없으면 빈 목록", none == [])

    only_search = build_web_tools(SimpleNamespace(tavily_api_key="tk", watercrawl_api_key=None))
    check("검색 키만 → web_search만", [t.name for t in only_search] == ["web_search"])

    # 라벨 계약
    check("라벨 전수", set(WEB_TOOL_LABELS.keys()) == {"web_search", "fetch_url"})
    check("라벨 한국어", all(any("가" <= ch <= "힣" for ch in v) for v in WEB_TOOL_LABELS.values()))

    print(f"\n합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python scripts/coach_web_tools_test.py`
Expected: `ModuleNotFoundError: ... web_tools`

- [ ] **Step 3: 의존성·설정 추가**

`backend/requirements.txt` 끝에 추가 (먼저 `httpx`가 이미 명시돼 있는지 확인 — 있으면 watercrawl-py 한 줄만):

```
httpx>=0.27.0
watercrawl-py>=0.9.2
```

`backend/core/config/settings.py` — 코치 LLM 필드(`anthropic_api_key` 근처)에 추가:

```python
    # 코치 웹 tool (C-2)
    tavily_api_key: Optional[str] = Field(default=None, validation_alias="TAVILY_API_KEY")
    watercrawl_api_key: Optional[str] = Field(default=None, validation_alias="WATERCRAWL_API_KEY")
```

설치: `cd backend && pip install -r requirements.txt` → `python -c "import watercrawl, httpx; print('ok')"` → `ok`

- [ ] **Step 4: web_tools 구현**

`backend/domain/ai_coach/spokes/agents/tools/web_tools.py`:

```python
# 코치 웹 tool 2종 — Tavily 검색·WaterCrawl 본문 추출(read-only, 출처 URL 필수 반환)

from __future__ import annotations

import asyncio
import logging

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

WEB_TOOL_LABELS: dict[str, str] = {
    "web_search": "웹 검색",
    "fetch_url": "웹 페이지 읽기",
}

_TAVILY_ENDPOINT = "https://api.tavily.com/search"
_SEARCH_MAX_RESULTS = 5
_SEARCH_TIMEOUT_S = 15.0
_SNIPPET_MAX_CHARS = 300
_FETCH_TIMEOUT_S = 45.0
_PAGE_MAX_CHARS = 8000


def shape_search_results(data: dict) -> dict:
    """Tavily 응답 → 축약 결과. 행마다 출처 url 을 보장한다(없는 행은 제외)."""
    results = []
    for r in data.get("results") or []:
        url = r.get("url")
        if not url:
            continue
        results.append(
            {
                "title": r.get("title") or "",
                "url": url,
                "snippet": (r.get("content") or "")[:_SNIPPET_MAX_CHARS],
            }
        )
        if len(results) >= _SEARCH_MAX_RESULTS:
            break
    return {"results": results}


def shape_page(url: str, result: dict) -> dict:
    """WaterCrawl scrape 응답 → 축약 본문. 중첩({"result": {...}})·평면 양쪽을 방어한다."""
    inner = result.get("result") if isinstance(result.get("result"), dict) else result
    markdown = (inner or {}).get("markdown") or ""
    truncated = len(markdown) > _PAGE_MAX_CHARS
    return {"url": url, "content": markdown[:_PAGE_MAX_CHARS], "truncated": truncated}


def build_web_tools(settings=None) -> list:
    """키가 등록된 웹 tool 만 생성한다 — 미설정 tool 은 목록에서 제외(모델이 호출 시도조차 안 하게)."""
    if settings is None:
        from core.config.settings import get_settings

        settings = get_settings()

    tools: list = []
    tavily_key = getattr(settings, "tavily_api_key", None)
    watercrawl_key = getattr(settings, "watercrawl_api_key", None)

    if tavily_key:

        @tool
        async def web_search(query: str) -> dict:
            """내부 데이터로 답할 수 없는 최신 정보(뉴스·시세·마감 임박 공고·기술 동향)를 웹에서 검색한다. 결과의 출처 URL 을 답변에 반드시 표기한다."""
            try:
                # httpx AsyncClient 는 요청마다 생성 — 루프 바인딩 회피(웹 호출은 저빈도).
                async with httpx.AsyncClient(timeout=_SEARCH_TIMEOUT_S) as client:
                    res = await client.post(
                        _TAVILY_ENDPOINT,
                        headers={"Authorization": f"Bearer {tavily_key}"},
                        json={"query": query, "max_results": _SEARCH_MAX_RESULTS},
                    )
                if res.status_code != 200:
                    logger.warning(f"Tavily 검색 실패(status {res.status_code})")
                    return {"error": f"웹 검색에 실패했습니다(status {res.status_code})."}
                return shape_search_results(res.json())
            except Exception as e:  # 웹 실패는 대화를 끊지 않는다 — 관찰로 되돌린다.
                logger.warning(f"Tavily 검색 예외: {e}")
                return {"error": "웹 검색 중 오류가 발생했습니다."}

        tools.append(web_search)
    else:
        logger.warning("TAVILY_API_KEY 미설정 — web_search tool 비활성.")

    if watercrawl_key:

        @tool
        async def fetch_url(url: str) -> dict:
            """웹 검색으로 찾은 특정 페이지의 본문을 읽는다(공고 원문·기사 전문 확인용)."""

            def _scrape() -> dict:
                # watercrawl-py 는 동기(requests) 클라이언트 — 스레드에서 생성·호출해 루프를 막지 않는다.
                from watercrawl import WaterCrawlAPIClient

                return WaterCrawlAPIClient(watercrawl_key).scrape_url(url)

            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(_scrape), timeout=_FETCH_TIMEOUT_S
                )
                return shape_page(url, result or {})
            except asyncio.TimeoutError:
                return {"error": "페이지 로드가 시간 초과되었습니다."}
            except Exception as e:  # 웹 실패는 대화를 끊지 않는다 — 관찰로 되돌린다.
                logger.warning(f"WaterCrawl 추출 예외: {e}")
                return {"error": "페이지 본문을 가져오지 못했습니다."}

        tools.append(fetch_url)
    else:
        logger.warning("WATERCRAWL_API_KEY 미설정 — fetch_url tool 비활성.")

    return tools
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd backend && python scripts/coach_web_tools_test.py`
Expected: PASS 16 / FAIL 0, exit 0

- [ ] **Step 6: 커밋**

```bash
git add backend/requirements.txt backend/core/config/settings.py backend/domain/ai_coach/spokes/agents/tools/web_tools.py backend/scripts/coach_web_tools_test.py
git commit -m "feat(coach): 웹 tool 2종 — Tavily 검색·WaterCrawl 본문 추출(키 없으면 제외·상한·출처 계약)"
```

---

### Task 2: 코치 통합 — tool 합성·라벨 병합·시스템 프롬프트 라우팅

**Files:**
- Modify: `backend/domain/ai_coach/hub/services/coach_service.py` (import, `_build_tools`, `_COACH_SYSTEM_PROMPT`)
- Modify: `backend/domain/ai_coach/spokes/infra/coach_graph.py` (라벨 병합 2줄)
- Test: `backend/scripts/coach_web_integration_test.py`

**Interfaces:**
- Consumes: Task 1의 `build_web_tools()`, `WEB_TOOL_LABELS`. 기존 `build_internal_tools(user_id)`, `TOOL_LABELS`(internal_tools).
- Produces: `CoachService._build_tools(user_id)` → 내부 6종 + 웹 0~2종 합성 리스트. coach_graph의 tool_call 라벨이 웹 tool도 한국어로 표시.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/scripts/coach_web_integration_test.py`:

```python
# 코치 웹 tool 통합 테스트(무DB·무네트워크) — tool 합성·라벨 병합·프롬프트 라우팅 지침

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from core.config.settings import get_settings
from domain.ai_coach.hub.services.coach_service import _COACH_SYSTEM_PROMPT, CoachService
from domain.ai_coach.spokes.agents.tools.internal_tools import TOOL_LABELS
from domain.ai_coach.spokes.agents.tools.web_tools import WEB_TOOL_LABELS

PASS = 0
FAIL = 0


def check(n: str, c: bool, e: str = "") -> None:
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"[PASS] {n}")
    else:
        FAIL += 1
        print(f"[FAIL] {n} {e}")


def run() -> int:
    svc = CoachService(None)  # DB 세션은 tool 구성에 불필요.
    tools = svc._build_tools("00000000-0000-0000-0000-000000000000")
    names = {t.name for t in tools}

    internal = {
        "get_pulse_trends", "get_gap_issues", "get_chance_matches",
        "get_sync_snapshot", "get_user_profile", "search_insights",
    }
    check("내부 6종 항상 포함", internal <= names, str(names))

    settings = get_settings()
    if getattr(settings, "tavily_api_key", None):
        check("Tavily 키 존재 → web_search 포함", "web_search" in names)
    else:
        check("Tavily 키 부재 → web_search 제외", "web_search" not in names)
    if getattr(settings, "watercrawl_api_key", None):
        check("WaterCrawl 키 존재 → fetch_url 포함", "fetch_url" in names)
    else:
        check("WaterCrawl 키 부재 → fetch_url 제외", "fetch_url" not in names)

    # 라벨 계약 — 이름 충돌 없음 + coach_graph 병합 매핑이 양쪽을 커버.
    check("라벨 이름 충돌 없음", set(TOOL_LABELS) & set(WEB_TOOL_LABELS) == set())
    from domain.ai_coach.spokes.infra import coach_graph

    merged = getattr(coach_graph, "_ALL_TOOL_LABELS")
    check("병합 라벨이 내부+웹 전수 커버", set(merged) == set(TOOL_LABELS) | set(WEB_TOOL_LABELS))

    # 시스템 프롬프트 — 웹 라우팅·출처 지침이 실제로 들어갔는지.
    check("프롬프트에 web_search 라우팅", "web_search" in _COACH_SYSTEM_PROMPT)
    check("프롬프트에 fetch_url 라우팅", "fetch_url" in _COACH_SYSTEM_PROMPT)
    check("프롬프트에 출처 URL 지침", "출처 URL" in _COACH_SYSTEM_PROMPT)

    print(f"\n합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python scripts/coach_web_integration_test.py`
Expected: FAIL 다수 (web_search 미포함·`_ALL_TOOL_LABELS` 부재·프롬프트 미갱신). `CoachService(None)` 생성 자체는 성공해야 한다(생성자는 settings만 읽음 — 실패 시 원인 확인).

- [ ] **Step 3: coach_service 수정**

`backend/domain/ai_coach/hub/services/coach_service.py`:

① import 추가 (기존 `build_internal_tools` import 옆):

```python
from domain.ai_coach.spokes.agents.tools.web_tools import build_web_tools
```

② `_build_tools` 교체:

```python
    def _build_tools(self, user_id: str) -> list:
        return build_internal_tools(user_id) + build_web_tools()
```

③ `_COACH_SYSTEM_PROMPT`의 원칙 2·4를 아래로 교체 (나머지 원칙은 그대로):

```python
2. tool 라우팅 — 트렌드는 get_pulse_trends, 미해결 기회는 get_gap_issues, 공고는 get_chance_matches,
   적합도는 get_sync_snapshot, 사용자 성향은 get_user_profile. 이 도구들로 답이 안 나오는 개방형 질문만
   search_insights(의미 검색)를 쓴다. 내부 데이터로 답할 수 없는 최신 정보(뉴스·시세·마감 임박 공고·
   기술 동향)는 web_search 로 검색하고, 찾은 페이지의 원문 확인이 필요하면 fetch_url 로 읽는다.
   내부 tool 로 충분한 질문에 웹을 쓰지 않는다.
```

```python
4. 인용 — 데이터를 근거로 쓸 때 어느 탭·데이터인지 자연스럽게 밝힌다(예: "Pulse 기준 AI 섹터가…").
   웹에서 가져온 정보는 반드시 출처 URL 을 함께 표기한다.
```

- [ ] **Step 4: coach_graph 라벨 병합**

`backend/domain/ai_coach/spokes/infra/coach_graph.py`:

① import 수정:

```python
from domain.ai_coach.spokes.agents.tools.internal_tools import TOOL_LABELS
from domain.ai_coach.spokes.agents.tools.web_tools import WEB_TOOL_LABELS

_ALL_TOOL_LABELS = {**TOOL_LABELS, **WEB_TOOL_LABELS}
```

② agent 노드의 tool_call 이벤트에서 `TOOL_LABELS.get(name, name)` → `_ALL_TOOL_LABELS.get(name, name)` 으로 교체 (1곳).

- [ ] **Step 5: 테스트 통과 + 회귀 확인**

Run: `cd backend && python scripts/coach_web_integration_test.py && python scripts/coach_graph_test.py && python scripts/coach_tools_test.py && python scripts/coach_web_tools_test.py`
Expected: 전부 PASS, exit 0 (통합 8 check + 기존 그래프 12 + 내부 tool 11 + 웹 tool 16)

- [ ] **Step 6: 커밋**

```bash
git add backend/domain/ai_coach/hub/services/coach_service.py backend/domain/ai_coach/spokes/infra/coach_graph.py backend/scripts/coach_web_integration_test.py
git commit -m "feat(coach): 웹 tool 코치 통합 — tool 합성·라벨 병합·웹 라우팅/출처 표기 프롬프트"
```

---

### Task 3: 라이브 verify — Tavily·WaterCrawl 실호출 + 코치 웹 1턴

**Files:**
- Create: `backend/scripts/coach_web_live_verify.py`

**Interfaces:**
- Consumes: 전체 스택. env `TAVILY_API_KEY`·`WATERCRAWL_API_KEY`·`ANTHROPIC_API_KEY`·DB(프로젝트 루트 `.env`, settings가 자동 로드). 실행 인자 `--user-id <uuid>`.
- 주의: **한 프로세스 asyncio.run() 1회** — tool 직접 호출과 코치 1턴을 같은 `main()` 안에서 수행. Anthropic·Tavily·WaterCrawl 실과금 — 실행 최대 2회(실패 시 원인 수정 후 1회 재시도), 반복 루프 금지.

- [ ] **Step 1: 스크립트 작성**

`backend/scripts/coach_web_live_verify.py`:

```python
# 코치 웹 tool 라이브 검증 — Tavily·WaterCrawl 실호출 + 코치 1턴에서 web_search 사용 확인

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

PASS = 0
FAIL = 0


def check(n: str, c: bool, e: str = "") -> None:
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"[PASS] {n}")
    else:
        FAIL += 1
        print(f"[FAIL] {n} {e}")


async def main(user_id: str) -> int:
    from core.database import AsyncSessionLocal
    from domain.ai_coach.hub.services.coach_service import CoachService
    from domain.ai_coach.spokes.agents.tools.web_tools import build_web_tools

    # 1) 웹 tool 2종 실호출
    tools = {t.name: t for t in build_web_tools()}
    check("웹 tool 2종 활성", set(tools) == {"web_search", "fetch_url"}, str(set(tools)))

    search = await tools["web_search"].ainvoke({"query": "2026년 AI 개발자 채용 시장 동향"})
    ok_search = isinstance(search, dict) and bool(search.get("results"))
    check("Tavily 검색 결과 수신", ok_search, str(search)[:200])
    first_url = search["results"][0]["url"] if ok_search else None
    if ok_search:
        print(f"    → {len(search['results'])}건, 첫 결과: {first_url}")
        check("결과 행마다 출처 url", all(r.get("url") for r in search["results"]))

    if first_url:
        page = await tools["fetch_url"].ainvoke({"url": first_url})
        ok_page = isinstance(page, dict) and len(page.get("content") or "") > 0
        check("WaterCrawl 본문 수신", ok_page, str(page)[:200])
        if ok_page:
            print(f"    → 본문 {len(page['content'])}자 (truncated={page.get('truncated')})")

    # 2) 코치 1턴 — 최신성 질문에 web_search 가 실제로 발동하는지
    async with AsyncSessionLocal() as db:
        sid = await CoachService(db).get_or_create_session(user_id)
    types, tool_names, text = [], [], ""
    async with AsyncSessionLocal() as db:
        svc = CoachService(db)
        async for sse in svc.stream_sse(
            user_id, sid, "최근 AI 개발자 채용 시장 뉴스를 웹에서 찾아서 요약해줘."
        ):
            obj = json.loads(sse.removeprefix("data: ").strip())
            types.append(obj.get("type"))
            if obj.get("type") == "tool_call":
                tool_names.append(obj.get("name"))
                print(f"    [tool_call] {obj.get('name')}")
            if obj.get("type") == "delta":
                text += obj.get("content") or ""
    check("스트림 done 종료", bool(types) and types[-1] == "done", str(types[-3:]))
    check("web_search 발동", "web_search" in tool_names, str(tool_names))
    check("텍스트 응답 수신", len(text) > 20, text[:120])
    check("에러 이벤트 없음", "error" not in types)
    print(f"\n--- 응답 미리보기 ---\n{text[:500]}\n")

    print(f"합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--user-id", required=True)
    a = p.parse_args()
    sys.exit(asyncio.run(main(a.user_id)))
```

- [ ] **Step 2: 라이브 실행**

사용자 UUID 조회(별도 프로세스라 asyncio.run 제약 무관):

```bash
cd backend && python -c "
import asyncio, sys, os
sys.path.insert(0, '.')
os.environ.setdefault('SCHEDULER_ENABLED', 'false')
from sqlalchemy import text
from core.database import AsyncSessionLocal
async def go():
    async with AsyncSessionLocal() as db:
        row = (await db.execute(text('SELECT user_id FROM user_self_model LIMIT 1'))).first()
        print(row[0])
asyncio.run(go())
"
```

Run: `cd backend && python scripts/coach_web_live_verify.py --user-id <위 UUID>`
Expected: PASS 9(±1 — first_url 유무에 따라) / FAIL 0. Tavily 결과 ≥1건, WaterCrawl 본문 >0자, 코치 턴에서 `web_search` tool_call 발동, `done` 종료. 코치가 web_search 를 안 불렀다면(내부 tool로만 답함) 질문 문구가 명시적으로 "웹에서"를 요구하는지 확인 — 그래도 미발동이면 시스템 프롬프트 라우팅 문구를 점검하고 1회만 재시도.

- [ ] **Step 3: 도커 컨테이너 반영**

사용자가 Docker로 백엔드를 구동 중이므로 러닝 컨테이너에 신규 의존성 설치(코드 자체는 마운트로 반영됨):

```bash
docker exec roadmap-api-1 pip install "watercrawl-py>=0.9.2" "httpx>=0.27.0"
docker restart roadmap-api-1
docker logs roadmap-api-1 --tail 5
```

Expected: 설치 성공 + 재시작 후 정상 부팅 로그. (requirements.txt에 이미 추가했으므로 다음 이미지 빌드부터는 자동 포함. 컨테이너 재생성 시엔 재설치 필요 — 보고서에 명기.)

- [ ] **Step 4: 커밋**

```bash
git add backend/scripts/coach_web_live_verify.py
git commit -m "test(coach): 웹 tool 라이브 verify — Tavily·WaterCrawl 실호출 + 코치 web_search 발동 확증"
```

---

## 완료 기준 (스펙 §8 C-2)

1. 최신 웹 정보가 출처 URL과 함께 코치 답변에 반영 (Task 3 라이브 verify PASS).
2. 키 미설정 환경에서 코치가 웹 tool 없이 정상 동작 (Task 1 팩토리 테스트).
3. 단위 스크립트 2종(coach_web_tools 16·coach_web_integration 8) PASS + 기존 코치 테스트(graph 12·tools 11·endpoint 4) 회귀 없음.

## 계획에서 의도적으로 뺀 것 (스코프 가드)

- 보조 검색 provider(Naver 재도입)·도메인 화이트리스트 → 필요 시 후속. `web_tools.py` 격리로 교체 지점은 확보됨.
- render_widget·deepagents(`launch_roadmap_generation`) → R-1/v2.
- 프론트 변경 없음 — tool_call 라벨은 이벤트의 `label` 필드를 그대로 표시하므로 백엔드 라벨 병합만으로 충분.
