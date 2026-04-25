"""add app settings table

Revision ID: 004
Revises: 003
Create Date: 2026-04-25 21:35:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(length=128), nullable=False),
        sa.Column('value', sa.Text(), nullable=False, server_default=''),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )
    op.create_index(op.f('ix_app_settings_key'), 'app_settings', ['key'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_app_settings_key'), table_name='app_settings')
    op.drop_table('app_settings')
