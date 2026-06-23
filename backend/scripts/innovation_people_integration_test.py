"""혁신·사람 수요 수집처를 제한된 요청 수로 실제 연결 검증한다."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv

for env_path in (backend_dir / ".env", backend_dir.parent / ".env"):
    if env_path.exists():
        load_dotenv(env_path)
        break

from domain.master.hub.services.collectors.innovation.arxiv.arxiv_papers_collector import (  # noqa: E402
    ArxivPapersCollector,
)
from domain.master.hub.services.collectors.innovation.github.github_trending_collector import (  # noqa: E402
    GithubTrendingCollector,
)
from domain.master.hub.services.collectors.people.hrdnet.hrdnet_training_collector import (  # noqa: E402
    HrdnetTrainingCollector,
)
from domain.master.hub.services.collectors.people.worknet.worknet_job_info_collector import (  # noqa: E402
    WorknetJobInfoCollector,
)
from domain.master.hub.services.collectors.people.careernet.careernet_collector import (  # noqa: E402
    CareernetCollector,
)

_pass = 0
_fail = 0
_skip = 0


def report(name: str, ok: bool, detail: object) -> None:
    global _pass, _fail
    if ok:
        _pass += 1
        print(f"[OK] {name} {detail}")
    else:
        _fail += 1
        print(f"[FAIL] {name} {detail}")


def skip(name: str, reason: str) -> None:
    global _skip
    _skip += 1
    print(f"[SKIP] {name} {reason}")


async def main() -> int:
    arxiv_rows, arxiv_stats = await ArxivPapersCollector().collect(
        days_back=30,
        max_results=3,
        categories=[("AI_CS", "cs.AI", "AI")],
        sleep_seconds=0,
    )
    report("arXiv", int(arxiv_stats["categories_ok"]) == 1, arxiv_stats)
    report("arXiv DTO", bool(arxiv_rows), f"rows={len(arxiv_rows)}")

    github_rows, github_stats = await GithubTrendingCollector(
        os.getenv("GITHUB_TOKEN")
    ).collect(
        days_back=30,
        topic_groups=[("AI_ML", ["machine-learning"])],
        per_page=3,
        sleep_seconds=0,
    )
    report("GitHub", int(github_stats["topics_ok"]) >= 1, github_stats)
    report("GitHub response parse", isinstance(github_rows, list), f"rows={len(github_rows)}")

    worknet_key = os.getenv("WORKNET_API_KEY")
    if worknet_key:
        rows, stats = await WorknetJobInfoCollector(worknet_key).collect()
        report("Work24 job info", stats["requests_ok"] == 1, stats)
        report("WorkNet DTO", bool(rows), f"rows={len(rows)}")
    else:
        skip("WorkNet", "WORKNET_API_KEY 없음")

    hrdnet_key = os.getenv("HRDNET_API_KEY")
    if hrdnet_key:
        rows, stats = await HrdnetTrainingCollector(hrdnet_key).collect(
            sectors=[("ICT_SW", "20")],
            sleep_seconds=0,
        )
        report("HRD-Net", stats["sectors_ok"] == 1, stats)
        report("HRD-Net DTO", bool(rows), f"rows={len(rows)}")
    else:
        skip("HRD-Net", "HRDNET_API_KEY 없음")

    careernet_key = os.getenv("CAREERNET_API_KEY")
    if careernet_key:
        rows, stats = await CareernetCollector(careernet_key).collect(
            include_major=False,
            per_page=10,
            max_pages=1,
            sleep_seconds=0,
        )
        report("CareerNet 직업정보", stats["specs_ok"] >= 1, stats)
        report("CareerNet DTO", bool(rows), f"rows={len(rows)}")
        if rows:
            # prospect(일자리전망)는 API 미제공 — possibility(발전가능성) 확인
            possibility_row = next(
                (r for r in rows if (r.raw_metadata or {}).get("possibility")), None
            )
            report(
                "CareerNet possibility(발전가능성) 필드",
                possibility_row is not None,
                (possibility_row.raw_metadata or {}).get("possibility") if possibility_row else "없음",
            )
    else:
        skip("CareerNet", "CAREERNET_API_KEY 없음")

    print(f"PASS={_pass} FAIL={_fail} SKIP={_skip}")
    return 1 if _fail else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
