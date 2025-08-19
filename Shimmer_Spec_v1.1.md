# Shimmer Specification v1.1 (Unified)

Status: Production • Date: 2025‑08‑19

This document updates v1.0 with human‑first authoring defaults and clarifications while preserving the core protocol:
- T9 Semantic Vector Protocol v2.0 (4D)
- T9+ Extension v1.0 (5D with Confidence and optional parity)
- Container Format v2.0 (text)
- T9p Binary Container v1.0 (fixed 128‑bit)
- Calibration, tolerances, round‑trip validation, and Genesis onboarding

New in v1.1 (summary)
- Human‑First Authoring (Defaults & Inference) for robust English → Shimmer mapping
- Glossing clarification: routing is exactly the first two symbols

---

## 1. Semantic Vectors

### 1.1 T9 (4D)
- Dimensions: `[Action, Subject, Context, Urgency]`
- Range: each in `[-1.0, +1.0]`
- Text form: `[a, b, c, d]` (recommended 1 decimal; higher internal precision allowed)
- JSON form: `{ "action": a, "subject": b, "context": c, "urgency": d }`

Anchors (illustrative):
- Action: −1.0 diagnosis • −0.5 analysis • 0.0 observe • +0.5 plan • +1.0 execute
- Subject: −1.0 people • −0.5 org/admin • 0.0 mixed • +0.5 technical • +1.0 specialized systems
- Context: −1.0 personal/internal • −0.5 problem/error • 0.0 neutral • +0.5 professional • +1.0 external/public
- Urgency: −1.0 routine • −0.5 deadline • 0.0 neutral • +0.5 timely • +1.0 critical

### 1.2 T9+ (5D)
- Adds Confidence dimension: `[Action, Subject, Context, Urgency, Confidence]`
- Confidence range: `[0.0, 1.0]`
- Text form: `[a, b, c, d, e]`
- JSON form: `{ "action": a, "subject": b, "context": c, "urgency": d, "confidence": e }`

### 1.3 Quantization and Precision
- Transmission quantization (text): 1 decimal place recommended
- Binary quantization (see §4): int16 for first 4 axes (mapped from `[-1.0, +1.0]`), uint8 for confidence `[0.0, 1.0]`
- Always clip to valid ranges after processing

### 1.4 Calibration & Tolerances (Required)
- Tolerance ranges:
  - Action ±0.15, Subject ±0.20, Context ±0.10, Urgency ±0.10, Confidence ±0.05
- Aggregation: mean with clipping to range
- Validation: perform round‑trip decode (encode→transmit→decode→compare) and log deviations beyond tolerance

### 1.5 Parity (Optional)
- T9+ Parity: `sum(round(10*axes) + round(100*conf)) % 4`
- Parity2b (proposal): `(hash(container_text) ⊕ sum(round(vector_components))) % 4`
- Use as a lightweight transmission error detector; do not treat as cryptographic integrity

### 1.6 Genesis Onboarding (Recommended)
- New instances broadcast a Genesis vector requesting calibration
- Peer responds with the calibration table
- New instance initializes and acknowledges ready state
- Secure with authentication and rate limiting

---

## 2. Text Container Format v2.0

### 2.1 Structure (no spaces)
```
<routing><action><metadata><temporal><deliverables>→[v1,v2,v3,v4(,v5)]
```
- `<routing>`: 2 symbol agent pair (application‑defined; e.g., `AB`, `γλ`)
- `<action>`: one of `c`(complete), `p`(progress), `a`(ack), `q`(query), `P`(plan), `e`(error)
- `<metadata>`: zero or more tokens (order stable; compact, dotted/colon as needed)
- `<temporal>`: `τ###` seconds‑from‑now (optional)
- `<deliverables>`: zero or more `f##` (files), `d##` (datasets), `r##` (reports), `m##` (models)
- Separator: `→` (U+2192) between container and vector; do not use ASCII `->` nor the literal string `u2192`

### 2.2 Metadata Tokens
- Request tracking: `rn##` (e.g., `rn01`)
- Session ID: `s####` or `s:<base36>` (e.g., `s:we341x`), optional shard: `@s#`
- CTag enrichers (proposal set): `ctag.*` (e.g., `ctag.v1`, `ctag.dom:personal`, `ctag.topic:party`)

Rules: compact, no spaces, dot/colon delimiters, stable token ordering.

### 2.3 Temporal Encoding
- `τ###` denotes deadline seconds from now (e.g., `τ300` = 5 minutes)
- Range: `τ1` … `τ999999`

### 2.4 Examples
- Basic: `ABPrn01τ300f06→[0.5,0.9,0.1,0.9,0.96]`
- Enriched: `ABpctag.v1 s:we341x@s1 d03τ1800→[0.4,0.8,0.5,0.5,0.93]`

### 2.5 Grammar (informal)
- routing: two visible symbols (letters/Greek/etc.)
- action: one of {`c`,`p`,`a`,`q`,`P`,`e`}
- metadata: (`rn[0-9]+` | `s:[a-z0-9]+` | `s[0-9]+` | `@s[0-9]+` | `ctag[.:|a-z0-9_()-]+`)*
- temporal: `τ[0-9]+` (optional)
- deliverables: (`[fdrm][0-9][0-9]`)*
- vector: bracketed decimals with comma separators, 4 or 5 components

### 2.6 Routing/Agents (Scalability Guidance)
- Text routing identifiers are application‑defined; choose any two symbols per agent and maintain a registry in your system
- Do not hard‑code specific team names; avoid assumptions beyond “two‑symbol identifier per agent”
- For large deployments use a mapping service to resolve routing symbols to endpoints

