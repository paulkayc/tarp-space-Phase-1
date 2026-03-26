"""
Semantic ranker — ARCHITECTURE.md Section 3.4, Stage 2
No LLM. pgvector cosine similarity against pre-computed listing embeddings.

alignment_score = similarity_score × (1 + trust_weight × 0.3)
trust_weight = 0.0 in Phase 1 (no live trust graph).
"""
# TODO: implement in Phase 1 matching sprint
