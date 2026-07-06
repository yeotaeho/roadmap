from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
import asyncio

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from core.database import Base
from domain.auth.models.bases.user import User  # Import all models here
from domain.auth.models.bases.user_sync_profile import UserSyncProfile
from domain.auth.models.bases.user_profile import UserProfile  # 기본정보
from domain.master.models.bases.raw_economic_data import RawEconomicData  # Bronze
from domain.master.models.bases.raw_market_timeseries import RawMarketTimeseries  # Bronze
from domain.master.models.bases.raw_opportunity_data import RawOpportunityData  # Bronze
from domain.master.models.bases.raw_innovation_data import RawInnovationData  # Bronze
from domain.master.models.bases.raw_people_data import RawPeopleData  # Bronze
from domain.master.models.bases.raw_discourse_data import RawDiscourseData  # Bronze
from domain.master.models.bases.verified_company_master import VerifiedCompanyMaster  # Bronze
from domain.market_insight.models.bases.refined_pulse_metric_silver import (  # Silver
    RefinedPulseMetricSilver,
)
from domain.market_insight.models.bases.pulse_metrics_log import PulseMetricsLog  # Gold
from domain.market_insight.models.bases.refined_text_sector_class import (  # Silver
    RefinedTextSectorClass,
)
from domain.market_insight.models.bases.refined_innovation_signal import (  # Silver
    RefinedInnovationSignal,
)
from domain.market_insight.models.bases.refined_signal_sources import (  # Silver 리니지
    RefinedSignalSources,
)
from domain.market_insight.models.bases.refined_gap_insights import (  # Silver
    RefinedGapInsights,
)
from domain.market_insight.models.bases.gap_issues import GapIssues  # Gold
from domain.market_insight.models.bases.issue_evidences import IssueEvidences  # Gold
from domain.market_insight.models.bases.refined_chance_insights import (  # Silver
    RefinedChanceInsights,
)
from domain.market_insight.models.bases.chance_opportunities import (  # Gold
    ChanceOpportunities,
)
from domain.market_insight.models.bases.user_chance_matches import (  # Gold
    UserChanceMatches,
)
from domain.market_insight.models.bases.document_embeddings import (  # Silver/RAG
    DocumentEmbeddings,
)
from domain.market_insight.models.bases.user_embeddings import UserEmbeddings  # Silver
from domain.market_insight.models.bases.refined_sync_inputs import (  # Silver
    RefinedSyncInputs,
)
from domain.market_insight.models.bases.sync_scores_daily import SyncScoresDaily  # Gold
from domain.market_insight.models.bases.economic_briefings import EconomicBriefing  # Gold
from domain.market_insight.models.bases.refined_causal_chain_insights import (  # Silver
    RefinedCausalChainInsights,
)
from domain.market_insight.models.bases.causal_chains import CausalChains  # Gold
from domain.market_insight.models.bases.refined_investment_flows import (  # Silver
    RefinedInvestmentFlows,
)
from domain.user_intelligence.models.bases.user_persona import UserPersona  # Persona
from domain.user_intelligence.models.bases.user_preference import UserPreference  # 성향·선호
from domain.user_intelligence.models.bases.user_self_model import UserSelfModel  # 자기모델
from domain.user_intelligence.models.bases.user_self_model_evidence import (  # 자기모델 근거
    UserSelfModelEvidence,
)
from domain.user_intelligence.models.bases.consult_session import ConsultSession  # 상담 세션
from domain.user_intelligence.models.bases.consult_message import ConsultMessage  # 상담 메시지
from domain.hrowth_journey.models.bases.user_roadmap import UserRoadmap  # Roadmap
from domain.hrowth_journey.models.bases.roadmap_quest import RoadmapQuest  # Roadmap
from domain.hrowth_journey.models.bases.growth_log import GrowthLog  # Roadmap
from domain.hrowth_journey.models.bases.planner_sprint import PlannerSprint  # Roadmap 플래너
from domain.hrowth_journey.models.bases.planner_task import PlannerTask  # Roadmap 플래너
from domain.hrowth_journey.models.bases.roadmap_note import RoadmapNote  # Roadmap 노트
from domain.market_insight.models.bases.sector_master import Sector, SubSector  # Sector master
from domain.task.models.bases.task import Task  # Task
from domain.master.models.bases.ncs_competency_master import NcsCompetencyMaster  # NCS 마스터
from domain.market_insight.models.bases.refined_market_forecast_silver import (  # Silver
    RefinedMarketForecastSilver,
)
from domain.market_insight.models.bases.market_forecast_log import (  # Gold
    MarketForecastLog,
)
from domain.ai_coach.models.bases.coach_session import CoachSession  # 코치 세션
from domain.ai_coach.models.bases.coach_message import CoachMessage  # 코치 메시지

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url():
    """Get database URL from settings"""
    from core.config.settings import settings
    return settings.database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    database_url = get_url()
    
    # SSL 설정 추가 (database.py와 동일한 설정)
    connect_args = {}
    
    # Neon PostgreSQL의 경우 기본적으로 SSL 필요
    if 'neon.tech' in database_url or 'neon' in database_url.lower():
        connect_args['ssl'] = True
    else:
        # 일반 PostgreSQL의 경우도 SSL 활성화 (보안을 위해)
        connect_args['ssl'] = True
    
    # InvalidCachedStatementError 방지: prepared statement 캐시 비활성화
    connect_args['server_settings'] = {
        'statement_cache_size': '0'
    }
    
    # create_async_engine을 직접 사용하여 connect_args 전달
    connectable = create_async_engine(
        database_url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

