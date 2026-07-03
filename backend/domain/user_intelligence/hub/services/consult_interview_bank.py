# 상담 인터뷰 문항 은행 — RIASEC 6축·Big Five 5축의 대화형 질문 각도(정식 검사 문항 풀 근거).

from __future__ import annotations

# 실제 검사(워크넷 직업선호도·O*NET Interest Profiler)가 축별 독립 문항 풀을 쓰는 것을 근거로,
# 각 축을 자연스러운 대화 질문 각도(probe)로 변환한다. LLM 은 probe 를 그대로 읽지 않고 참고 각도로 쓴다.
INTERVIEW_AXES: dict[str, dict] = {
    "R": {
        "label": "현실형(손·도구·몸)",
        "probes": [
            "손으로 만들거나 고치거나 몸을 쓰는 활동을 즐기는지, 최근 그런 경험이 있었는지",
            "기계·도구·장비를 다루는 일에 흥미를 느끼는지",
        ],
    },
    "I": {
        "label": "탐구형(원리·분석)",
        "probes": [
            "어떤 주제를 원리까지 파고들었던 경험이 있는지, 무엇이 그렇게 만들었는지",
            "문제를 분석하거나 실험해 보는 활동을 즐기는지",
        ],
    },
    "A": {
        "label": "예술형(창작·표현)",
        "probes": [
            "무언가를 만들거나 표현하는 활동(글·그림·영상·스타일링 등)에 끌리는지",
            "정해진 틀보다 자유로운 방식이 좋은 순간이 언제인지",
        ],
    },
    "S": {
        "label": "사회형(돕기·소통)",
        "probes": [
            "다른 사람을 돕거나 가르쳐 준 경험에서 어떤 기분을 느꼈는지",
            "사람들과 소통하며 무언가를 함께 할 때와 혼자 할 때 중 무엇이 좋은지",
        ],
    },
    "E": {
        "label": "진취형(설득·주도)",
        "probes": [
            "모임이나 프로젝트에서 방향을 정하고 이끌어 본 경험이 있는지",
            "누군가를 설득하거나 목표를 밀어붙이는 상황을 즐기는지",
        ],
    },
    "C": {
        "label": "관습형(정리·체계)",
        "probes": [
            "일정·자료·물건을 정리하고 체계를 잡는 걸 좋아하는지",
            "꼼꼼하게 규칙대로 처리해야 하는 일이 편한지 답답한지",
        ],
    },
    "BF_O": {
        "label": "개방성(새로움·호기심)",
        "probes": [
            "새로운 것(장소·음식·분야)을 시도하는 편인지, 익숙한 게 좋은지",
            "요즘 호기심이 생긴 낯선 주제가 있는지",
        ],
    },
    "BF_C": {
        "label": "성실성(계획·꾸준함)",
        "probes": [
            "일을 계획 세워 진행하는 편인지, 닥쳐서 몰아치는 편인지",
            "꾸준히 이어 온 습관이나 루틴이 있는지",
        ],
    },
    "BF_E": {
        "label": "외향성(에너지 방향)",
        "probes": [
            "사람들과 어울린 뒤 충전되는지, 혼자 있는 시간이 필요해지는지",
            "여럿이 하는 활동과 혼자 몰입하는 활동 중 무엇이 더 자연스러운지",
        ],
    },
    "BF_A": {
        "label": "우호성(협력·배려)",
        "probes": [
            "의견이 부딪힐 때 맞춰 주는 편인지, 자기 생각을 밀고 나가는 편인지",
            "팀에서 갈등이 생기면 주로 어떤 역할을 하는지",
        ],
    },
    "BF_N": {
        "label": "정서반응(스트레스 대처)",
        "probes": [
            "스트레스를 받으면 주로 어떻게 풀고, 회복이 빠른 편인지",
            "중요한 일 전에 긴장을 많이 하는 편인지 담담한 편인지",
        ],
    },
}

ALL_AXES: tuple[str, ...] = tuple(INTERVIEW_AXES)


def first_uncovered(coverage: dict) -> str | None:
    """커버리지에서 아직 신호가 없는 첫 축 코드. 전부 커버면 None."""
    for code in INTERVIEW_AXES:
        if not coverage.get(code):
            return code
    return None


def axis_label(code: str) -> str:
    ax = INTERVIEW_AXES.get(code)
    return ax["label"] if ax else code


def probe_hint(code: str) -> str | None:
    ax = INTERVIEW_AXES.get(code)
    return ax["probes"][0] if ax and ax.get("probes") else None
