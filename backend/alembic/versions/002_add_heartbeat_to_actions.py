"""Add heartbeat to actions

Revision ID: 002
Revises: 001
Create Date: 2024-04-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add last_heartbeat_at column to actions table
    op.add_column('actions',
        sa.Column('last_heartbeat_at', sa.DateTime(timezone=True), nullable=True)
    )

    # Create index for efficient heartbeat queries
    op.create_index('ix_actions_last_heartbeat_at', 'actions', ['last_heartbeat_at'])


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_actions_last_heartbeat_at', table_name='actions')

    # Remove column
    op.drop_column('actions', 'last_heartbeat_at')