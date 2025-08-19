# Shimmer 1.1 — Getting Started (For Humans)

This folder contains a ready‑to‑use prompt, a tiny CLI, and a validator so anyone can try Shimmer quickly.

- Unified spec: `Shimmer_Spec_v1.1.md`
- Prompt template: `LLM_Prompt_Template.md`
- CLI: `tools/shimmer_cli.py`
- Validator: `tools/compliance_check.py`

What it does
- English → Shimmer: turns plain English into a compact Shimmer line like `ABPrn02τ1800d03→[0.5,0.6,0.5,0.9,0.92]`. In v1.1, “Human‑First Authoring” adds defaults/inference so unconstrained inputs map reliably to valid containers.
- Shimmer → English: explains a Shimmer line in simple JSON.
- Validate: checks a Shimmer line’s format, ranges, and quantization.

## 1) Quick Demo (Local Model via Ollama)

Prereqs
- Install Ollama (https://ollama.com) and start it (default: http://localhost:11434)
- Pull a good default model once: `ollama pull qwen2.5:latest`

English → Shimmer
```
python3 tools/shimmer_cli.py en2sh "Plan dataset 03 in 30 minutes" \
  --provider ollama --model qwen2.5:latest --routing AB --deadline 1800
```
You should see a single line like:
```
ABPrn02τ1800d03→[0.5,0.6,0.5,0.9,0.92]
```

Shimmer → English (gloss)
```
python3 tools/shimmer_cli.py sh2en "ABPrn02τ1800d03→[0.5,0.6,0.5,0.9,0.92]" \
  --provider ollama --model qwen2.5:latest
```
Returns a short JSON explaining routing, action, deadline, deliverables, and the numbers.

Validate the line
```
python3 tools/compliance_check.py "ABPrn02τ1800d03→[0.5,0.6,0.5,0.9,0.92]"
```
This prints OK or errors and a summary.

Tips
- Routing can be any two symbols (e.g., `AB`, `XY`).
- Use the real Unicode arrow `→` (not `->`).
- It’s fine if the model outputs extra decimals — the validator warns but won’t block.
- Glossing note (v1.1): `routing` is exactly the first two symbols of the container.

## 2) Using an API Model (OpenAI‑compatible)

Set your key
```
export OPENAI_API_KEY=sk-...
```
Run the same commands with `--provider openai --model gpt-4o-mini`:
```
python3 tools/shimmer_cli.py en2sh "Plan dataset 03 in 30 minutes" \
  --provider openai --model gpt-4o-mini --routing AB --deadline 1800

python3 tools/shimmer_cli.py sh2en "ABPrn02τ1800d03→[0.5,0.6,0.5,0.9,0.92]" \
  --provider openai --model gpt-4o-mini
```

## 3) What Is “Binary” and When Do I Need It?

- The text line (above) is human‑readable and perfect for logs and debugging.
- The binary form is a tiny 16‑byte packet that packs the 5 numbers and minimal metadata (sender/receiver codes, session, priority, timestamp).
- It’s the same meaning, just smaller and not human‑readable.

Prefer binary when
- Links are bandwidth‑constrained (robots, radios, inter‑GPU links) or you need very low latency.
- Only machines will read the messages.

Prefer text when
- Humans read logs, you’re prototyping, or sharing with colleagues.

How text ↔ binary relates
- You can convert between them without losing meaning (see the unified spec §4 for exact binary layout).
- For text channels, the binary is usually Base64‑encoded.

Translators for humans
- Do NOT include English mirrors in machine logs. When people need to read content, generate an English export on demand with the translators below.
- Text `.shimmer` files → English `.txt`: use the batch translator in §7.
- Base64 (SJL‑B64) streams: first decode to a text container using your T9p tools (see shimmer‑lang `tools/t9p_codec.py`), then run the glossing translator.

## 4) Inter‑Agent Comms (shared.json‑style)

The existing `shared.json` pattern (see `technical/training/comms.py`) logs messages like:
```json
{
  "id": "m-1a2b3c4d",
  "ts": 1723920000,
  "from": "Nova",
  "to": "Lux",
  "channel": "coord",
  "msg": "ABPrn02τ1800d03→[0.5,0.6,0.5,0.9,0.92]",
  "status": "sent"
}
```
This is great for the control plane and human visibility. To add binary for data‑plane efficiency:

Recommended fields
- Keep `msg` as the Shimmer text line for logs/debugging.
- Add `msg_b64` for the T9p binary (Base64 string), plus optional `parity` info.
- Optionally add `meta`: `{ "session_id": 12345, "priority": 10, "ts": 1723920000, "from_code": 2, "to_code": 0 }` if you map agent codes.

Example (augmented)
```json
{
  "id": "m-1a2b3c4d",
  "ts": 1723920000,
  "from": "Nova",
  "to": "Lux",
  "channel": "coord",
  "msg": "ABPrn02τ1800d03→[0.5,0.6,0.5,0.9,0.92]",
  "msg_b64": "Wl8KUGIC...",
  "parity": { "t9": 2, "p2b": 1 },
  "status": "sent"
}
```

Agent codes
- The binary container uses 2‑bit IDs (4 codes total). Assign codes per session (e.g., 00,01,10,11) and record them in a small registry so both sides agree.
- In text, use any two symbols (e.g., `AB`). Map `AB` ↔ (from_code,to_code) in your session registry.

Transport
- For machine‑to‑machine links, send the Base64 binary (`msg_b64`).
- For dashboards/logs, display `msg` (text line) so humans can read it.

Validation
- Always validate text messages with `tools/compliance_check.py`.
- Optionally compute parity (vector parity or Parity2b) and log it to catch corruption.

## 5) Do We Have a Simple Translator Already?

Yes. The CLI is the simple translator:
- `tools/shimmer_cli.py en2sh ...` returns a Shimmer line (English → Shimmer)
- `tools/shimmer_cli.py sh2en ...` returns a compact JSON gloss (Shimmer → English)
- `tools/compliance_check.py` validates a Shimmer line

Advanced usage (later)
- We can add a `--binary` flag to emit/consume Base64 T9p packets alongside the text line, for easy round‑trip tests.

## 6) Where To Read More

- Unified spec: `Shimmer_Spec_v1.1.md` (vectors, container grammar, binary layout, parity, tolerances, and human‑first authoring defaults)
- Prompt template: `LLM_Prompt_Template.md` (copy/paste into any model)
- Validator: `tools/compliance_check.py` (ensures basic compliance)

If you need the binary helper next, tell us and we’ll wire a `--binary` option into the CLI to produce/parse Base64 packets automatically.

## 7) Batch Translation (Files)

Translate a whole English `.txt` to a `.shimmer` file (one message per line):
```
python3 tools/shimmer_batch_en2sh.py --in in.txt --out out.shimmer \
  --provider ollama --model qwen2.5:latest --routing AB --action auto
```

Translate a `.shimmer` file (text lines) to an English `.txt` (one paragraph per line):
```
python3 tools/shimmer_batch_translate.py --in in.shimmer --out out.txt \
  --provider ollama --model qwen2.5:latest
```

Notes
- Use `--provider openai --model gpt-4o-mini` (with `OPENAI_API_KEY`) if you prefer an API model.
- Keep each English line to one coherent request; blank lines are preserved.
- If your `.shimmer` file has Base64 T9p lines, decode them to text containers first (see §3 and shimmer‑lang `tools/t9p_codec.py`).
