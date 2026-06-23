"""섹터 마스터·소스 매핑과 교차융합형 혁신 Silver 스키마를 생성한다.

ERD 결함 수정:
  A. sectors/sub_sectors 마스터 부재 → 생성 + 시드, 5개 소스 분류값을 섹터로
     통합하는 sector_source_map 추가
  B. Silver 리니지 1:1 → refined_signal_sources(N:M 증거 매핑)로 한 신호가 다수
     원천을 가리키도록 분리
  C. Silver 기준 기간 부재 → refined_innovation_signal에 reference_period_start/end,
     증거별 contribution_weight(lead-lag 가중)
  D. data_role JSONB 매몰 → refined_innovation_signal의 1급 컬럼으로 승격
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "d7f3a9c1e5b2"
down_revision: Union[str, None] = "c8d4e6f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 시드: 프로젝트 타깃 섹터 (slug 단일 기준)
_SECTORS = [
    ("ai-data", "AI·데이터", "#6366F1", 1),
    ("semiconductor", "반도체·디스플레이", "#0EA5E9", 2),
    ("bio-health", "바이오·헬스케어", "#10B981", 3),
    ("energy-climate", "에너지·기후", "#84CC16", 4),
    ("mobility", "모빌리티·자동차", "#F59E0B", 5),
    ("fintech", "핀테크·금융", "#3B82F6", 6),
    ("content-creator", "콘텐츠·크리에이터", "#EC4899", 7),
    ("edutech", "교육·에듀테크", "#8B5CF6", 8),
    ("food-agri", "식품·농업", "#22C55E", 9),
    ("social-service", "사회서비스·복지", "#14B8A6", 10),
    ("logistics", "물류·유통", "#F97316", 11),
    ("beauty-fashion", "뷰티·패션", "#F43F5E", 12),
]

# 시드: 5개 Innovation 소스의 분류값 → 섹터 매핑 (확장 가능한 시작 세트)
#   match_key = 분류 차원, match_value = 원천 분류값
_SOURCE_MAP = [
    # arXiv 카테고리
    ("arxiv_category", "cs.AI", "ai-data"),
    ("arxiv_category", "cs.LG", "ai-data"),
    ("arxiv_category", "cs.CL", "ai-data"),
    ("arxiv_category", "cs.CV", "ai-data"),
    ("arxiv_category", "q-bio", "bio-health"),
    ("arxiv_category", "q-fin", "fintech"),
    ("arxiv_category", "physics.ao-ph", "energy-climate"),
    ("arxiv_category", "eess.SY", "mobility"),
    # GitHub 토픽
    ("github_topic", "machine-learning", "ai-data"),
    ("github_topic", "deep-learning", "ai-data"),
    ("github_topic", "fintech", "fintech"),
    ("github_topic", "healthcare", "bio-health"),
    ("github_topic", "climate", "energy-climate"),
    ("github_topic", "robotics", "mobility"),
    ("github_topic", "blockchain", "fintech"),
    # 관세청 HS 그룹
    ("customs_group", "SEMICONDUCTOR", "semiconductor"),
    ("customs_group", "DISPLAY", "semiconductor"),
    ("customs_group", "AUTOMOTIVE", "mobility"),
    ("customs_group", "MACHINERY", "mobility"),
    ("customs_group", "CHEMICAL", "energy-climate"),
    ("customs_group", "COSMETICS", "beauty-fashion"),
    ("customs_group", "FOOD_PROCESS", "food-agri"),
    ("customs_group", "STEEL_METAL", "semiconductor"),
    ("customs_group", "SHIP_LOGISTICS", "logistics"),
    ("customs_group", "BATTERY", "energy-climate"),
    # 한국 테크블로그 tech_category
    ("tech_category", "AI_ML", "ai-data"),
    ("tech_category", "DATA", "ai-data"),
    ("tech_category", "INFRA", "ai-data"),
    ("tech_category", "FINTECH", "fintech"),
]


def upgrade() -> None:
    # ── (A) 섹터 마스터 ──────────────────────────────────────────────
    op.create_table(
        "sectors",
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("name_ko", sa.String(length=100), nullable=False),
        sa.Column("accent_color", sa.String(length=20), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.PrimaryKeyConstraint("slug", name="pk_sectors"),
        comment="산업 마스터 (단일 기준 slug). Silver·Gold가 FK로 참조",
    )

    op.create_table(
        "sub_sectors",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sector_slug", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_sub_sectors"),
        sa.ForeignKeyConstraint(
            ["sector_slug"], ["sectors.slug"], name="fk_sub_sectors_sector"
        ),
        comment="세부 섹터",
    )
    op.create_index("ix_sub_sectors_sector", "sub_sectors", ["sector_slug"])

    # ── (A) 소스 분류값 → 섹터 통합 매핑 ─────────────────────────────
    op.create_table(
        "sector_source_map",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sector_slug", sa.String(length=50), nullable=False),
        sa.Column("match_key", sa.String(length=50), nullable=False),
        sa.Column("match_value", sa.String(length=120), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sector_source_map"),
        sa.ForeignKeyConstraint(
            ["sector_slug"], ["sectors.slug"], name="fk_sector_source_map_sector"
        ),
        sa.UniqueConstraint(
            "match_key", "match_value", name="uq_sector_source_map_key_value"
        ),
        comment="원천 분류값(arXiv 카테고리·HS그룹·토픽 등)을 섹터 slug로 통합 (결함 A)",
    )
    op.create_index(
        "ix_sector_source_map_sector", "sector_source_map", ["sector_slug"]
    )

    # ── (C,D) 교차융합형 혁신 Silver 신호 ────────────────────────────
    op.create_table(
        "refined_innovation_signal",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sector_slug", sa.String(length=50), nullable=False),
        sa.Column("sub_sector_id", sa.BigInteger(), nullable=True),
        # (D) data_role 1급 컬럼: FUTURE_TECH_SIGNAL / EXPORT_FLOW_SIGNAL 등
        sa.Column("data_role", sa.String(length=50), nullable=False),
        sa.Column("signal_topic", sa.String(length=255), nullable=False),
        sa.Column("momentum_score", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column(
            "extracted_keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        # (C) 데이터가 가리키는 기준 기간 (lead-lag 정렬의 근거)
        sa.Column("reference_period_start", sa.Date(), nullable=False),
        sa.Column("reference_period_end", sa.Date(), nullable=False),
        # (B) 교차 출처 보강 개수 (다수 소스 동시 출현 시 신호 강화)
        sa.Column(
            "source_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_refined_innovation_signal"),
        sa.ForeignKeyConstraint(
            ["sector_slug"], ["sectors.slug"], name="fk_refined_innov_sector"
        ),
        sa.ForeignKeyConstraint(
            ["sub_sector_id"], ["sub_sectors.id"], name="fk_refined_innov_sub_sector"
        ),
        sa.CheckConstraint(
            "reference_period_end >= reference_period_start",
            name="ck_refined_innov_period",
        ),
        comment="Silver — 섹터별 혁신 모멘텀 신호 (data_role·기준기간 1급화: 결함 C·D)",
    )
    op.create_index(
        "ix_refined_innov_sector", "refined_innovation_signal", ["sector_slug"]
    )
    op.create_index(
        "ix_refined_innov_data_role", "refined_innovation_signal", ["data_role"]
    )
    op.create_index(
        "ix_refined_innov_period",
        "refined_innovation_signal",
        ["reference_period_start", "reference_period_end"],
    )

    # ── (B) N:M 증거 매핑: 한 신호 ↔ 다수 원천 ───────────────────────
    op.create_table(
        "refined_signal_sources",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("signal_id", sa.BigInteger(), nullable=False),
        sa.Column("raw_table_ref", sa.String(length=50), nullable=False),
        sa.Column("raw_id", sa.BigInteger(), nullable=False),
        # 시차/신뢰 가중치 (arXiv 선행 vs 관세청 후행 차등 — 결함 C 연계)
        sa.Column(
            "contribution_weight", sa.Numeric(precision=5, scale=2), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_refined_signal_sources"),
        sa.ForeignKeyConstraint(
            ["signal_id"],
            ["refined_innovation_signal.id"],
            name="fk_refined_signal_sources_signal",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "signal_id",
            "raw_table_ref",
            "raw_id",
            name="uq_refined_signal_sources_signal_raw",
        ),
        comment="Silver 리니지 — 한 신호가 가리키는 다수 Bronze 원천(N:M, 결함 B)",
    )
    # 역추적: 특정 Bronze 행이 어느 신호들에 기여했는가
    op.create_index(
        "ix_refined_signal_sources_raw",
        "refined_signal_sources",
        ["raw_table_ref", "raw_id"],
    )

    # ── 시드 데이터 (FK 충족 위해 sectors → map 순서) ────────────────
    sectors_tbl = sa.table(
        "sectors",
        sa.column("slug", sa.String),
        sa.column("name_ko", sa.String),
        sa.column("accent_color", sa.String),
        sa.column("display_order", sa.Integer),
    )
    op.bulk_insert(
        sectors_tbl,
        [
            {
                "slug": slug,
                "name_ko": name_ko,
                "accent_color": color,
                "display_order": order,
            }
            for (slug, name_ko, color, order) in _SECTORS
        ],
    )

    map_tbl = sa.table(
        "sector_source_map",
        sa.column("sector_slug", sa.String),
        sa.column("match_key", sa.String),
        sa.column("match_value", sa.String),
    )
    op.bulk_insert(
        map_tbl,
        [
            {"match_key": key, "match_value": value, "sector_slug": slug}
            for (key, value, slug) in _SOURCE_MAP
        ],
    )


def downgrade() -> None:
    # 자식(FK 참조) → 부모 순서로 제거
    op.drop_index(
        "ix_refined_signal_sources_raw", table_name="refined_signal_sources"
    )
    op.drop_table("refined_signal_sources")

    op.drop_index("ix_refined_innov_period", table_name="refined_innovation_signal")
    op.drop_index("ix_refined_innov_data_role", table_name="refined_innovation_signal")
    op.drop_index("ix_refined_innov_sector", table_name="refined_innovation_signal")
    op.drop_table("refined_innovation_signal")

    op.drop_index("ix_sector_source_map_sector", table_name="sector_source_map")
    op.drop_table("sector_source_map")

    op.drop_index("ix_sub_sectors_sector", table_name="sub_sectors")
    op.drop_table("sub_sectors")

    op.drop_table("sectors")
