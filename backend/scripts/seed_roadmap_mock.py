# Roadmap 목업 시드 — 프론트 roadmapQuestMap.ts 모양 그대로 적재(멱등)
#
# 사용법:  python scripts/seed_roadmap_mock.py [user_id]
#   user_id 생략 시 users 테이블 첫 사용자에 시드한다.

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from core.database import AsyncSessionLocal  # noqa: E402

# ── 프론트 roadmapQuestMap.ts 미러 ──────────────────────────────────────────
SKILL_PILLARS = [
    {"id": "pillar-data", "label": "데이터 파이프라인", "blurb": "수집·정제·저장까지 신뢰 가능한 흐름 설계"},
    {"id": "pillar-domain", "label": "에너지·ESG 도메인", "blurb": "규제·지표·비즈니스 맥락을 언어로 전환"},
    {"id": "pillar-ai", "label": "AI 엔지니어링", "blurb": "모델보다 시스템 — 배포·관측·품질"},
]

BRIDGE_KEYWORDS = ["탄소회계", "CSRD", "FastAPI", "관측 가능성", "포트폴리오 스토리"]

# (quest_key, parent_key, title, purpose, difficulty, keywords, state, sort_order)
QUESTS = [
    ("root", None, "나의 시작점", "대시보드·상담에서 도출된 간극을 바탕으로, 지금 서 있는 위치입니다.",
     "입문", ["현재 위치", "간극 인식"], "start", 0),
    ("q-esg-map", "root", "ESG 데이터 지형도 그리기",
     "공개 데이터·지표 체계를 한 장의 지도로 정리해 도메인 언어를 몸에 익힙니다.",
     "입문", ["지표", "데이터 소스", "용어"], "done", 0),
    ("q-carbon-schema", "q-esg-map", "탄소 데이터 스키마 초안",
     "배출·감축 데이터가 어떤 엔티티로 흐르는지 스키마로 고정합니다.",
     "중급", ["스키마", "엔티티", "갭"], "active", 0),
    ("q-pipeline-mini", "q-esg-map", "데이터 파이프라인 미니 구현",
     "입력→검증→저장의 최소 파이프라인으로 ‘움직이는 증거’를 만듭니다.",
     "심화", ["FastAPI", "ETL", "품질"], "available", 1),
    ("q-observability", "q-pipeline-mini", "관측·재처리 루프",
     "실패를 전제로 로그·알림·재시도를 설계해 운영 감각을 쌓습니다.",
     "심화", ["로그", "SLA", "재처리"], "locked", 0),
    ("q-portfolio-case", "root", "도메인 문제 해결형 포트폴리오",
     "실제 결핍을 정의하고, 코드·문서·데모로 ‘해결의 궤적’을 남깁니다.",
     "중급", ["케이스", "README", "데모"], "available", 1),
    ("q-story-pitch", "q-portfolio-case", "면접 스토리라인 (3분 피치)",
     "문제-실행-성과를 한 호흡으로 말할 수 있게 구조화합니다.",
     "중급", ["STAR", "임팩트", "피치"], "locked", 0),
]

ARCHIVE_SEED = {
    "2026-04-22": {"completed": ["q-esg-map"], "note": "공공 API 2종 정리, 지표 용어집 초안 작성."},
    "2026-04-26": {"completed": ["q-esg-map"], "note": "ESG 리포트 샘플 읽고 질문 리스트업."},
}

MOCK_PERSONA = {
    "education": [{"school": "OO대학교", "major": "컴퓨터공학", "degree": "학사", "status": "재학"}],
    "experiences": [{"title": "교내 데이터 분석 동아리", "description": "공공데이터 시각화 프로젝트", "period": "2025"}],
    "skills": [
        {"name": "Python", "level": "중급"},
        {"name": "SQL", "level": "입문"},
        {"name": "데이터 시각화", "level": "입문"},
    ],
    "summary": "에너지·ESG 도메인 × AI 엔지니어링으로 진로를 탐색 중인 학생(목업).",
    "source": "mock",
}


async def _first_user_id(session) -> str | None:
    r = (await session.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).first()
    return str(r.id) if r else None


