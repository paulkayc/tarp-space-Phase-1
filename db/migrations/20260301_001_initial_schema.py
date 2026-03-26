"""
20260301_001_initial_schema

Full initial schema for Tarp-Space Phase 1:
  extensions, all tables, and all indexes.

Revision: 20260301_001
"""
from alembic import op

# Alembic revision identifiers
revision = "20260301_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ------------------------------------------------------------------
    # Extensions
    # ------------------------------------------------------------------
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "postgis"')

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE users (
            id                        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            email                     TEXT UNIQUE,
            display_name              TEXT,
            phone                     TEXT,
            sex                       TEXT CHECK (sex IN (
                                        'male','female','non-binary','prefer_not_to_say'
                                      )),
            location_raw              TEXT,
            location_geom             GEOGRAPHY(POINT, 4326),
            dev_user_id               TEXT NOT NULL UNIQUE,
            persona                   JSONB NOT NULL DEFAULT '{}',
            onboarding_completed_at   TIMESTAMPTZ,
            autonomy_default          TEXT NOT NULL DEFAULT 'escalate_key_points'
                                      CHECK (autonomy_default IN (
                                        'supervised',
                                        'escalate_key_points',
                                        'fully_autonomous'
                                      )),
            community_ids             TEXT[],
            created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ------------------------------------------------------------------
    # onboarding_sessions
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE onboarding_sessions (
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

    # ------------------------------------------------------------------
    # onboarding_messages
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE onboarding_messages (
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

    # ------------------------------------------------------------------
    # mandates
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE mandates (
            id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            owner_id              UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            intent_type           TEXT CHECK (intent_type IN (
                                    'buy','sell','request_service',
                                    'offer_service','discover'
                                  )),
            vertical              TEXT CHECK (vertical IN ('goods','services')),
            category              TEXT,
            description           TEXT,
            hard_constraints      JSONB NOT NULL DEFAULT '[]',
            negotiation_range     JSONB NOT NULL DEFAULT '[]',
            soft_preferences      JSONB NOT NULL DEFAULT '[]',
            dealbreakers          JSONB NOT NULL DEFAULT '[]',
            escalation_triggers   JSONB NOT NULL DEFAULT '[]',
            autonomy_level        TEXT NOT NULL DEFAULT 'escalate_key_points'
                                  CHECK (autonomy_level IN (
                                    'supervised',
                                    'escalate_key_points',
                                    'fully_autonomous'
                                  )),
            completeness_score    NUMERIC(4,3) NOT NULL DEFAULT 0.0
                                  CHECK (completeness_score BETWEEN 0 AND 1),
            is_active             BOOLEAN NOT NULL DEFAULT FALSE,
            is_archived           BOOLEAN NOT NULL DEFAULT FALSE,
            version               INTEGER NOT NULL DEFAULT 1,
            created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            confirmed_at          TIMESTAMPTZ,
            archived_at           TIMESTAMPTZ
        )
    """)

    # ------------------------------------------------------------------
    # mandate_fields
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE mandate_fields (
            id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            mandate_id   UUID NOT NULL REFERENCES mandates(id) ON DELETE CASCADE,
            field_name   TEXT NOT NULL,
            field_value  JSONB NOT NULL,
            source       TEXT NOT NULL DEFAULT 'inferred'
                         CHECK (source IN (
                           'explicit',
                           'inferred',
                           'persona',
                           'defaulted'
                         )),
            confidence   NUMERIC(4,3) NOT NULL DEFAULT 1.0,
            version      INTEGER NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (mandate_id, field_name, version)
        )
    """)

    # ------------------------------------------------------------------
    # mandate_versions
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE mandate_versions (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            mandate_id      UUID NOT NULL REFERENCES mandates(id) ON DELETE CASCADE,
            version         INTEGER NOT NULL,
            snapshot        JSONB NOT NULL,
            changed_fields  TEXT[],
            change_source   TEXT NOT NULL
                            CHECK (change_source IN (
                              'user_message',
                              'explicit_edit',
                              'signal_refinement',
                              'confirmation',
                              'persona_prefill'
                            )),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (mandate_id, version)
        )
    """)

    # ------------------------------------------------------------------
    # conversations
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE conversations (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            mandate_id      UUID REFERENCES mandates(id) ON DELETE SET NULL,
            status          TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'confirmed', 'abandoned')),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_message_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ------------------------------------------------------------------
    # messages
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE messages (
            id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            conversation_id     UUID NOT NULL REFERENCES conversations(id)
                                ON DELETE CASCADE,
            role                TEXT NOT NULL CHECK (role IN ('user', 'agent')),
            content             TEXT NOT NULL,
            mandate_delta       JSONB,
            completeness_after  NUMERIC(4,3),
            gaps_remaining      TEXT[],
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            token_count         INTEGER
        )
    """)

    # ------------------------------------------------------------------
    # inventory
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE inventory (
            id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            seller_id        UUID REFERENCES users(id) ON DELETE SET NULL,
            vertical         TEXT NOT NULL CHECK (vertical IN ('goods', 'services')),
            category         TEXT NOT NULL,
            title            TEXT NOT NULL,
            description      TEXT NOT NULL,
            metadata         JSONB NOT NULL DEFAULT '{}',
            price            NUMERIC(10, 2) NOT NULL,
            price_negotiable BOOLEAN NOT NULL DEFAULT TRUE,
            location_raw     TEXT,
            location_geom    GEOGRAPHY(POINT, 4326),
            embedding        VECTOR(1536),
            is_active        BOOLEAN NOT NULL DEFAULT TRUE,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ------------------------------------------------------------------
    # search_runs
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE search_runs (
            id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            mandate_id               UUID NOT NULL REFERENCES mandates(id)
                                     ON DELETE CASCADE,
            mandate_version          INTEGER NOT NULL,
            candidates_pre_filter    INTEGER,
            candidates_post_filter   INTEGER,
            result_count             INTEGER,
            escalation_count         INTEGER,
            top_score                NUMERIC(5,4),
            latency_ms               INTEGER,
            created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ------------------------------------------------------------------
    # search_results
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE search_results (
            id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            search_run_id       UUID NOT NULL REFERENCES search_runs(id)
                                ON DELETE CASCADE,
            listing_id          UUID NOT NULL REFERENCES inventory(id)
                                ON DELETE CASCADE,
            similarity_score    NUMERIC(5,4) NOT NULL,
            trust_weight        NUMERIC(5,4) NOT NULL DEFAULT 0.0,
            alignment_score     NUMERIC(5,4) NOT NULL,
            within_mandate      BOOLEAN NOT NULL,
            matched_dimensions  TEXT[],
            explanation         TEXT,
            is_escalation       BOOLEAN NOT NULL DEFAULT FALSE,
            escalation_delta    NUMERIC(10,2),
            escalation_question TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ------------------------------------------------------------------
    # signals
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE signals (
            id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            owner_id              UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            search_result_id      UUID NOT NULL REFERENCES search_results(id)
                                  ON DELETE CASCADE,
            signal_type           TEXT NOT NULL CHECK (signal_type IN (
                                    'accept', 'reject',
                                    'escalation_yes', 'escalation_no'
                                  )),
            reason                TEXT,
            mandate_delta_applied JSONB,
            mandate_version_after INTEGER,
            created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ------------------------------------------------------------------
    # activity_log
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE activity_log (
            id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            owner_id    UUID REFERENCES users(id) ON DELETE SET NULL,
            mandate_id  UUID REFERENCES mandates(id) ON DELETE SET NULL,
            event_type  TEXT NOT NULL,
            payload     JSONB NOT NULL DEFAULT '{}',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ------------------------------------------------------------------
    # trust_edges
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE trust_edges (
            id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            from_user_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            to_user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            edge_type     TEXT NOT NULL CHECK (edge_type IN (
                            'transaction', 'vouched', 'community', 'referral'
                          )),
            weight        NUMERIC(4,3) NOT NULL DEFAULT 0.4
                          CHECK (weight BETWEEN 0 AND 1),
            source_ref    TEXT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at    TIMESTAMPTZ,
            revoked_at    TIMESTAMPTZ,
            UNIQUE (from_user_id, to_user_id, edge_type)
        )
    """)

    # ------------------------------------------------------------------
    # Indexes — users
    # ------------------------------------------------------------------
    op.execute("CREATE INDEX idx_users_dev_user_id ON users (dev_user_id)")
    op.execute("CREATE INDEX idx_users_location ON users USING GIST (location_geom)")

    # Indexes — onboarding
    op.execute("CREATE INDEX idx_onboarding_sessions_owner ON onboarding_sessions (owner_id)")
    op.execute("""
        CREATE INDEX idx_onboarding_messages_session
            ON onboarding_messages (session_id, created_at ASC)
    """)

    # Indexes — mandates
    op.execute("CREATE INDEX idx_mandates_owner_id ON mandates (owner_id)")
    op.execute("""
        CREATE INDEX idx_mandates_owner_active
            ON mandates (owner_id) WHERE is_active = TRUE
    """)
    op.execute("CREATE INDEX idx_mandates_intent_vertical ON mandates (intent_type, vertical)")

    # Indexes — mandate fields and versions
    op.execute("CREATE INDEX idx_mandate_fields_mandate_id ON mandate_fields (mandate_id)")
    op.execute("""
        CREATE INDEX idx_mandate_fields_field_name
            ON mandate_fields (mandate_id, field_name)
    """)
    op.execute("""
        CREATE INDEX idx_mandate_versions_mandate
            ON mandate_versions (mandate_id, version DESC)
    """)

    # Indexes — conversations and messages
    op.execute("CREATE INDEX idx_conversations_owner_id ON conversations (owner_id)")
    op.execute("CREATE INDEX idx_conversations_mandate_id ON conversations (mandate_id)")
    op.execute("""
        CREATE INDEX idx_messages_conversation_id
            ON messages (conversation_id, created_at ASC)
    """)

    # Indexes — inventory
    op.execute("""
        CREATE INDEX idx_inventory_category_vertical
            ON inventory (category, vertical) WHERE is_active = TRUE
    """)
    op.execute("""
        CREATE INDEX idx_inventory_price
            ON inventory (price) WHERE is_active = TRUE
    """)
    op.execute("CREATE INDEX idx_inventory_location ON inventory USING GIST (location_geom)")
    op.execute("""
        CREATE INDEX idx_inventory_embedding
            ON inventory USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 50)
    """)

    # Indexes — search
    op.execute("CREATE INDEX idx_search_results_run_id ON search_results (search_run_id)")
    op.execute("CREATE INDEX idx_search_results_listing_id ON search_results (listing_id)")

    # Indexes — signals
    op.execute("""
        CREATE INDEX idx_signals_owner_id
            ON signals (owner_id, created_at DESC)
    """)
    op.execute("CREATE INDEX idx_signals_result_id ON signals (search_result_id)")

    # Indexes — trust graph
    op.execute("""
        CREATE INDEX idx_trust_edges_from_user
            ON trust_edges (from_user_id) WHERE revoked_at IS NULL
    """)
    op.execute("""
        CREATE INDEX idx_trust_edges_to_user
            ON trust_edges (to_user_id) WHERE revoked_at IS NULL
    """)
    op.execute("""
        CREATE INDEX idx_trust_edges_type
            ON trust_edges (from_user_id, edge_type) WHERE revoked_at IS NULL
    """)

    # Indexes — activity log
    op.execute("""
        CREATE INDEX idx_activity_log_owner
            ON activity_log (owner_id, created_at DESC)
    """)
    op.execute("""
        CREATE INDEX idx_activity_log_mandate
            ON activity_log (mandate_id, created_at DESC)
    """)
    op.execute("""
        CREATE INDEX idx_activity_log_event_type
            ON activity_log (event_type, created_at DESC)
    """)


def downgrade():
    # Drop indexes first (most drop automatically with table, but be explicit)
    op.execute("DROP INDEX IF EXISTS idx_activity_log_event_type")
    op.execute("DROP INDEX IF EXISTS idx_activity_log_mandate")
    op.execute("DROP INDEX IF EXISTS idx_activity_log_owner")
    op.execute("DROP INDEX IF EXISTS idx_trust_edges_type")
    op.execute("DROP INDEX IF EXISTS idx_trust_edges_to_user")
    op.execute("DROP INDEX IF EXISTS idx_trust_edges_from_user")
    op.execute("DROP INDEX IF EXISTS idx_signals_result_id")
    op.execute("DROP INDEX IF EXISTS idx_signals_owner_id")
    op.execute("DROP INDEX IF EXISTS idx_search_results_listing_id")
    op.execute("DROP INDEX IF EXISTS idx_search_results_run_id")
    op.execute("DROP INDEX IF EXISTS idx_inventory_embedding")
    op.execute("DROP INDEX IF EXISTS idx_inventory_location")
    op.execute("DROP INDEX IF EXISTS idx_inventory_price")
    op.execute("DROP INDEX IF EXISTS idx_inventory_category_vertical")
    op.execute("DROP INDEX IF EXISTS idx_messages_conversation_id")
    op.execute("DROP INDEX IF EXISTS idx_conversations_mandate_id")
    op.execute("DROP INDEX IF EXISTS idx_conversations_owner_id")
    op.execute("DROP INDEX IF EXISTS idx_mandate_versions_mandate")
    op.execute("DROP INDEX IF EXISTS idx_mandate_fields_field_name")
    op.execute("DROP INDEX IF EXISTS idx_mandate_fields_mandate_id")
    op.execute("DROP INDEX IF EXISTS idx_mandates_intent_vertical")
    op.execute("DROP INDEX IF EXISTS idx_mandates_owner_active")
    op.execute("DROP INDEX IF EXISTS idx_mandates_owner_id")
    op.execute("DROP INDEX IF EXISTS idx_onboarding_messages_session")
    op.execute("DROP INDEX IF EXISTS idx_onboarding_sessions_owner")
    op.execute("DROP INDEX IF EXISTS idx_users_location")
    op.execute("DROP INDEX IF EXISTS idx_users_dev_user_id")

    # Drop tables in reverse dependency order
    op.execute("DROP TABLE IF EXISTS trust_edges")
    op.execute("DROP TABLE IF EXISTS activity_log")
    op.execute("DROP TABLE IF EXISTS signals")
    op.execute("DROP TABLE IF EXISTS search_results")
    op.execute("DROP TABLE IF EXISTS search_runs")
    op.execute("DROP TABLE IF EXISTS inventory")
    op.execute("DROP TABLE IF EXISTS messages")
    op.execute("DROP TABLE IF EXISTS conversations")
    op.execute("DROP TABLE IF EXISTS mandate_versions")
    op.execute("DROP TABLE IF EXISTS mandate_fields")
    op.execute("DROP TABLE IF EXISTS mandates")
    op.execute("DROP TABLE IF EXISTS onboarding_messages")
    op.execute("DROP TABLE IF EXISTS onboarding_sessions")
    op.execute("DROP TABLE IF EXISTS users")
