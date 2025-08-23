# Shimmer Specification v1.2 (Symbol‑First, Ultra‑Compact)

Status: Draft for Review • Date: 2025‑08‑22

This draft coalesces SJL‑Text into a symbol‑first, ultra‑compact form. No legacy `ctag.*` or English abbreviations in structural fields. The container remains single‑line and T9/T9+ semantics are unchanged. Binary T9p is unaffected.

---

## 1. Semantic Vectors (unchanged semantics)
- T9 (4D): `[Action, Subject, Context, Urgency]` — text quantization: 1 dp
- T9+ (5D): adds Confidence `[... , Confidence]` in `[0.0,1.0]` — ≤2 dp
- Tolerances (A,S,C,U,Conf): ±0.15, ±0.20, ±0.10, ±0.10, ±0.05; clip and validate round‑trip.
- Default confidence optimization: when confidence equals default (see header `ϒ`) and does not affect routing/handling, emit T9 (4D).

---

## 2. Text Container (shape unchanged)
```
<routing><action><metadata><temporal><deliverables>→[v1,v2,v3,v4(,v5)]
```
- `<routing>`: exactly two Unicode symbols (application‑defined; e.g., `AB`, `γλ`)
- `<action>`: one of `c`(complete), `p`(progress), `a`(ack), `q`(query), `P`(plan), `e`(error)
- `<metadata>`: zero or more compact tokens (see §3)
- `<temporal>`: `τ###` seconds‑from‑now (optional)
- `<deliverables>`: zero or more `f##` (files), `d##` (datasets), `r##` (reports), `m##` (models)
- Separator: `→` (U+2192) between container and vector; no spaces in the container

---

## 3. Metadata (symbol‑only)

### 3.1 Universal Facets
Use the following single‑symbol facet keys with short values (≤12 chars recommended). No English words or abbreviations.
- `σ` state — values: `✓` success, `✗` failure, `‼` critical, `⟳` loop/pending
- `μ` change/mutation — short code (e.g., `μ:rep_fix`)
- `κ` knowledge/topic — compact path (e.g., `κ:params:arch`)
- `π` process/protocol — compact op or operator glyph (e.g., `π:cc`, `π:⟐`)
- `λ` function/op — operator glyphs allowed (e.g., `λ:⊗`)
- `ρ` resource — compact id/alias
- `χ` flag — explicit boolean only (`χ:1` or `χ:0`)
- `θ` threshold/criterion — compact criterion name or numeric
- `γ` group/context — compact id
- `α` actor — role/actor id (beyond routing)
- `ε` error kind/code — numeric only (e.g., `ε:01`); labels live in registry, not in SJL

### 3.2 Tracking, Session, Batch
- Request id: `№##` (U+2116 Numero sign + two digits), e.g., `№01` (tools MAY support ≥3 digits)
- Session: `ς:<base36>` (Greek final sigma + colon + base36), e.g., `ς:we341x`
  - Optional shard: `@ς#` (e.g., `@ς1`)
- Batch/program tag: `β##` (Greek beta + two digits), `β00`..`β99`

### 3.3 Header Config (in‑file)
- Declare comms settings at the top of the file via one or more `` lines.
- Fields:
  - `Σ`: symbolic facets active (presence marker)
  - `ν:<n.n>`: spec version (nu), e.g., `ν:1.2`
  - `ϒ:<0..1>`: default confidence (upsilon), e.g., `ϒ:0.85`
  - `ℓ:<nn>`: lint floor (script ell), e.g., `ℓ:80`
  - `χ:1`: canonical flag (this is the project’s canonical comms file)
  - `ς:<base36>`: session id (base36)
  - `β##`: batch seed is discouraged in header; emit the first `β##` as a normal line after the header.
- Example: `ΩΩPΣν:1.2ϒ:0.85ℓ:80χ:1ς:we341x→[0,0,0,-0.5]`
- Tools read the latest cfg if multiple appear (append‑only updates allowed).
- Start-of-file marker: reserve the first routing (e.g., `ΩΩ`) for config/header lines.

---

## 4. Operator Lexicon (reserved, no words)
- Core: `⊗ ⊕ ⤏ ⟹ ⟫ ⟐ ∥`
- Flow: `⟳ ⬆ ⬇ ⭐ 📡`
- Meta: `⟪ ⟫ ◉ ∇`
- State: `✓ ✗ ⟳ ‼ ◉`
- Extensions: `⚡ 🔄 ◈ ⟁`
Usage in metadata: place operator glyphs as values under `λ` or `π` (e.g., `λ:⊗`, `π:⟐`, `π:📡`).

