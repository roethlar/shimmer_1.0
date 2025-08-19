# Shimmer 1.0

Unified, production‑ready specification bundle for the Shimmer communication stack.

This folder consolidates finalized pieces from the research repo into a coherent, versioned spec suitable for implementation and review.

## Contents

- `Shimmer_Spec_v1.0.md` — Single, unified spec for:
  - T9 (4D) and T9+ (5D) Semantic Vectors
  - Text Container Format v2.0 (routing/actions/metadata/temporal/deliverables)
  - Binary Container (T9p) v1.0 (fixed 16‑byte structure)
  - Parity/validation, calibration/tolerances, Genesis onboarding

## Binary vs Text (At a Glance)

- Binary (T9p/Base64 SJL‑B64): smallest, fastest, most precise (int16 axes, uint8 confidence), no string parsing. Preferred for inter‑agent links and storage.
- Text (container→vector): human‑legible, LLM‑friendly, carries richer inline tokens (e.g., deliverables). Use only where an LLM must read/write the message.
- No English mirrors in machine logs (Spec §6.1). Generate human‑readable exports on demand with the translators.

## Operational Model

- Inside your fabric (no LLM token billing): prefer T9p binary (often logged as SJL‑B64). Saves bytes/latency/CPU and prevents prose from creeping in.
- LLM boundary (where tokens are billed): send compact Shimmer Text Containers (CF v2.0), not English. This is where 85–90% token savings come from.
- Human outputs: translate Shimmer → English on demand for UIs/reports; do not persist English mirrors in machine logs.

## Edge Contract & Enforcement (for external clients)

- Content‑Types your gateway accepts:
  - `application/shimmer+t9p` (binary T9p, 16‑byte packet; send as Base64 in HTTP body)
  - `application/shimmer+cf2` (strict text Container v2.0 string)
- Hard limits for `+cf2` (text):
  - Max container length ≤ 96 chars before `→`; no spaces before `→`
  - Action ∈ {`c`,`p`,`a`,`q`,`P`,`e`} (lowercase, except `P` allowed for Plan)
  - Tokens must match: `rn## | s:<base36> | s## | @s# | [fdrm]## | ctag[.:|a-zA-Z0-9_()\-]+`
  - Vector: 4–5 values; axes ≤ 1 dp; confidence ≤ 2 dp; clipped ranges
- Gateway behavior:
  - `+t9p`: Base64‑decode; length==16; unpack/validate or 400
  - `+cf2`: run compactness linter; 400 if score < 80 with `{score,issues}` JSON
  - Observability: emit `compactness_score`, `reject_count`, issue counters; include `X‑Shimmer‑Score` on success
- SDK expectation (no separate “tool”): provide a tiny pack/unpack + linter helper clients embed (10–50 LoC in Python/Node/Go). Build containers from typed tokens, never prose.
- Policy & incentives:
  - Enforce [POLICY_Compactness_v1.0.md] target ≥ 80; 429 on repeat violations
  - Prefer partners with avg score ≥ 90 (higher QPS/priority)
  - Version header: `X‑Shimmer‑Policy: compact_v1`

## Tools in This Bundle

- Translators: `tools/shimmer_cli.py`, `tools/shimmer_batch_en2sh.py`, `tools/shimmer_batch_translate.py`
- Compliance: `tools/compliance_check.py` (spec), `tools/sjl_policy_lint.py` (compactness)
- Dataset prep: `tools/build_full_corpus_manifest.py` → `data/full_corpus_ordered.jsonl`
- Standards & policy: `COMMS_STANDARD_v1.0.md`, `POLICY_Compactness_v1.0.md`

## Scope and Versioning

- Shimmer 1.0 aggregates the following stable components:
  - T9 Semantic Vector Protocol v2.0 (text form, 4D)
  - T9+ Extension v1.0 (5D with confidence)
  - Container Format v2.0 (text)
  - T9p Binary Container v1.0 (fixed 128‑bit)
  - Parity: T9+ parity (sum‑mod‑4) and proposal Parity2b (hash⊕round(vec)%4)

Experimental or proposal materials are referenced but not normative.

## Quick Start (Implementers)

1. Use T9+ (5D) by default. Quantize to 1 decimal for text; keep higher precision internally.
2. Use Container Format v2.0 for LLM‑friendly text messaging. Include temporal `τ###` when scheduling matters.
3. For ultra‑compact transport (GPU/GPU), use T9p Binary Container v1.0. Map your application’s agent IDs to the 2‑bit codepoints per session.
4. Enforce round‑trip decode (English → Shimmer → English gloss) and tolerance checks.
5. Optionally enable parity (T9+ parity or Parity2b) for basic error detection.

Human‑readable exports
- Use the included translators (see `GETTING_STARTED.md`) to convert `.shimmer` files to `.txt` for colleagues and review workflows without bloating machine logs.

## Notes on Routing/Agents

The text container uses a two‑symbol routing pair (e.g., `AB`, `γλ`). These are application‑defined identifiers, not tied to specific teams. For T9p’s 2‑bit agent fields, assign per‑session mappings (e.g., 00,01,10,11) and record them in your session registry.

## Source Index (for reference)

Key upstream files consolidated here (paths from the research repo):

- `language/specs/T9_SEMANTIC_VECTOR_PROTOCOL_v2.0.shimmer`
- `shimmer-spec/docs/T9_PLUS_SPECIFICATION_v1.0.md`
- `language/specs/CONTAINER_FORMAT_v2.0.shimmer`
- `technical/training/T9p_Binary_Container_Spec.md`
- `proposals/shimmer_spec_proposal.jsonl` (ctag, parity2b rules)

## License

This spec reflects your internal work; place under your preferred license or keep private. No new license terms are introduced by this consolidation.
