"""迭代审批与变更审计（在已有表上增量变更）

Revision ID: 20250604_001
Revises:
Create Date: 2025-06-04

适用：本地/服务器已有 NEXUS 表结构、尚未包含审批字段时执行 upgrade。
若已手工执行过 docs/migrations/20250604_iteration_approval.sql，请改用：
  uv run alembic stamp 20250604_001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20250604_001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APPROVAL_STATUS = postgresql.ENUM(
    "draft",
    "pending",
    "rejected",
    "committed",
    name="iterationapprovalstatus",
    create_type=False,
)

AUDIT_ACTION = postgresql.ENUM(
    "iteration_started",
    "description_updated",
    "api_added",
    "api_deleted",
    "api_updated",
    "openapi_imported",
    "submitted_for_approval",
    "approved",
    "rejected",
    "committed",
    name="iterationauditaction",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    APPROVAL_STATUS.create(bind, checkfirst=True)
    AUDIT_ACTION.create(bind, checkfirst=True)

    op.add_column(
        "service",
        sa.Column(
            "requires_iteration_approval",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column(
        "service",
        "requires_iteration_approval",
        server_default=None,
    )

    op.add_column(
        "service_iteration",
        sa.Column("base_version", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "service_iteration",
        sa.Column(
            "approval_status",
            APPROVAL_STATUS,
            nullable=False,
            server_default="draft",
        ),
    )
    op.add_column(
        "service_iteration",
        sa.Column("proposed_version", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "service_iteration",
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "service_iteration",
        sa.Column("submitted_by_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "service_iteration",
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "service_iteration",
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "service_iteration",
        sa.Column("review_comment", sa.Text(), nullable=True),
    )

    op.create_foreign_key(
        "fk_service_iteration_submitted_by_id_user",
        "service_iteration",
        "user",
        ["submitted_by_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_service_iteration_reviewed_by_id_user",
        "service_iteration",
        "user",
        ["reviewed_by_id"],
        ["id"],
    )

    op.execute(
        "UPDATE service_iteration SET approval_status = 'committed' "
        "WHERE is_committed = TRUE"
    )
    op.alter_column("service_iteration", "approval_status", server_default=None)

    op.create_table(
        "iteration_audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("service_iteration_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("action", AUDIT_ACTION, nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["service_iteration_id"],
            ["service_iteration.id"],
            name="fk_iteration_audit_log_service_iteration_id_service_iteration",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name="fk_iteration_audit_log_user_id_user",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_iteration_audit_log"),
    )
    op.create_index(
        "ix_iteration_audit_log_service_iteration_id",
        "iteration_audit_log",
        ["service_iteration_id"],
        unique=False,
    )
    op.create_index(
        "ix_iteration_audit_log_created_at",
        "iteration_audit_log",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_iteration_audit_log_created_at", table_name="iteration_audit_log")
    op.drop_index(
        "ix_iteration_audit_log_service_iteration_id",
        table_name="iteration_audit_log",
    )
    op.drop_table("iteration_audit_log")

    op.drop_constraint(
        "fk_service_iteration_reviewed_by_id_user",
        "service_iteration",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_service_iteration_submitted_by_id_user",
        "service_iteration",
        type_="foreignkey",
    )
    op.drop_column("service_iteration", "review_comment")
    op.drop_column("service_iteration", "reviewed_by_id")
    op.drop_column("service_iteration", "reviewed_at")
    op.drop_column("service_iteration", "submitted_by_id")
    op.drop_column("service_iteration", "submitted_at")
    op.drop_column("service_iteration", "proposed_version")
    op.drop_column("service_iteration", "approval_status")
    op.drop_column("service_iteration", "base_version")

    op.drop_column("service", "requires_iteration_approval")

    bind = op.get_bind()
    AUDIT_ACTION.drop(bind, checkfirst=True)
    APPROVAL_STATUS.drop(bind, checkfirst=True)
