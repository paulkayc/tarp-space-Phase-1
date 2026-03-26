"""
20260301_003_add_persona_source

Documents the addition of 'persona' as a valid source value in mandate_fields.
The source CHECK constraint in migration 001 already includes 'persona' because
the scaffold was built with onboarding pre-fill in mind. This migration makes
the intent explicit in the audit trail.

The upgrade is a true no-op (IF NOT EXISTS / constraint already correct).
The downgrade is intentionally a no-op — removing 'persona' from the constraint
would break any mandate_fields rows already using that source.

Revision: 20260301_003
"""
from alembic import op

revision = "20260301_003"
down_revision = "20260301_002"
branch_labels = None
depends_on = None


def upgrade():
    # 'persona' source was included in the CHECK constraint in migration 001:
    #   CHECK (source IN ('explicit', 'inferred', 'persona', 'defaulted'))
    # No DDL change needed. This migration documents the intent.
    pass


def downgrade():
    # Intentional no-op — do not remove 'persona' from the source constraint.
    pass
