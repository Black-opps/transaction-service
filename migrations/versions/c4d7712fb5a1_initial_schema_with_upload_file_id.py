"""Initial schema with upload_file_id

Revision ID: c4d7712fb5a1
Revises:
Create Date: 2026-05-18 13:25:50.835212

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d7712fb5a1"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        "transactions", sa.Column("upload_file_id", sa.String(), nullable=True)
    )
    op.create_index(
        "idx_transactions_upload_file_id", "transactions", ["upload_file_id"]
    )


def downgrade():
    op.drop_index("idx_transactions_upload_file_id", table_name="transactions")
    op.drop_column("transactions", "upload_file_id")
