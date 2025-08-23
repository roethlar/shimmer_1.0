# Shimmer v1.1 → v1.2 Change Log (Draft)

Status: For reviewer circulation

## Summary
- Jettison legacy verbosity (no `ctag.*`); adopt symbol‑only metadata facets.
- Replace text tokens with symbols where safe: `№##` (request id), `ς:<base36>` (session), `β##` (batch), `ξ.*` (capabilities).
- Prefer 4D vectors when confidence is default; semantics unchanged.
- Tighten compactness guidance and introduce a facet registry for interoperability.

## Additions
- Symbolic facets (domain‑agnostic): `σ μ κ π λ ρ χ θ γ α ε` with `:` values (no `ctag` alias).
- Facet registry (YAML) with allowed values/regex and examples.
- Capability negotiation (compact): `ξ.spec`, `ξ.conf`, `ξ.fac`, `ξ.lint`, optional `ξ.reg`.
- Batching tag: `β00`..`β99` for related lines.
- ABNF grammar appendix and explicit parsing precedence.

## Changes (non-breaking)
- Compactness preference: emit T9 (4D) when confidence equals default.
- Clarify Unicode tooling requirements; reaffirm real `→` (U+2192).
- Clarify that `χ` must be boolean (`χ:1`/`χ:0`), avoiding presence‑only ambiguity.
- Remove `ctag.*` entirely from v1.2; only symbolic facets are valid in this draft.

## Defer/Out of Scope
- Runtime/programming proposals (interpreters, IR) remain external guidance.
- Binary T9p unchanged; text↔binary bridge guidance unchanged.

## Compatibility
- This draft targets a clean adoption in greenfield contexts (no production users); no `ctag.*` aliasing.
- Existing v1.1 lines are not guaranteed to lint under v1.2 compact rules; migration is mechanical via facets/ξ/β/№/ς.

