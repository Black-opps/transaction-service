"""add_upload_file_id_column

Revision ID: b3fd8f610988
Revises: c4d7712fb5a1
Create Date: 2026-05-18 13:26:07.398328

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3fd8f610988"
down_revision: Union[str, Sequence[str], None] = "c4d7712fb5a1"
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
