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

        # 완전 빈 프로필 행(내용·성향·페르소나 없음)도 자격 미달 — 영구 재스캔 방지
        await s.execute(text(
            "INSERT INTO user_sync_profiles (user_id) VALUES (CAST(:u AS UUID))"), {"u": uid})
        await s.commit()
        rows = await repo.fetch_unembedded_users(model, 1000)
        check("빈 프로필 행 제외", uid not in {str(r.user_id) for r in rows})
        await s.execute(text(
            "DELETE FROM user_sync_profiles WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
        await s.commit()

        # 빈 자기모델(축 전부 null)은 임베딩할 것이 없어 자격 미달
        await s.execute(text(
            "INSERT INTO user_self_model (user_id, source, updated_at) "
            "VALUES (CAST(:u AS UUID), 'coach_extraction', now())"
        ), {"u": uid})
        await s.commit()
        rows = await repo.fetch_unembedded_users(model, 1000)
        check("빈 자기모델 제외", uid not in {str(r.user_id) for r in rows})

        # all-neutral 추출(6축 전부 중립·top_codes 빈·narrative 없음)도 임베딩할 것이 없어 자격 미달
        await s.execute(text(
            "UPDATE user_self_model SET riasec = CAST(:r AS JSONB), narrative_summary = NULL, "
            "updated_at = now() WHERE user_id = CAST(:u AS UUID)"
        ), {"u": uid, "r": (
            '{"scores": {"R": 50, "I": 50, "A": 50, "S": 50, "E": 50, "C": 50}, '
            '"weights": {"R": 0, "I": 0, "A": 0, "S": 0, "E": 0, "C": 0}, "top_codes": []}'
        )})
        await s.commit()
        rows = await repo.fetch_unembedded_users(model, 1000)
        check("all-neutral riasec 제외", uid not in {str(r.user_id) for r in rows})

        # top_codes 에 값이 생기면 후보 진입
        await s.execute(text(
            "UPDATE user_self_model SET riasec = CAST(:r AS JSONB), updated_at = now() "
            "WHERE user_id = CAST(:u AS UUID)"
        ), {"u": uid, "r": (
            '{"scores": {"R": 50, "I": 62, "A": 50, "S": 50, "E": 50, "C": 50}, '
            '"weights": {"R": 0, "I": 1, "A": 0, "S": 0, "E": 0, "C": 0}, "top_codes": ["I"]}'
        )})
        await s.commit()
        rows = await repo.fetch_unembedded_users(model, 1000)
        check("top_codes 진입 → 후보 진입", uid in {str(r.user_id) for r in rows})

        # 자기모델 축이 차면 후보 진입(프로필 없음)
        await s.execute(text(
            "UPDATE user_self_model SET riasec = CAST(:r AS JSONB), narrative_summary = '탐구 지향', "
            "updated_at = now() WHERE user_id = CAST(:u AS UUID)"
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

        # dislike 변경도 후보 트리거(설명 프롬프트 입력) — touch 로 워터마크 소진
        await repo.upsert_user_embedding(uid, [0.0] * 3072, "feedbeeffeedbeef", model)
        await s.commit()
        rows = await repo.fetch_unembedded_users(model, 1000)
        check("재임베딩 후 후보 제외", uid not in {str(r.user_id) for r in rows})
        await s.execute(text(
            "INSERT INTO user_self_model_evidence "
            "(user_id, dimension, polarity, content, confidence, is_sensitive, content_hash, source) "
            "VALUES (CAST(:u AS UUID), 'dislike', 'dislike', :c, 0.8, false, md5('dislike' || 'dislike' || :c2), "
            "'coach_extraction')"
        ), {"u": uid, "c": "새 야근 회피", "c2": "새 야근 회피"})
        await s.commit()
        rows = await repo.fetch_unembedded_users(model, 1000)
        check("dislike 추가 → 후보 재진입", uid in {str(r.user_id) for r in rows})
        n_touch = await repo.touch_user_embedding(uid)
        await s.commit()
        rows = await repo.fetch_unembedded_users(model, 1000)
        check("touch → 후보 종료", n_touch == 1 and uid not in {str(r.user_id) for r in rows})

        # Chance 매칭 사용자에도 코치-only 포함
        users = await ChanceRepository(s).fetch_users()
        check("chance 사용자 포함", uid in {str(r.user_id) for r in users})

        # 신호 소실 정리 경로 — 낡은 임베딩·매치 잔재 삭제(레포 수준)
        opp = (await s.execute(text(
            "SELECT id FROM chance_opportunities WHERE is_active = true ORDER BY id LIMIT 1"
        ))).scalar_one()
        await s.execute(text(
            "INSERT INTO user_chance_matches (user_id, opportunity_id, match_score, match_reason) "
            "VALUES (CAST(:u AS UUID), :o, 50, '정리 테스트') "
            "ON CONFLICT (user_id, opportunity_id) DO NOTHING"), {"u": uid, "o": opp})
        await s.commit()
        check("임베딩 삭제", await repo.delete_user_embedding(uid) == 1)
        check("매치 잔재 삭제", await repo.delete_user_matches(uid) == 1)
        await s.commit()

        await _cleanup(s, uid)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
