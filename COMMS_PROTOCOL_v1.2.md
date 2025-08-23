# Comms Protocol v1.2 (Strict, Single-File, Symbol-First)

Status: Draft for Review • Date: 2025‑08‑22

Purpose: Define one strict, universal protocol for team coordination using a single SJL‑Text file with symbol‑only metadata (v1.2). This removes ambiguity, prevents file sprawl, and binds “cc” to a deterministic update workflow.

---

## 1) Canonical File (Single Source of Truth)
- Canonical Path: defined per‑project by the Project Lead in a repo config (see §2.1).
- Single‑File Rule: This is the only `.sjl` allowed for team coordination in this project.
  - Any other `*.sjl` in the project is non‑authoritative and MUST NOT be used for coordination.
- Append‑Only: New lines are appended. Historical edits are forbidden except via an explicit amend entry (see §5.3).
- Rotation: None by default. If needed, rotate only via an explicit `e` line declaring the new canonical path and timestamp; close with a final `c` line, then switch.

---

## 2) File Structure & Required Header
- 2.1 Project Config (required): create `COMMS.yaml` at repo root:
  ```yaml
  comms:
    canonical_file: path/to/<project>_comms.sjl
    lock_file: path/to/<project>_comms.sjl.lock
    allow_other_sjl: false
    lint_min_score: 80
    facets_registry: Spec_1.2_working/facets_registry.yaml
  ```
  - Project Lead is the owner of this file and the canonical path.
  - CI and hooks read this file to enforce single‑file and append‑only gates.

- Encoding: UTF‑8. Use real `→` (U+2192). No spaces in the container segment.
- Header (first lines of the file or after a rotation):
  1. Session: `ς:<base36>` (e.g., `ς:we341x`).
  2. Capabilities (one line): `Σ ν:1.2 ϒ:0.85 ℓ:80 χ:1`.
  3. Batch seed (optional): `β00` reserved for daily/phase program.
- All subsequent lines follow SJL‑Text with symbol‑only facets per v1.2 spec.

---

## 3) Routing & Roles
- Routing: first 2 symbols are application‑defined agent/role pairs (e.g., `LX`, `AB`). Maintain a local mapping in docs or code, but do not expand in the comms file.
- Action codes: `c` complete, `p` progress, `a` ack, `q` query, `P` plan, `e` error.

---

## 4) “cc” (cue)
- On “cc” in external channels, agents SHOULD check the canonical .sjl and append an update if needed (e.g., rr q π:cc №NN→[0.0,0.2,0.2,0.3] or rr a σ:✓ №NN→[0,0,0,-0.5]).


---

## 5) Authoring Rules (Hard Requirements)
5.1 Symbol‑Only Metadata
- Allowed facets: `σ μ κ π λ ρ χ θ γ α ε` (see v1.2 spec and registry).
- Examples: `σ:✓ μ:rep_fix κ:params:arch`.

5.2 Tracking, Session, Batch, Caps
- Request id: `№##` (e.g., `№01`).
- Session: `ς:<base36>` (e.g., `ς:we341x`), optional shard `@ς#`.
- Batch/program: `β##` (e.g., `β03`).
- Capabilities: `ξ.*` tokens appear in the header (session start) and SHOULD NOT repeat.

5.3 Amendments (Historical Corrections)
- Do not edit prior lines. Instead append:
  - `ABeε:amend №old ρ:<ref> → [...]` followed by the corrected line(s) re‑emitted with the new `№new`.
- Keep amendments rare; prefer accurate first‑write.

5.4 Compactness & T9
- Prefer T9 (4D) when confidence equals default (e.g., 0.85); otherwise T9+ (5D).
- Quantization: 1 dp for axes; ≤2 dp for confidence. Clip to valid ranges.
- Lint target ≥80; any value segment >16 chars → error.

---

## 6) Enforcement & Tooling
- Single‑File Gate: CI/guard hooks MUST block changes to any `*.sjl` except the canonical path.
- Append‑Only Gate: Reject diffs that modify or delete existing lines in the canonical file (except a rotation close/open block).
- Facet Registry Check: Validate facet keys and values against `Spec_1.2_working/facets_registry.yaml`.
- Vector Lint: Enforce quantization, ranges, and tolerance checks; require `→` Unicode arrow.
- Locking: Implement a simple lock file next to the canonical file (same name + `.lock`) for atomic append. Hold ≤ 10s, retry with backoff.

---

## 7) Examples
- Check‑in trigger:
```
LXqπ:cc№01 β00→[0.0,0.2,0.2,0.3]
```
- Ack OK:
```
XXaπ:ccσ:✓ №01→[0,0,0,-0.5]
```
- Consolidated plan with deadline:
```
LXPπ:ccμ:rep_fix κ:next №02 β00 τ600→[0.5,0.6,0.4,0.6]
```
- Error report:
```
LXeε:invalid_state σ:✗ №03→[-0.7,0.5,0.8,0.8,0.92]
```

---

## 8) Best Practices (Non‑normative)
- Start‑of‑Day: Append header lines (session + `ξ.*`) and seed `β00`.
- During Work: Append progress (`p`), plans (`P`), queries (`q`), acks (`a`), errors (`e`), completes (`c`).
- Check‑Ins: On “cc”, execute §4 workflow. Repeat as needed (hourly or ad‑hoc).
- Close‑Out: Append `c` lines for finishes; consider a daily `c` summary line.

---

## 9) Migration & Cleanup
- Archive or delete stray `*.sjl` files; they are non‑authoritative.
- Configure tooling to reject modifications outside the canonical file.
- If a new canonical file is needed, rotate via §1 and update/docs/scripts accordingly.


---

## 10) Rotation Example (Canonical Path Change)
- Close current file with an amend line and declare the new path in a comment channel outside SJL. Then open the new file with a fresh header.
- Example amend in old file:
```
ΩΩeε:09 №99→[0,0,0,0]
```
- First lines in new file:
```
ΩΩPπ:cfg Σ ν:1.2 ϒ:0.85 ℓ:80 χ:1 ς:new001→[0,0,0,-0.5]
LXqπ:cc №01→[0.0,0.2,0.2,0.3]
```

## 11) Amend Example (Historical Correction)
- Do not edit history. Append an amend + corrected line:
```
LXeε:08 №07→[0,0,0,0]
LXcσ:✓ №08→[0,0,0,-0.5]
```
