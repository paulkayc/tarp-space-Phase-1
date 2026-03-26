"""
20260326_003_personal_memory_tables

Adds Personal Agent snippet memory persistence tables.

Revision: 20260326_003
"""
from alembic import op

revision = "20260326_003"
down_revision = "20260308_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE personal_memories (
            id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            owner_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            content       TEXT NOT NULL,
            tags          TEXT[] NOT NULL DEFAULT '{}',
            source        TEXT NOT NULL DEFAULT 'inferred'
                          CHECK (source IN ('explicit','inferred','derived')),
            confidence    NUMERIC(4,3) NOT NULL DEFAULT 0.8
                          CHECK (confidence BETWEEN 0 AND 1),
            is_active     BOOLEAN NOT NULL DEFAULT TRUE,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE personal_memory_events (
            id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            memory_id         UUID NOT NULL REFERENCES personal_memories(id) ON DELETE CASCADE,
            owner_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            event_type        TEXT NOT NULL
                              CHECK (event_type IN ('created','updated','deactivated','reactivated')),
            previous_content  TEXT,
            new_content       TEXT,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute("CREATE INDEX idx_personal_memories_owner_id ON personal_memories (owner_id)")
    op.execute("CREATE INDEX idx_personal_memories_owner_updated ON personal_memories (owner_id, updated_at DESC)")
    op.execute("CREATE INDEX idx_personal_memory_events_memory_id ON personal_memory_events (memory_id)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_personal_memory_events_memory_id")
    op.execute("DROP INDEX IF EXISTS idx_personal_memories_owner_updated")
    op.execute("DROP INDEX IF EXISTS idx_personal_memories_owner_id")
    op.execute("DROP TABLE IF EXISTS personal_memory_events")
    op.execute("DROP TABLE IF EXISTS personal_memories")
