"""Add confirmation tables

Revision ID: 002
Revises: 001
Create Date: 2024-04-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create review_thumbnails table
    op.create_table('review_thumbnails',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('image_url', sa.String(length=2048), nullable=False),
        sa.Column('thumbnail_blob', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['target_id'], ['targets.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_review_thumbnails_expires_at'), 'review_thumbnails', ['expires_at'], unique=False)
    op.create_index(op.f('ix_review_thumbnails_id'), 'review_thumbnails', ['id'], unique=False)
    op.create_index(op.f('ix_review_thumbnails_target_id'), 'review_thumbnails', ['target_id'], unique=False)

    # Add match_type column to target_hashes
    op.add_column('target_hashes', sa.Column('match_type', sa.String(length=50), nullable=True))


def downgrade() -> None:
    # Remove match_type column from target_hashes
    op.drop_column('target_hashes', 'match_type')

    # Drop review_thumbnails table
    op.drop_index(op.f('ix_review_thumbnails_target_id'), table_name='review_thumbnails')
    op.drop_index(op.f('ix_review_thumbnails_id'), table_name='review_thumbnails')
    op.drop_index(op.f('ix_review_thumbnails_expires_at'), table_name='review_thumbnails')
    op.drop_table('review_thumbnails')