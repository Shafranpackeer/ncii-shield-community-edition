"""Initial schema with all tables

Revision ID: 001
Revises:
Create Date: 2024-04-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE casestatus AS ENUM ('ACTIVE', 'RESOLVED', 'SUSPENDED')")
    op.execute("CREATE TYPE identifiertype AS ENUM ('NAME', 'HANDLE', 'ALIAS', 'EMAIL', 'PHONE')")
    op.execute("CREATE TYPE targetstatus AS ENUM ('DISCOVERED', 'CONFIRMED', 'FALSE_POSITIVE', 'CONTACTED', 'REMOVED', 'ESCALATED', 'RESOLVED')")
    op.execute("CREATE TYPE actiontype AS ENUM ('EMAIL_INITIAL', 'EMAIL_FOLLOWUP', 'EMAIL_HOSTING', 'EMAIL_REGISTRAR', 'MANUAL_ESCALATION', 'CHECK_REMOVAL')")
    op.execute("CREATE TYPE actionstatus AS ENUM ('PENDING', 'APPROVED', 'REJECTED', 'SCHEDULED', 'EXECUTING', 'COMPLETED', 'FAILED')")

    case_status_enum = postgresql.ENUM('ACTIVE', 'RESOLVED', 'SUSPENDED', name='casestatus', create_type=False)
    identifier_type_enum = postgresql.ENUM('NAME', 'HANDLE', 'ALIAS', 'EMAIL', 'PHONE', name='identifiertype', create_type=False)
    target_status_enum = postgresql.ENUM('DISCOVERED', 'CONFIRMED', 'FALSE_POSITIVE', 'CONTACTED', 'REMOVED', 'ESCALATED', 'RESOLVED', name='targetstatus', create_type=False)
    action_type_enum = postgresql.ENUM('EMAIL_INITIAL', 'EMAIL_FOLLOWUP', 'EMAIL_HOSTING', 'EMAIL_REGISTRAR', 'MANUAL_ESCALATION', 'CHECK_REMOVAL', name='actiontype', create_type=False)
    action_status_enum = postgresql.ENUM('PENDING', 'APPROVED', 'REJECTED', 'SCHEDULED', 'EXECUTING', 'COMPLETED', 'FAILED', name='actionstatus', create_type=False)

    # Create cases table
    op.create_table('cases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('victim_id', sa.String(length=255), nullable=False),
        sa.Column('status', case_status_enum, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('authorization_doc', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cases_id'), 'cases', ['id'], unique=False)

    # Create reference_hashes table
    op.create_table('reference_hashes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('phash', sa.BigInteger(), nullable=False),
        sa.Column('dhash', sa.BigInteger(), nullable=False),
        sa.Column('face_embedding', sa.JSON(), nullable=True),
        sa.Column('label', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reference_hashes_id'), 'reference_hashes', ['id'], unique=False)
    op.create_index(op.f('ix_reference_hashes_phash'), 'reference_hashes', ['phash'], unique=False)
    op.create_index(op.f('ix_reference_hashes_dhash'), 'reference_hashes', ['dhash'], unique=False)

    # Create identifiers table
    op.create_table('identifiers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('type', identifier_type_enum, nullable=False),
        sa.Column('value', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_identifiers_id'), 'identifiers', ['id'], unique=False)
    op.create_index(op.f('ix_identifiers_value'), 'identifiers', ['value'], unique=False)

    # Create targets table
    op.create_table('targets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('status', target_status_enum, nullable=False),
        sa.Column('discovery_source', sa.String(length=255), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('next_action_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url')
    )
    op.create_index(op.f('ix_targets_id'), 'targets', ['id'], unique=False)
    op.create_index(op.f('ix_targets_status'), 'targets', ['status'], unique=False)
    op.create_index(op.f('ix_targets_next_action_at'), 'targets', ['next_action_at'], unique=False)

    # Create target_hashes table
    op.create_table('target_hashes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('image_url', sa.Text(), nullable=False),
        sa.Column('phash', sa.BigInteger(), nullable=False),
        sa.Column('dhash', sa.BigInteger(), nullable=False),
        sa.Column('face_embedding', sa.JSON(), nullable=True),
        sa.Column('match_against_ref_id', sa.Integer(), nullable=True),
        sa.Column('match_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['target_id'], ['targets.id'], ),
        sa.ForeignKeyConstraint(['match_against_ref_id'], ['reference_hashes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_target_hashes_id'), 'target_hashes', ['id'], unique=False)
    op.create_index(op.f('ix_target_hashes_phash'), 'target_hashes', ['phash'], unique=False)
    op.create_index(op.f('ix_target_hashes_dhash'), 'target_hashes', ['dhash'], unique=False)

    # Create contacts table
    op.create_table('contacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('method_found', sa.String(length=255), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['target_id'], ['targets.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_contacts_id'), 'contacts', ['id'], unique=False)

    # Create actions table (append-only)
    op.create_table('actions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('type', action_type_enum, nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('status', action_status_enum, nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['target_id'], ['targets.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_actions_id'), 'actions', ['id'], unique=False)
    op.create_index(op.f('ix_actions_status'), 'actions', ['status'], unique=False)
    op.create_index(op.f('ix_actions_scheduled_at'), 'actions', ['scheduled_at'], unique=False)

    # Create audit_log table (append-only)
    op.create_table('audit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=100), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('old_value', sa.JSON(), nullable=True),
        sa.Column('new_value', sa.JSON(), nullable=True),
        sa.Column('user_id', sa.String(length=255), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_log_id'), 'audit_log', ['id'], unique=False)
    op.create_index(op.f('ix_audit_log_entity_type'), 'audit_log', ['entity_type'], unique=False)
    op.create_index(op.f('ix_audit_log_entity_id'), 'audit_log', ['entity_id'], unique=False)
    op.create_index(op.f('ix_audit_log_created_at'), 'audit_log', ['created_at'], unique=False)

    # Create trigger function for append-only audit_log
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'Updates not allowed on audit_log table';
            ELSIF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Deletes not allowed on audit_log table';
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger for audit_log
    op.execute("""
        CREATE TRIGGER enforce_audit_log_append_only
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_log_modification();
    """)

    # Create update trigger for targets.updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER update_targets_updated_at
        BEFORE UPDATE ON targets
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_targets_updated_at ON targets")
    op.execute("DROP TRIGGER IF EXISTS enforce_audit_log_append_only ON audit_log")

    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_modification")

    # Drop tables in reverse order of creation
    op.drop_index(op.f('ix_audit_log_created_at'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_entity_id'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_entity_type'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_id'), table_name='audit_log')
    op.drop_table('audit_log')

    op.drop_index(op.f('ix_actions_scheduled_at'), table_name='actions')
    op.drop_index(op.f('ix_actions_status'), table_name='actions')
    op.drop_index(op.f('ix_actions_id'), table_name='actions')
    op.drop_table('actions')

    op.drop_index(op.f('ix_contacts_id'), table_name='contacts')
    op.drop_table('contacts')

    op.drop_index(op.f('ix_target_hashes_dhash'), table_name='target_hashes')
    op.drop_index(op.f('ix_target_hashes_phash'), table_name='target_hashes')
    op.drop_index(op.f('ix_target_hashes_id'), table_name='target_hashes')
    op.drop_table('target_hashes')

    op.drop_index(op.f('ix_targets_next_action_at'), table_name='targets')
    op.drop_index(op.f('ix_targets_status'), table_name='targets')
    op.drop_index(op.f('ix_targets_id'), table_name='targets')
    op.drop_table('targets')

    op.drop_index(op.f('ix_identifiers_value'), table_name='identifiers')
    op.drop_index(op.f('ix_identifiers_id'), table_name='identifiers')
    op.drop_table('identifiers')

    op.drop_index(op.f('ix_reference_hashes_dhash'), table_name='reference_hashes')
    op.drop_index(op.f('ix_reference_hashes_phash'), table_name='reference_hashes')
    op.drop_index(op.f('ix_reference_hashes_id'), table_name='reference_hashes')
    op.drop_table('reference_hashes')

    op.drop_index(op.f('ix_cases_id'), table_name='cases')
    op.drop_table('cases')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS actionstatus")
    op.execute("DROP TYPE IF EXISTS actiontype")
    op.execute("DROP TYPE IF EXISTS targetstatus")
    op.execute("DROP TYPE IF EXISTS identifiertype")
    op.execute("DROP TYPE IF EXISTS casestatus")