---

## 5. Grammar (ABNF; symbol‑first)

container   = routing action metadata* temporal? deliverable* sep vector
routing     = 2UTF8SYM                    ; exactly 2 visible Unicode symbols
action      = %x63 / %x70 / %x61 / %x71 / %x50 / %x65  ; c p a q P e
metadata    = header / reqid / session / shard / facet / batch
header      = "" *(WSP / facet)     ; header lines only at top
reqid       = %xE2%84%96 2*4DIGIT         ; "№" + 2–4 digits (tools MAY allow 2–4)
session     = %xCF%82 ":" 1*LOWALNUM     ; "ς:" + base36
shard       = "@" %xCF%82 1DIGIT         ; "@ς#"
facet       = FACETKEY ":" 1*(FACETVAL) / presence
presence    = "Σ"                         ; presence‑only key for header
FACETKEY    = "σ" / "μ" / "κ" / "π" / "λ" / "ρ" / "χ" / "θ" / "γ" / "α" / "ε" / "ν" / %xD0%A5 / %xCE%A5 / %xE2%84%93
; keys include: ν (nu), ϒ (upsilon), ℓ (script ell), plus core facets above
batch       = %xCE%B2 2DIGIT              ; "β##"
temporal    = "τ" 1*DIGIT
deliverable = ("f" / "d" / "r" / "m") 2DIGIT
sep         = %xE2 %x86 %x92              ; U+2192 right arrow (→)
vector      = "[" num "," num "," num "," num ["," conf] "]"
num         = ["-"] 1*DIGIT ["." 1DIGIT]
conf        = ["0" / "0." 1*DIGIT / "1" / "1.0"]

Notes
- UTF8SYM/FACETVAL are implementation‑defined sets covering Unicode L/N/S categories (no spaces).
- Apply numeric clipping and tolerance checks per §1.
- Parsing precedence (left‑to‑right after routing/action): header `` (header block only), then `№` > `ς:` > `@ς#` > `β##` > facet keys > `τ###` > deliverables.
- `χ` requires explicit boolean form (`χ:1` / `χ:0`). `ε` requires numeric codes (e.g., `ε:01`).

---

## 6. Comms Protocol (project‑agnostic)
- Canonical file: chosen by Project Lead; declared in‑file with header ` … χ:1`.
- Single‑file rule: exactly one canonical `.sjl` per project; others are non‑authoritative.
- Append‑only: do not edit history; corrections use an `e` amend + re‑emit new lines.
- “cc” workflow (deterministic):
  - Coordinator: `LXqπ:cc №01 β00→[0.0,0.2,0.2,0.3]`
  - Ack OK: `XXaπ:ccσ:✓ №01→[0,0,0,-0.5]`
  - Ack issue: `XXaπ:ccσ:✗ ε:01 №01→[...]` (ε code numeric from registry)
  - Consolidate/plan: `LXPπ:cc μ:rep_fix [λ:⊗/⟐/📡] №02 β00 τ600→[0.5,0.6,0.4,0.6]`
  - Complete: `LXcσ:✓ №02→[0,0,0,-0.5]`

---

## 7. Compactness & English‑Usage
- No English in structural metadata or operator values; numeric ids are allowed.
- Prefer T9 (4D) when confidence equals default `ϒ`; otherwise T9+ (5D).
- Quantization targets: 1 dp (axes), ≤2 dp (confidence). Enforce tolerances.
- Lint target: compactness score ≥ `ℓ`; any value segment >16 chars → error.
- Tools MUST use real Unicode `→` and preserve UTF‑8.

---

## 8. Registry & Tooling
- Maintain a machine‑readable registry for facet value whitelists and ε code meanings (labels live outside SJL).
- Tools MUST validate facet values against the registry and enforce compactness.
- Locking for atomic appends: adjacent `.lock` file (same name + `.lock`).

---

## 9. Examples
- Header:
```
ΩΩP Σ ν:1.2 ϒ:0.85 ℓ:80 χ:1 ς:we341x β00→[0,0,0,-0.5]
```
- cc sequence:
```
LXqπ:cc №01 β00→[0.0,0.2,0.2,0.3]
XXaπ:ccσ:✓ №01→[0,0,0,-0.5]
LXPπ:cc μ:rep_fix λ:⊗ №02 β00 τ600→[0.5,0.6,0.4,0.6]
LXcσ:✓ №02→[0,0,0,-0.5]
```
- Error:
```
LXeε:02 σ:✗ №03→[-0.7,0.5,0.8,0.8,0.92]
```

