"""
SQLAlchemy ORM models for every table in the Tarp-Space schema.
"""
import uuid

from geoalchemy2 import Geography
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.ext.mutable import MutableDict

from app.db.base import Base


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(Text, unique=True)
    display_name = Column(Text)
    phone = Column(Text)
    sex = Column(
        Text,
        CheckConstraint(
            "sex IN ('male','female','non-binary','prefer_not_to_say')",
            name="ck_users_sex",
        ),
    )

    # Location
    location_raw = Column(Text)
    location_geom = Column(Geography(geometry_type="POINT", srid=4326))

    # Dev auth
    dev_user_id = Column(Text, nullable=False, unique=True)

    # Persona JSONB blob
    persona = Column(MutableDict.as_mutable(JSONB), nullable=False, default=dict)

    # Onboarding state
    onboarding_completed_at = Column(TIMESTAMP(timezone=True))

    # Agent defaults
    autonomy_default = Column(
        Text,
        nullable=False,
        default="escalate_key_points",
        info={"check": "autonomy_default IN ('supervised','escalate_key_points','fully_autonomous')"},
    )

    # Community membership strings
    community_ids = Column(ARRAY(Text))

    created_at = Column(TIMESTAMP(timezone=True), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "autonomy_default IN ('supervised','escalate_key_points','fully_autonomous')",
            name="ck_users_autonomy_default",
        ),
    )

    def __repr__(self):
        return f"<User id={self.id}>"


# ---------------------------------------------------------------------------
# onboarding_sessions
# ---------------------------------------------------------------------------
class OnboardingSession(Base):
    __tablename__ = "onboarding_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status = Column(Text, nullable=False, default="active")
    completed_at = Column(TIMESTAMP(timezone=True))
    skipped_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)
    last_message_at = Column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','completed','skipped')",
            name="ck_onboarding_sessions_status",
        ),
    )

    def __repr__(self):
        return f"<OnboardingSession id={self.id}>"


# ---------------------------------------------------------------------------
# onboarding_messages
# ---------------------------------------------------------------------------
class OnboardingMessage(Base):
    __tablename__ = "onboarding_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("onboarding_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    persona_delta = Column(JSONB)
    completeness_after = Column(Numeric(4, 3))
    token_count = Column(Integer)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "role IN ('user','agent')",
            name="ck_onboarding_messages_role",
        ),
    )

    def __repr__(self):
        return f"<OnboardingMessage id={self.id}>"


# ---------------------------------------------------------------------------
# mandates
# ---------------------------------------------------------------------------
class Mandate(Base):
    __tablename__ = "mandates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    intent_type = Column(Text)
    vertical = Column(Text)
    category = Column(Text)
    description = Column(Text)
    hard_constraints = Column(JSONB, nullable=False, default=list)
    negotiation_range = Column(JSONB, nullable=False, default=list)
    soft_preferences = Column(JSONB, nullable=False, default=list)
    dealbreakers = Column(JSONB, nullable=False, default=list)
    escalation_triggers = Column(JSONB, nullable=False, default=list)
    autonomy_level = Column(Text, nullable=False, default="escalate_key_points")
    completeness_score = Column(Numeric(4, 3), nullable=False, default=0.0)
    is_active = Column(Boolean, nullable=False, default=False)
    is_archived = Column(Boolean, nullable=False, default=False)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False)
    confirmed_at = Column(TIMESTAMP(timezone=True))
    archived_at = Column(TIMESTAMP(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "intent_type IN ('buy','sell','request_service','offer_service','discover')",
            name="ck_mandates_intent_type",
        ),
        CheckConstraint(
            "vertical IN ('goods','services')",
            name="ck_mandates_vertical",
        ),
        CheckConstraint(
            "autonomy_level IN ('supervised','escalate_key_points','fully_autonomous')",
            name="ck_mandates_autonomy_level",
        ),
        CheckConstraint(
            "completeness_score BETWEEN 0 AND 1",
            name="ck_mandates_completeness_score",
        ),
    )

    def __repr__(self):
        return f"<Mandate id={self.id}>"


# ---------------------------------------------------------------------------
# mandate_fields
# ---------------------------------------------------------------------------
class MandateField(Base):
    __tablename__ = "mandate_fields"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mandate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mandates.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_name = Column(Text, nullable=False)
    field_value = Column(JSONB, nullable=False)
    source = Column(Text, nullable=False, default="inferred")
    confidence = Column(Numeric(4, 3), nullable=False, default=1.0)
    version = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "source IN ('explicit','inferred','persona','defaulted')",
            name="ck_mandate_fields_source",
        ),
        UniqueConstraint("mandate_id", "field_name", "version", name="uq_mandate_fields"),
    )

    def __repr__(self):
        return f"<MandateField id={self.id}>"


