# Shimmer Spec Changelog

All notable changes to this repository are documented here. Dates use YYYY‑MM‑DD.

## 1.1 — 2025-08-19
- Add “Human‑First Authoring: Defaults & Inference” (normative) to enable robust English → Shimmer mapping from unconstrained human input.
  - Deterministic defaults for routing (app‑provided), action inference, temporal extraction (τ###), deliverables inclusion, session/tags (`ctag.*`, `s:<base36>`), and 5D vector estimation with quantization.
  - Clarify container compactness: no spaces in container; real Unicode arrow `→`.
  - Emphasize encoding domain/intent using compact `ctag.*` tokens instead of prose.
- Glossing guidance: routing is exactly the first two symbols of the container; do not conflate routing with tokens.
- No binary layout changes.

## 1.0 — 2025-08-18
- Unified initial release of Shimmer 1.0 (T9/T9+, Container Format v2.0, T9p Binary, parity, tolerances).