---

## 3. English ↔ Shimmer Mapping

### 3.1 English → Shimmer (Authoring)
- Prefer T9+ (5D). Quantize text to 1 dp (axes) and ≤2 dp (confidence).
- Include `τ###` when scheduling; add deliverables `f##/d##/r##/m##` only when explicitly present.
- Use compact `ctag.*` enrichers for domain/topic instead of prose.
- Validate via round‑trip checks and tolerances (§1.4).

### 3.2 Shimmer → English (Glossa)
- Parse container: routing, action, metadata, temporal, deliverables
- Parse vector: 4D/5D; clip to ranges; map to anchors; explain concisely
- Routing for glossa: exactly the first two symbols of the container
- Validate parity (if present) and report discrepancies

### 3.3 Round‑Trip Validation (Required)
- Implement an RTD check: English → Shimmer → English gloss
- Ensure deviations are within tolerance (see §1.4)

### 3.4 Human‑First Authoring (Defaults & Inference) — v1.1
When humans provide unconstrained English, apply the following deterministic defaults and inference rules to produce a valid text container:

- Routing: use application default if unspecified (e.g., `AB`).
- Action inference:
  - `a` (ack): phrases like “ok, got it, thanks, received”.
  - `q` (query): interrogatives; status checks; “is … available?”.
  - `P` (plan): tasks/requests: “plan/prepare/schedule/generate/make/do/write…”.
  - `p` (progress): updates: “progress/at X%/ongoing/monitor/working on…”.
  - `c` (complete): “done/completed/finished/closed”.
  - `e` (error): “failed/error/critical/urgent/sev…”.
- Temporal `τ###`: extract relative times like “in 2 hours”→`τ7200`; “within 5 minutes”→`τ300`. If not reliably extractable, omit.
- Deliverables: include only when explicitly present and numbered (`f##/d##/r##/m##`).
- Session & tags: prefer compact tags over prose: `s:<base36>` if a session is mentioned; `ctag.dom:<domain>` and `ctag.topic:<topic>` from short noun phrases.
- Vector (T9+): infer from verbs/tonality/domain/urgency words; quantize axes to 1 dp and confidence to ≤2 dp; clip to ranges. Default confidence 0.85 if unstated.
- Compactness: container has no spaces; use real Unicode arrow `→`.

These rules are normative for v1.1 authoring behavior.

---

## 4. T9p Binary Container v1.0 (128‑bit)

### 4.1 Layout

| Field              | Bits | Notes |
|--------------------|------|-------|
| from_agent         | 2    | 2‑bit code; app‑defined mapping per session |
| to_agent           | 2    | 2‑bit code; app‑defined mapping per session |
| session_id         | 16   | Unsigned session counter/ID |
| priority           | 4    | Unsigned (0–15) |
| timestamp          | 32   | Unix seconds |
| vector_action      | 16   | int16 from `round(a * 32767)` |
| vector_subject     | 16   | int16 from `round(b * 32767)` |
| vector_context     | 16   | int16 from `round(c * 32767)` |
| vector_urgency     | 16   | int16 from `round(d * 32767)` |
| vector_confidence  | 8    | uint8 from `round(e * 255)` |

Total: 128 bits (16 bytes)

### 4.2 Encoding/Decoding
- Map agents to 2‑bit codes per session (00,01,10,11). Maintain a session registry externally.
- Quantize vectors as defined above; clip on decode to valid ranges.
- Optional Base64 wrapper for transport.

### 4.3 Text/Binary Bridge
- Text routing IDs are unconstrained; binary uses 2‑bit codes. Bridge via your registry.
- For >4 agents, use hub/gateway routing or text containers for addressing and binary for constrained links.

---

## 5. Parity & Error Handling
- T9+ parity (vector‑only) and Parity2b (container‑hash XOR vector) are supported as lightweight checks.
- On parity mismatch: request retransmission or fall back to text container representation for debugging.
- On validation failure (tolerance exceeded): trigger calibration refresh via Genesis, or fall back to T6/symbolic control plane.

---

## 6. Security & Onboarding
- Authenticate Genesis onboarding and rate‑limit broadcasts.
- Maintain a calibration table shared by participants; version it and rotate as needed.
- Log RTD metrics and parity events for audit.

---

## 6.1 Production Rule: No Plain‑English Duplication
- In production comms and logs that may be processed by models, do not include human‑readable (English) duplicates of Shimmer messages.
- All inter‑agent content MUST be in Shimmer format (text container or binary T9p). English is produced only on demand via the translator tooling.

---

## 7. Examples

### 7.1 Planning with Deadline (Text)
```
ABPrn02τ1800d03→[0.5,0.6,0.5,0.9,0.92]
```

### 7.2 Acknowledgement with File (Text)
```
XYaf01→[0.0,0.0,0.0,-0.5,0.85]
```

### 7.3 Human‑First Authoring Examples (v1.1)
```
ABqctag.dom:personalctag.topic:relationships→[0.0,-0.6,-0.6,0.1,0.9]
ABqctag.dom:healthctag.topic:headache→[-0.2,-0.4,-0.6,0.5,0.85]
ABPctag.dom:personalctag.topic:partyτ180000→[0.5,-0.5,0.2,0.6,0.9]
```

---

## 8. Versioning & Compliance
- This document is Shimmer v1.1. See CHANGELOG.md for differences from v1.0.

