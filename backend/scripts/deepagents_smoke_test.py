# deepagents 0.6.12 설치·호환 스모크 — 임포트 경로·시그니처·무네트워크 빌드 확인
from __future__ import annotations

import inspect
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


def main() -> int:
    import importlib.metadata as md

    print("deepagents:", md.version("deepagents"))
    print("langchain-core:", md.version("langchain-core"))
    print("langchain:", md.version("langchain"))
    print("langchain-anthropic:", md.version("langchain-anthropic"))
    try:
        print("langgraph:", md.version("langgraph"))
    except md.PackageNotFoundError:
        print("langgraph: (미설치 — transitive 아님)")

    from deepagents import create_deep_agent

    sig = inspect.signature(create_deep_agent)
    for p in ("model", "tools", "system_prompt", "subagents", "backend", "checkpointer", "response_format"):
        check(f"create_deep_agent 파라미터 {p}", p in sig.parameters)

    # StateBackend 임포트 경로 확정(이후 태스크가 사용) — 실패 시 대체 경로 출력.
    try:
        from deepagents.backends import StateBackend  # noqa: F401

        check("StateBackend 임포트(deepagents.backends)", True)
    except ImportError:
        import deepagents as da

        print("deepagents 공개 심볼:", [n for n in dir(da) if "ackend" in n])
        check("StateBackend 임포트(deepagents.backends)", False)

    # 무네트워크 빌드 — 더미 키 ChatAnthropic 인스턴스 + 서브에이전트 1종.
    from langchain_anthropic import ChatAnthropic
    from langchain_core.tools import tool

    @tool
    def _noop(q: str) -> str:
        """스모크용 무동작 tool."""
        return q

    model = ChatAnthropic(
        model="claude-sonnet-5", api_key="sk-dummy", max_tokens=1024,
        thinking={"type": "disabled"},
    )
    agent = create_deep_agent(
        model=model,
        system_prompt="스모크 오케스트레이터.",
        subagents=[{
            "name": "smoke_sub", "description": "스모크 서브에이전트.",
            "system_prompt": "스모크.", "tools": [_noop], "model": model,
        }],
    )
    check("컴파일 그래프 astream 지원", hasattr(agent, "astream"))
    check("컴파일 그래프 ainvoke 지원", hasattr(agent, "ainvoke"))

    print(f"\nRESULT: PASS {_pass} / FAIL {_fail}")
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
