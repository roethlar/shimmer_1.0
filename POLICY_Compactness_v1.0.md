# Shimmer Compactness & English‑Usage Policy v1.0

Purpose: maximize token savings and enforce protocol discipline in production.

## Rules (Machine Channels)
- No English mirrors; Shimmer only (Spec §6.1).
- Action codes: lowercase from {c,p,a,q,P,e} (P allowed as Plan per v2.0).
- Tokens compactness:
  - Prefer typed tokens: `rn##`, `s:<base36>`, `f##/d##/r##/m##`, `ctag.*`
  - Avoid natural language phrases in metadata (e.g., long underscore/word blobs).
  - Use `ctag.*` for concepts (halluc.traits, book_only) instead of prose.
- Vector quantization (text): 1 dp for first 4 axes; ≤2 dp for confidence; clip ranges.

## Scoring (Lint Target ≥ 80)
- Start 100; subtract:
  - −20 if any English spaces appear before `→`
  - −10 per token > 24 chars of continuous letters/underscores
  - −10 if action code invalid/not lowercase (except `P`)
  - −5 if any of the first 4 axes use >1 dp; −3 if confidence >2 dp
  - −5 if missing typed tokens where obvious (e.g., uses long prose instead of `ctag.*`)

## Enforcement
- CI/agent pre‑send hook: reject lines scoring < 80; log issues.
- Observability: emit compactness score distribution per session; alert on drift.
- Exceptions: allow SJL‑Text for human‑debug channels; still apply compactness scoring.

## Examples
- Verbose (reject):
  - `λνeskippymodelfilehallucinated_personalitynotfrombooksrequirebookbasedtraits→[…]`
- Compact (accept):
  - `λνeskippyrn03m01ctag.halluc.traitsctag.book_only→[…]`

Adopt this policy alongside Spec v1.0 to keep Shimmer’s compression advantage.

