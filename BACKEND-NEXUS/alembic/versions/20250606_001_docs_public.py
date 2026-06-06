"""只读 API 文档门户：service.docs_public

Revision ID: 20250606_001
Revises: 20250604_001
Create Date: 2025-06-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20250606_001"
down_revision: Union[str, Sequence[str], None] = "20250604_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "service",
        sa.Column(
            "docs_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column("service", "docs_public", server_default=None)


def downgrade() -> None:
    op.drop_column("service", "docs_public")
