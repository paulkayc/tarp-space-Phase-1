"""
20260301_002_add_persona

Documents the persona JSONB blob and onboarding_completed_at columns on users.
Uses ADD COLUMN IF NOT EXISTS — these were pre-included in migration 001
for the Phase 1 scaffold. This migration makes the intent explicit and keeps
the audit trail consistent with the onboarding implementation session.

Revision: 20260301_002
"""
from alembic import op

revision = "20260301_002"
down_revision = "20260308_002"
branch_labels = None
depends_on = None


def upgrade():
    # IF NOT EXISTS — these columns already exist from migration 001.
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS persona JSONB NOT NULL DEFAULT '{}'
    """)
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMPTZ
    """)
    # Onboarding sessions and messages tables (created in 001).
    # Document their existence here for audit clarity.
    op.execute("""
        CREATE TABLE IF NOT EXISTS onboarding_sessions (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status          TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'completed', 'skipped')),
            completed_at    TIMESTAMPTZ,
            skipped_at      TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_message_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS onboarding_messages (
            id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            session_id          UUID NOT NULL REFERENCES onboarding_sessions(id)
                                ON DELETE CASCADE,
            role                TEXT NOT NULL CHECK (role IN ('user', 'agent')),
            content             TEXT NOT NULL,
            persona_delta       JSONB,
            completeness_after  NUMERIC(4,3),
            token_count         INTEGER,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def downgrade():
    # Do not drop persona or onboarding_completed_at — they belong to the
    # original schema intent established in migration 001.
    pass