# ---------------------------------------------------------------------------
# mandate_versions
# ---------------------------------------------------------------------------
class MandateVersion(Base):
    __tablename__ = "mandate_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mandate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mandates.id", ondelete="CASCADE"),
        nullable=False,
    )
    version = Column(Integer, nullable=False)
    snapshot = Column(JSONB, nullable=False)
    changed_fields = Column(ARRAY(Text))
    change_source = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "change_source IN ('user_message','explicit_edit','signal_refinement','confirmation','persona_prefill')",
            name="ck_mandate_versions_change_source",
        ),
        UniqueConstraint("mandate_id", "version", name="uq_mandate_versions"),
    )

    def __repr__(self):
        return f"<MandateVersion id={self.id}>"


# ---------------------------------------------------------------------------
# conversations
# ---------------------------------------------------------------------------
class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    mandate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mandates.id", ondelete="SET NULL"),
    )
    status = Column(Text, nullable=False, default="active")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)
    last_message_at = Column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','confirmed','abandoned')",
            name="ck_conversations_status",
        ),
    )

    def __repr__(self):
        return f"<Conversation id={self.id}>"


# ---------------------------------------------------------------------------
# messages
# ---------------------------------------------------------------------------
class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    mandate_delta = Column(JSONB)
    completeness_after = Column(Numeric(4, 3))
    gaps_remaining = Column(ARRAY(Text))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)
    token_count = Column(Integer)

    __table_args__ = (
        CheckConstraint(
            "role IN ('user','agent')",
            name="ck_messages_role",
        ),
    )

    def __repr__(self):
        return f"<Message id={self.id}>"


# ---------------------------------------------------------------------------
# inventory
# ---------------------------------------------------------------------------
class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    vertical = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    metadata = Column(JSONB, nullable=False, default=dict)
    price = Column(Numeric(10, 2), nullable=False)
    price_negotiable = Column(Boolean, nullable=False, default=True)
    location_raw = Column(Text)
    location_geom = Column(Geography(geometry_type="POINT", srid=4326))
    embedding = Column(Vector(1536))
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "vertical IN ('goods','services')",
            name="ck_inventory_vertical",
        ),
    )

    def __repr__(self):
        return f"<Inventory id={self.id}>"


# ---------------------------------------------------------------------------
# search_runs
# ---------------------------------------------------------------------------
class SearchRun(Base):
    __tablename__ = "search_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mandate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mandates.id", ondelete="CASCADE"),
        nullable=False,
    )
    mandate_version = Column(Integer, nullable=False)
    candidates_pre_filter = Column(Integer)
    candidates_post_filter = Column(Integer)
    result_count = Column(Integer)
    escalation_count = Column(Integer)
    top_score = Column(Numeric(5, 4))
    latency_ms = Column(Integer)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)

    def __repr__(self):
        return f"<SearchRun id={self.id}>"


# ---------------------------------------------------------------------------
# search_results
# ---------------------------------------------------------------------------
class SearchResult(Base):
    __tablename__ = "search_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("search_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("inventory.id", ondelete="CASCADE"),
        nullable=False,
    )
    similarity_score = Column(Numeric(5, 4), nullable=False)
    trust_weight = Column(Numeric(5, 4), nullable=False, default=0.0)
    alignment_score = Column(Numeric(5, 4), nullable=False)
    within_mandate = Column(Boolean, nullable=False)
    matched_dimensions = Column(ARRAY(Text))
    explanation = Column(Text)
    is_escalation = Column(Boolean, nullable=False, default=False)
    escalation_delta = Column(Numeric(10, 2))
    escalation_question = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)

    def __repr__(self):
        return f"<SearchResult id={self.id}>"


# ---------------------------------------------------------------------------
# signals
# ---------------------------------------------------------------------------
class Signal(Base):
    __tablename__ = "signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    search_result_id = Column(
        UUID(as_uuid=True),
        ForeignKey("search_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    signal_type = Column(Text, nullable=False)
    reason = Column(Text)
    mandate_delta_applied = Column(JSONB)
    mandate_version_after = Column(Integer)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "signal_type IN ('accept','reject','escalation_yes','escalation_no')",
            name="ck_signals_signal_type",
        ),
    )

    def __repr__(self):
        return f"<Signal id={self.id}>"


# ---------------------------------------------------------------------------
# activity_log
# ---------------------------------------------------------------------------
class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    mandate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mandates.id", ondelete="SET NULL"),
    )
    event_type = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=False, default=dict)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)

    def __repr__(self):
        return f"<ActivityLog id={self.id}>"


# ---------------------------------------------------------------------------
# trust_edges
# ---------------------------------------------------------------------------
class TrustEdge(Base):
    __tablename__ = "trust_edges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    edge_type = Column(Text, nullable=False)
    weight = Column(Numeric(4, 3), nullable=False, default=0.4)
    source_ref = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False)
    expires_at = Column(TIMESTAMP(timezone=True))
    revoked_at = Column(TIMESTAMP(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "edge_type IN ('transaction','vouched','community','referral')",
            name="ck_trust_edges_edge_type",
        ),
        CheckConstraint(
            "weight BETWEEN 0 AND 1",
            name="ck_trust_edges_weight",
        ),
        UniqueConstraint(
            "from_user_id", "to_user_id", "edge_type",
            name="uq_trust_edges",
        ),
    )

    def __repr__(self):
        return f"<TrustEdge id={self.id}>"