async def seed(user_id: str | None) -> int:
    async with AsyncSessionLocal() as session:
        if user_id is None:
            user_id = await _first_user_id(session)
            if user_id is None:
                print("[FAIL] users 테이블이 비어 있습니다. user_id 인자를 주세요.")
                return 1
        print(f"대상 user_id = {user_id}")

        # 1) 페르소나 upsert
        await session.execute(
            text(
                """
                INSERT INTO user_personas (user_id, education, experiences, skills, summary, source, updated_at)
                VALUES (CAST(:uid AS UUID), CAST(:edu AS JSONB), CAST(:exp AS JSONB),
                        CAST(:skl AS JSONB), :summary, :source, now())
                ON CONFLICT (user_id) DO UPDATE SET
                    education = EXCLUDED.education, experiences = EXCLUDED.experiences,
                    skills = EXCLUDED.skills, summary = EXCLUDED.summary,
                    source = EXCLUDED.source, updated_at = now()
                """
            ),
            {
                "uid": user_id,
                "edu": json.dumps(MOCK_PERSONA["education"]),
                "exp": json.dumps(MOCK_PERSONA["experiences"]),
                "skl": json.dumps(MOCK_PERSONA["skills"]),
                "summary": MOCK_PERSONA["summary"],
                "source": MOCK_PERSONA["source"],
            },
        )

        # 2) 로드맵 헤더 upsert (사용자당 1)
        rid = (
            await session.execute(
                text(
                    """
                    INSERT INTO user_roadmaps (user_id, title, summary, skill_pillars, bridge_keywords, status)
                    VALUES (CAST(:uid AS UUID), :title, :summary, CAST(:pillars AS JSONB),
                            CAST(:bridge AS JSONB), 'active')
                    ON CONFLICT (user_id) DO UPDATE SET
                        title = EXCLUDED.title, summary = EXCLUDED.summary,
                        skill_pillars = EXCLUDED.skill_pillars,
                        bridge_keywords = EXCLUDED.bridge_keywords, updated_at = now()
                    RETURNING id
                    """
                ),
                {
                    "uid": user_id,
                    "title": "에너지·ESG × AI 엔지니어링 로드맵",
                    "summary": "방향만 고정, 마감은 강제하지 않습니다.",
                    "pillars": json.dumps(SKILL_PILLARS),
                    "bridge": json.dumps(BRIDGE_KEYWORDS),
                },
            )
        ).scalar_one()

        # 3) 퀘스트 — 멱등 위해 해당 로드맵 퀘스트 전체 재생성
        await session.execute(
            text("DELETE FROM roadmap_quests WHERE roadmap_id = :rid"), {"rid": rid}
        )
        for key, parent, title, purpose, diff, kws, state, order in QUESTS:
            await session.execute(
                text(
                    """
                    INSERT INTO roadmap_quests
                        (roadmap_id, quest_key, parent_key, title, purpose, difficulty,
                         keywords, state, sort_order)
                    VALUES (:rid, :key, :parent, :title, :purpose, :diff,
                            CAST(:kws AS JSONB), :state, :order)
                    """
                ),
                {
                    "rid": rid, "key": key, "parent": parent, "title": title,
                    "purpose": purpose, "diff": diff, "kws": json.dumps(kws),
                    "state": state, "order": order,
                },
            )

        # 4) 아카이브 일별 로그 upsert
        for log_date, payload in ARCHIVE_SEED.items():
            await session.execute(
                text(
                    """
                    INSERT INTO growth_logs (user_id, log_date, note, completed_quest_keys, created_at, updated_at)
                    VALUES (CAST(:uid AS UUID), :d, :note, CAST(:completed AS JSONB), now(), now())
                    ON CONFLICT (user_id, log_date) DO UPDATE SET
                        note = EXCLUDED.note,
                        completed_quest_keys = EXCLUDED.completed_quest_keys, updated_at = now()
                    """
                ),
                {
                    "uid": user_id, "d": date.fromisoformat(log_date), "note": payload["note"],
                    "completed": json.dumps(payload["completed"]),
                },
            )

        await session.commit()
        print(f"[OK] roadmap_id={rid}, 퀘스트 {len(QUESTS)}개, 아카이브 {len(ARCHIVE_SEED)}일, 페르소나 1건 시드 완료.")
        return 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    raise SystemExit(asyncio.run(seed(arg)))
