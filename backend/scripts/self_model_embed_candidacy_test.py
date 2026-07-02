# 재임베딩 후보 — 코치-only 사용자 포함·자기모델 갱신 트리거·긍정 근거 필터 (Neon 통합).

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text

from core.config.settings import get_settings
from core.database import AsyncSessionLocal
from domain.market_insight.hub.repositories.chance_repository import ChanceRepository
from domain.market_insight.hub.repositories.embed_repository import EmbedRepository

PASS = 0
FAIL = 0
TEST_EMAIL = "sp3-candidacy-test@example.local"


def check(n: str, c: bool, e: str = "") -> None:
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"[PASS] {n}")
    else:
        FAIL += 1
        print(f"[FAIL] {n} {e}")


async def _cleanup(s, uid: str | None) -> None:
    if uid is None:
        r = (await s.execute(text("SELECT id FROM users WHERE email = :e"), {"e": TEST_EMAIL})).first()
        if r is None:
            return
        uid = str(r.id)
    await s.execute(text("DELETE FROM user_self_model_evidence WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.execute(text("DELETE FROM user_self_model WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.execute(text("DELETE FROM user_embeddings WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.execute(text("DELETE FROM users WHERE id = CAST(:u AS UUID)"), {"u": uid})
    await s.commit()


async def run() -> int:
    model = get_settings().llm_embed_model
    async with AsyncSessionLocal() as s:
        await _cleanup(s, None)
        # 프로필 없는 코치-only 사용자 생성
        uid = str((await s.execute(text(
            "INSERT INTO users (email, nickname) VALUES (:e, 'SP3테스트') RETURNING id"
        ), {"e": TEST_EMAIL})).scalar_one())
        await s.commit()

        repo = EmbedRepository(s)

        # 자기모델도 근거도 없으면 후보 아님
        rows = await repo.fetch_unembedded_users(model, 1000)
        check("신호 없는 사용자 제외", uid not in {str(r.user_id) for r in rows})

        # 자기모델만 생기면 후보 진입(프로필 없음)
        await s.execute(text(
            "INSERT INTO user_self_model (user_id, riasec, narrative_summary, source, updated_at) "
            "VALUES (CAST(:u AS UUID), CAST(:r AS JSONB), '탐구 지향', 'coach_extraction', now())"
        ), {"u": uid, "r": '{"top_codes": ["I"]}'})
        await s.commit()
        rows = await repo.fetch_unembedded_users(model, 1000)
        mine = [r for r in rows if str(r.user_id) == uid]
        check("코치-only 후보 진입", len(mine) == 1, str(len(mine)))
        check("riasec 셀렉트 포함", mine and mine[0].riasec == {"top_codes": ["I"]}, str(mine and mine[0].riasec))
        check("narrative 셀렉트 포함", mine and mine[0].narrative_summary == "탐구 지향")

        # 임베딩 기록 후 후보에서 빠짐 → 자기모델 갱신 시 재진입
        await repo.upsert_user_embedding(uid, [0.0] * 3072, "deadbeefdeadbeef", model)
        await s.commit()
        rows = await repo.fetch_unembedded_users(model, 1000)
        check("임베딩 후 후보 제외", uid not in {str(r.user_id) for r in rows})
        await s.execute(text(
            "UPDATE user_self_model SET narrative_summary = '성장 지향', updated_at = now() "
            "WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
        await s.commit()
        rows = await repo.fetch_unembedded_users(model, 1000)
        check("자기모델 갱신 → 재진입", uid in {str(r.user_id) for r in rows})

        # 긍정 근거 필터 — dislike·constraint·민감 제외
        for dim, pol, content, sens in [
            ("like", "like", "발표를 좋아함", False),
            ("value", None, "성장을 중시함", False),
            ("dislike", "dislike", "야근을 싫어함", False),
            ("constraint", None, "장거리 통근 불가", False),
            ("like", "like", "민감한 내용", True),
        ]:
            # 근거: :d/:p/:c 를 컬럼 값과 md5() 인자에 이중 사용하면 asyncpg 가 매개변수 타입을
            # 일관되게 추론하지 못해 AmbiguousParameterError 가 나므로, 용도별로 별도 바인드한다.
            await s.execute(text(
                "INSERT INTO user_self_model_evidence "
                "(user_id, dimension, polarity, content, confidence, is_sensitive, content_hash, source) "
                "VALUES (CAST(:u AS UUID), :d, :p, :c, 0.9, :s, md5(:d2 || COALESCE(:p2,'') || :c2), "
                "'coach_extraction')"
            ), {
                "u": uid, "d": dim, "p": pol, "c": content, "s": sens,
                "d2": dim, "p2": pol, "c2": content,
            })
        await s.commit()
        ev = await repo.fetch_positive_evidence([uid])
        contents = ev.get(uid, [])
        check("긍정 근거 포함", "발표를 좋아함" in contents and "성장을 중시함" in contents, str(contents))
        check("dislike 제외", "야근을 싫어함" not in contents)
        check("constraint 제외", "장거리 통근 불가" not in contents)
        check("민감 제외", "민감한 내용" not in contents)
        check("빈 입력 빈 dict", await repo.fetch_positive_evidence([]) == {})

        # Chance 매칭 사용자에도 코치-only 포함
        users = await ChanceRepository(s).fetch_users()
        check("chance 사용자 포함", uid in {str(r.user_id) for r in users})

        await _cleanup(s, uid)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