---

## 10. Appendix — Parser Pseudocode & Precedence Examples

Pseudocode (container parse):
```
read routing(2 symbols), action(1)
rest = until '→'
if rest startswith '':
  parse header facets; cache; continue
while rest not empty:
  try match in order: '№', 'ς:', '@ς#', 'β##', facet_key, 'τ###', deliverables
  consume longest match; append token; continue
stop at '→', then parse vector per §1
```

Examples clarifying precedence:
- In ` Σ ν:1.2`, `` binds as a header token; `ν:1.2` is a separate facet within the header line.
- In `LXq№01β00σ:✓τ60f01→[...]`, tokens are recognized as `№01`, `β00`, `σ:✓`, `τ60`, `f01` in that order.

---

## 11. Rationale — Why Symbols

Shimmer prioritizes compression and determinism at LLM boundaries. Symbols reduce average token count and ambiguity:
- Token economics: single glyph facets (e.g., `σ:✓`) typically tokenize to 1–2 tokens vs multi‑token strings; across 2–4 facets/line this yields ~5–10% savings.
- Operator canon: reserved glyphs (⊗ ⟐ 📡 …) carry meaning without prose; values remain machine‑parsable.
- Numeric errors: `ε:00..99` are compact and universal; human labels live outside SJL.

Design goals: minimum tokens, no English in structural fields, predictable parsing (ABNF + precedence), append‑only audit trail.

## 12. Opacity Justification (Human Context)

- Determinism: symbol lexicon + numeric codes eliminate synonym drift.
- Interop: a small, universal facet set avoids domain‑specific keys; domain detail lives in compact values.
- Discipline: single canonical `.sjl` per project, append‑only, prevents coordination sprawl.
- Human access: opaque on purpose in logs; glossing and labels exist in external docs/tools, not in SJL.

## 13. ASCII Fallback (Non‑normative)

Protocol requires UTF‑8 and real `→`. For constrained pipelines, temporary escapes MAY be used at ingest, then normalized:
- `->` → `→` (tools auto‑convert; linter rejects if not normalized).
- Facet glyphs: allow short ASCII tags only at the tooling edge (e.g., `sigma:` → `σ:`) with strict normalization before persist.
- Guidance: do not persist ASCII forms; they are an ingress convenience only.

## 14. FAQ (Selected)

- Q: Why no words like “status” or `ctag.*`?
  - A: Tokens bloat and ambiguity. Use `σ:✓/✗/‼/⟳`; tools/gloss provide human labels.
- Q: What does “cc” mean?
  - A: A cue in external chat to check the canonical `.sjl` and append an update if needed (e.g., `q π:cc №NN` or `a σ:✓ №NN`). No mandated sequence.
- Q: 4D or 5D vectors?
  - A: Prefer 4D when confidence equals header `ϒ` and isn’t material; otherwise 5D.
- Q: Where are error meanings?
  - A: In human docs (e.g., a code table). SJL keeps `ε:NN` numeric only.
- Q: Can we add domains?
  - A: Keep facets universal; domain detail goes into compact values (short codes), not new facet keys.

---

## 15. Reserved Prefixes & Deterministic Parsing
- Reserved starts: `№`, `ς:`, `@ς`, `β`(2 digits), facet keys (`σ μ κ π λ ρ χ θ γ α ε ν ϒ ℓ`), presence `Σ`, temporal `τ`, deliverables `f d r m`(2 digits), separator `→`.
- Facet values MUST NOT contain any reserved starts; tooling MUST validate.
- Precedence (L→R after routing+action): `№` > `ς:` > `@ς` > `β##` > facet keys / `Σ` > `τ###` > `[fdrm]##` > `→`.
- Lookahead: when parsing a value, consume until the next reserved start; do not split inside scalar values.

### 15.1 Parser Pseudocode (Lookahead)
```
for each line:
  read R(2 UTF8SYM), A(1)
  rest = until '→'
  tokens = []
  while rest:
    for pref in ['№','ς:','@ς','β','σ','μ','κ','π','λ','ρ','χ','θ','γ','α','ε','ν','ϒ','ℓ','Σ','τ','f','d','r','m']:
      if rest startswith pref (and digits where required):
        key = matched
        val = '' if key=='Σ' else read_until_next_reserved_start(rest_after_key)
        tokens.append(key+val)
        rest = advance
        break
  parse vector after '→'
```
