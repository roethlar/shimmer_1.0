# Shimmer Comms Standard v1.0 (SJL — Shimmer Journaling Lines)

Goal: standardized, minimal‑overhead files for multi‑agent setups without bespoke transports.

Two production formats (pick one per system):

## 1) SJL‑B64 (Recommended for Production)
- One Base64 line per message, where the content is a 16‑byte T9p binary container.
- Example line (24 chars typical):
```
Wl8KUGICmJ0wEAAAQkAAAGYAAABg8w==
```
- Advantages: smallest text representation; includes sender/receiver codes, session_id, priority, timestamp, and the 5D vector.
- Reader/writer must maintain a per‑session map from routing symbols (e.g., `AB`) to 2‑bit codes (0..3). Store that map in a small sidecar file if needed.
- No English, no JSON keys, no extra whitespace.

## 2) SJL‑Text (For LLM Text Channels Only)
- One line per message using the canonical text container:
```
<routing><action><metadata><temporal><deliverables>→[v1,v2,v3,v4(,v5)]
```
- Use only when you need to keep content consumable by LLMs in plain text; still no English duplication.

## Rules (Both Formats)
- One message per line, newline‑delimited.
- No plain‑English mirrors in these logs (see Spec §6.1). Use the translator to produce English off‑band when required.
- If you need additional metadata (e.g., deliverables) with SJL‑B64, store it in a compact sidecar file keyed by (session_id, timestamp) or use SJL‑Text for those messages.

## Agent/Session Mapping
- Maintain a tiny registry per session to map routing symbols ↔ 2‑bit codes for T9p:
```
{ "session": 12345, "codes": { "A": 0, "B": 1, "C": 2, "D": 3 } }
```
- The text routing pair `AB` maps to (from_code=0, to_code=1) when packing to T9p.
- Rotation: new sessions can use different mappings without affecting old logs.

## File Rotation and Concurrency
- Append‑only, newline‑terminated writes.
- Use file locks or a single writer task if multiple agents share one file.
- Rotate files by size or time (e.g., 100 MB or hourly) to keep tailing cheap.

## Suggested Filenames
- `coord.sjl` — control/coordination plane (text or b64)
- `data.sjl` — data plane (b64 preferred)
- `errors.sjl` — errors/alerts (text ok for quicker human inspection)

## Minimal Tools (next)
- `tools/sjl_pack.py` — pack/unpack T9p containers and output/read SJL‑B64 lines
- `tools/sjl_tail.py` — tail and decode for operators (no English unless explicitly requested)

This standard replaces ad hoc JSONL logs for inter‑agent messaging where possible, preserving Shimmer’s compression advantage.

