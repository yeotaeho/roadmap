# People·Discourse·Opportunity·Company 신규 수집기 통합 테스트 (키/네트워크 게이트)

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config.settings import get_settings  # noqa: E402
from core.database import get_db  # noqa: E402
from domain.master.hub.services.bronze_company_ingest_service import (  # noqa: E402
    BronzeCompanyIngestService,
)
from domain.master.hub.services.bronze_discourse_ingest_service import (  # noqa: E402
    BronzeDiscourseIngestService,
)
from domain.master.hub.services.bronze_opportunity_ingest_service import (  # noqa: E402
    BronzeOpportunityIngestService,
)
from domain.master.hub.services.bronze_people_ingest_service import (  # noqa: E402
    BronzePeopleIngestService,
)


async def _run() -> None:
    settings = get_settings()

    async for db in get_db():
        # 1) Discourse 뉴스 RSS — 키 불필요, 항상 실행 (네트워크 필요)
        print("\n[1] Discourse 뉴스 RSS (키 불필요)")
        try:
            res = await BronzeDiscourseIngestService(db).ingest_news_rss(max_items_per_feed=10)
            print("   ->", res)
        except Exception as e:
            print(f"   [ERROR] {e}")

        # 2) People 고용24 채용
        print("\n[2] People 고용24 채용")
        if not settings.goyong24_recruit_api_key:
            print("   [SKIP] GOYONG24_RECRUIT_API_KEY 미설정")
        else:
            try:
                svc = BronzePeopleIngestService(
                    db, goyong24_recruit_api_key=settings.goyong24_recruit_api_key
                )
                print("   ->", await svc.ingest_goyong24_recruit(max_pages=2))
            except Exception as e:
                print(f"   [ERROR] {e}")

        # 3) People 사람인
        print("\n[3] People 사람인 채용")
        if not settings.saramin_access_key:
            print("   [SKIP] SARAMIN_ACCESS_KEY 미설정")
        else:
            try:
                svc = BronzePeopleIngestService(db, saramin_api_key=settings.saramin_access_key)
                print("   ->", await svc.ingest_saramin_recruit())
            except Exception as e:
                print(f"   [ERROR] {e}")

        # 4) Opportunity K-Startup
        print("\n[4] Opportunity K-Startup")
        if not settings.kstartup_service_key:
            print("   [SKIP] KSTARTUP_SERVICE_KEY 미설정")
        else:
            try:
                svc = BronzeOpportunityIngestService(
                    db, kstartup_service_key=settings.kstartup_service_key
                )
                print("   ->", await svc.ingest_kstartup(max_items=20))
            except Exception as e:
                print(f"   [ERROR] {e}")

        # 5) Opportunity 나라장터
        print("\n[5] Opportunity 나라장터")
        if not settings.narajangteo_service_key:
            print("   [SKIP] NARAJANGTEO_SERVICE_KEY 미설정")
        else:
            try:
                svc = BronzeOpportunityIngestService(
                    db, narajangteo_service_key=settings.narajangteo_service_key
                )
                print("   ->", await svc.ingest_narajangteo(max_items=20))
            except Exception as e:
                print(f"   [ERROR] {e}")

        # 6) Company 벤처기업명단
        print("\n[6] Company 벤처기업명단")
        if not settings.venture_list_service_key:
            print("   [SKIP] VENTURE_LIST_SERVICE_KEY 미설정")
        else:
            try:
                svc = BronzeCompanyIngestService(
                    db, venture_list_service_key=settings.venture_list_service_key
                )
                # resource(uddi) 는 data.go.kr 상세에서 확인 후 VENTURE_LIST_RESOURCE 로 주입.
                print(
                    "   ->",
                    await svc.ingest_venture_list(
                        max_items=50, resource=os.getenv("VENTURE_LIST_RESOURCE")
                    ),
                )
            except Exception as e:
                print(f"   [ERROR] {e}")
        break


if __name__ == "__main__":
    asyncio.run(_run())
