# 로드맵 딥 에이전트 빌더 — deepagents 서브에이전트 3종·모델 믹스·산출 파싱(3단 폴백)
from __future__ import annotations

import json
import logging
import re

from langchain_core.tools import StructuredTool

from core.llm.client import _parse_roadmap

logger = logging.getLogger(__name__)

RESULT_FILE_CANDIDATES = ("/roadmap_result.json", "roadmap_result.json")


def _limited(tools: list, limit: int) -> list:
    """웹 tool 공유 호출 카운터 래핑 — 상한 초과 시 error dict 반환(대화 비파괴)."""
    counter = {"n": 0}
    wrapped = []
    for t in tools:
        async def _run(_t=t, **kwargs):
            if counter["n"] >= limit:
                return {"error": "웹 호출 한도를 초과했습니다. 지금까지 수집한 정보로 진행하세요."}
            counter["n"] += 1
            return await _t.ainvoke(kwargs)

        wrapped.append(
            StructuredTool(
                name=t.name, description=t.description,
                args_schema=t.args_schema, coroutine=_run,
            )
        )
    return wrapped


def _chat_model(model_name: str, api_key: str, max_tokens: int):
    from langchain_anthropic import ChatAnthropic

    # Sonnet 5 는 thinking 미지정 시 adaptive 활성 → tool 라운드 재전송 400. 반드시 비활성 명시.
    return ChatAnthropic(
        model=model_name, api_key=api_key, max_tokens=max_tokens,
        thinking={"type": "disabled"},
    )


def build_subagent_specs(user_id: str, settings=None) -> list[dict]:
    """서브에이전트 3종 선언 — tools 명시 리스트(task 미포함=재귀 스폰 차단)."""
    from core.config.settings import get_settings
    from core.llm.provider import resolve_coach_llm
    from domain.ai_coach.spokes.agents.tools.internal_tools import build_internal_tools
    from domain.ai_coach.spokes.agents.tools.web_tools import build_web_tools

    from domain.hrowth_journey.spokes.agents.roadmap_agent_prompts import (
        MARKET_ANALYST_PROMPT,
        OPPORTUNITY_SCOUT_PROMPT,
        QUEST_DESIGNER_PROMPT,
    )

    settings = settings or get_settings()
    api_key, sonnet_model = resolve_coach_llm(settings)
    cheap = _chat_model(settings.roadmap_agent_cheap_model, api_key, 4096)
    sonnet = _chat_model(sonnet_model, api_key, 8192)

    internal = {t.name: t for t in build_internal_tools(user_id)}
    web = _limited(build_web_tools(settings), settings.roadmap_agent_web_call_limit)

    return [
        {
            "name": "market_analyst",
            "description": "시장 트렌드·미해결 기회·사용자 적합도를 종합해 유망 방향 후보를 분석한다.",
            "system_prompt": MARKET_ANALYST_PROMPT,
            "tools": [internal["get_pulse_trends"], internal["get_gap_issues"], internal["get_sync_snapshot"]],
            "model": cheap,
        },
        {
            "name": "opportunity_scout",
            "description": "맞춤 공고와 웹 최신 동향으로 실행 가능한 기회·요건을 수집한다.",
            "system_prompt": OPPORTUNITY_SCOUT_PROMPT,
            "tools": [internal["get_chance_matches"], *web],
            "model": cheap,
        },
        {
            "name": "quest_designer",
            "description": "사용자 자기모델과 시장 분석을 잇는 퀘스트 트리 초안을 설계한다.",
            "system_prompt": QUEST_DESIGNER_PROMPT,
            "tools": [internal["get_user_profile"]],
            "model": sonnet,
        },
    ]


def build_roadmap_deep_agent(user_id: str, settings=None):
    """딥 에이전트 컴파일 — 오케스트레이터 Sonnet, 기본 StateBackend(스레드 스코프 가상 FS)."""
    from deepagents import create_deep_agent

    from core.config.settings import get_settings
    from core.llm.provider import resolve_coach_llm
    from domain.hrowth_journey.spokes.agents.roadmap_agent_prompts import ORCHESTRATOR_PROMPT

    settings = settings or get_settings()
    api_key, sonnet_model = resolve_coach_llm(settings)
    return create_deep_agent(
        model=_chat_model(sonnet_model, api_key, 8192),
        system_prompt=ORCHESTRATOR_PROMPT,
        subagents=build_subagent_specs(user_id, settings),
    )


def _extract_json_block(content) -> dict | None:
    """AIMessage content(문자열/블록 리스트)에서 마지막 JSON 오브젝트 추출."""
    if isinstance(content, list):
        content = "".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
    if not isinstance(content, str):
        return None
    matches = re.findall(r"\{[\s\S]*\}", content)
    for raw in reversed(matches):
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def parse_agent_output(final_state: dict) -> tuple[dict, list]:
    """최종 state → (검증된 roadmap dict 또는 {}, raw tasks). 1) 결과 파일 2) 마지막 AIMessage JSON."""
    obj: dict | None = None
    files = final_state.get("files") or {}
    for key in RESULT_FILE_CANDIDATES:
        raw = files.get(key)
        if raw is None:
            continue
        content = raw.get("content") if isinstance(raw, dict) else raw
        if isinstance(content, list):  # 일부 버전은 라인 리스트로 저장.
            content = "\n".join(str(x) for x in content)
        try:
            obj = json.loads(content)
            break
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"결과 파일 파싱 실패({key}) — 메시지 폴백 시도")
    if obj is None:
        for msg in reversed(final_state.get("messages") or []):
            if getattr(msg, "type", None) == "ai":
                obj = _extract_json_block(getattr(msg, "content", None))
                if obj:
                    break
    if not isinstance(obj, dict):
        return {}, []
    raw_tasks = obj.get("tasks") if isinstance(obj.get("tasks"), list) else []
    roadmap = _parse_roadmap(json.dumps(obj, ensure_ascii=False))
    return roadmap, raw_tasks
