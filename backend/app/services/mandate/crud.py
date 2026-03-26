"""
Mandate DB read/write with version management — ARCHITECTURE.md Section 3.2
Every write increments version and snapshots prior state to mandate_versions.
owner_id is always injected from the auth dependency — never from request body.
"""
# TODO: implement in Phase 1 mandate sprint
