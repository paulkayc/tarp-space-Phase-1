"""
20260308_002_add_auth_fields

Three changes to the users table to support both local dev and cloud auth:

1. Rename dev_user_id → external_user_id
   Keeps the column provider-neutral. In dev it holds any string passed via
   X-Dev-User-Id. In cloud it holds the auth provider's UUID (Clerk sub / Supabase UUID).

2. Add clerk_id TEXT UNIQUE (nullable)
   Reserved for Clerk's user ID format (user_xxxxx). Null in local dev.
   Populate via Clerk webhook on first sign-in in cloud.
   NOTE: if Supabase is chosen over Clerk, rename this column in migration 003.

3. Add verified_at TIMESTAMPTZ (nullable)
   Present in ARCHITECTURE.md and returned by GET /users/me (CONTRACTS.md C1.2).
   Null in local dev. Set by auth provider webhook on identity verification.

Revision: 20260308_002
"""
from alembic import op

revision = "20260308_002"
down_revision = "20260301_001"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Rename dev_user_id → external_user_id (provider-neutral name)
    op.execute("ALTER TABLE users RENAME COLUMN dev_user_id TO external_user_id")

    # Update the index to match the new column name
    op.execute("DROP INDEX IF EXISTS idx_users_dev_user_id")
    op.execute("CREATE UNIQUE INDEX idx_users_external_user_id ON users (external_user_id)")

    # 2. Add clerk_id (nullable — null until cloud auth is wired up)
    op.execute("ALTER TABLE users ADD COLUMN clerk_id TEXT UNIQUE")

    # 3. Add verified_at (nullable — null in local dev)
    op.execute("ALTER TABLE users ADD COLUMN verified_at TIMESTAMPTZ")


def downgrade():
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS verified_at")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS clerk_id")
    op.execute("DROP INDEX IF EXISTS idx_users_external_user_id")
    op.execute("ALTER TABLE users RENAME COLUMN external_user_id TO dev_user_id")
    op.execute("CREATE UNIQUE INDEX idx_users_dev_user_id ON users (dev_user_id)")
