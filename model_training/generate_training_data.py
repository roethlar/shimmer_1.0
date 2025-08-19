import subprocess
import os
import json
import re
import argparse
import openai
import google.generativeai as genai

# --- Configuration ---
PROMPTS_FILE = "prompts.txt"
TRAINING_FILE = "training_data.jsonl"

# --- LLM Configuration ---
# Supported providers: "openai", "google", "anthropic"
LLM_PROVIDER = "google"
LLM_MODEL = "models/gemini-2.5-pro"
OPENAI_MODEL_DEFAULT = "gpt-4o"
GOOGLE_MODEL_DEFAULT = "gemini-2.5-flash"
ANTHROPIC_MODEL_DEFAULT = "claude-opus-4-1-20250805"

# --- System Prompts ---
EN2SH_SYSTEM_PROMPT = r"""You are a protocol agent. Follow Shimmer Spec v1.1. Output EXACTLY one line: <routing><action><metadata><temporal><deliverables>→[a,b,c,d,e]. No other text.

Container (CF v2.0)
- No spaces in container; use real Unicode arrow → (U+2192)
- routing: exactly two symbols (e.g., AB, XY, γλ)
- action: one of c (complete), p (progress), a (ack), q (query), P (plan), e (error)
- metadata tokens (optional): rn## | s#### | s:<base36> | @s# | ctag[.:|a-zA-Z0-9_()\-]+
- temporal (optional): τ### (deadline seconds‑from‑now)
- deliverables (optional, repeatable): f## | d## | r## | m##

Vector (T9+, 5D)
- [Action, Subject, Context, Urgency, Confidence]
- Ranges: first 4 ∈ [-1.0,+1.0], Confidence ∈ [0.0,1.0]
- Quantize text: 1 dp for first 4; ≤2 dp for confidence; clip to ranges

Human‑First Defaults (v1.1)
- Action inference: a=ack phrases; q=questions/status; P=tasks/requests; p=updates; c=done; e=errors/failures/alerts
- Temporal: extract relative times (e.g., “in 2 hours”→τ7200). If unclear, omit τ
- Deliverables: include only explicit numbered items (f##/d##/r##/m##)
- Tags/session: use compact `ctag.dom:*`, `ctag.topic:*`, `s:<base36>`, optional `@s#` when implied by the text
- Vector: infer from verbs/domain/tonality/urgency; default confidence 0.85 if not stated

Strictness
- One line only; no markdown/code fences; no commentary

Examples
XYaf07→[0.0,0.2,0.0,0.1,0.95]
ABPrn02τ1800d03→[0.5,0.6,0.5,0.9,0.92]
XYqrn42→[0.0,0.5,0.0,0.1,0.90]
"""

SH2EN_SYSTEM_PROMPT = r"""You are a protocol agent. Read a Shimmer text container and vector, then return a compact JSON object.

Parsing rules (v1.1):
- routing: exactly the first two symbols of the container (e.g., 'XY', 'γλ')
- action: one of c,p,a,q,P,e; include code and short meaning
- metadata: list all non‑deliverable tokens (rn##, s#### or s:<base36>, @s#, ctag.*)
- deadline_seconds: integer from τ### if present; else null
- deliverables: list deliverable tokens only (f##, d##, r##, m##)
- vector_gloss: short summary of [Action, Subject, Context, Urgency, Confidence]
- one_paragraph_summary: 1–2 sentences in plain English

Return ONLY JSON with keys: routing, action, metadata, deadline_seconds, deliverables, vector_gloss, one_paragraph_summary. No markdown.
"""


def _normalize_shimmer(text: str) -> str:
    """Make small, safe normalizations to model output.
    - Replace arrow variants with the Unicode arrow
    - Remove spaces on the container side (left of the arrow)
    - Strip simple code fences
    """
    if not text:
        return text
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        s = s.replace("json\n", "").replace("JSON\n", "")
    s = s.replace("u2192", "→").replace("\\u2192", "→").replace("->", "→")
    if "→" in s:
        left, right = s.split("→", 1)
        s = f"{left.replace(' ', '')}→{right.strip()}"
    return s


def _extract_json_braces(text: str) -> str:
    if not text:
        return text
    m = re.search(r"\{[\s\S]*\}", text)
    return m.group(0) if m else text.strip()

def get_google_completion(user_prompt, system_prompt):
    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError("GOOGLE_API_KEY not set.")
    try:
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        config = genai.types.GenerationConfig(temperature=0.1)
        model = genai.GenerativeModel(LLM_MODEL, system_instruction=system_prompt, generation_config=config)
        response = model.generate_content(user_prompt)
        if getattr(response, "text", None):
            return response.text.strip()
        raise RuntimeError(f"Empty response. Feedback={getattr(response, 'prompt_feedback', None)}")
    except Exception as e:
        raise RuntimeError(f"Google API error: {e}")

def get_openai_completion(user_prompt, system_prompt):
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY not set.")
    client = openai.OpenAI()
    # Try Chat Completions with new param, then old, then Responses API
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            max_completion_tokens=200,
            temperature=0,
        )
        return response.choices[0].message.content.strip()
    except Exception as e1:
        msg = str(e1)
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                max_tokens=200,
                temperature=0,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            # Responses API as final fallback
            try:
                resp = client.responses.create(
                    model=LLM_MODEL,
                    input=f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{user_prompt}",
                    max_output_tokens=200,
                    temperature=0,
                )
                if hasattr(resp, "output_text") and resp.output_text:
                    return resp.output_text.strip()
                parts = getattr(resp, "output", []) or getattr(resp, "content", [])
                buf = []
                for p in parts:
                    items = getattr(p, "content", []) if hasattr(p, "content") else [p]
                    for it in items:
                        t = getattr(it, "text", None) or (it.get("text") if isinstance(it, dict) else None)
                        if t:
                            buf.append(t)
                if buf:
                    return "".join(buf).strip()
            except Exception as e3:
                raise RuntimeError(f"OpenAI API error: {msg} / fallback: {e3}")

def get_anthropic_completion(user_prompt, system_prompt):
    # Optional dependency; skip if not available
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set.")
    try:
        import anthropic  # type: ignore
    except Exception as e:
        raise RuntimeError(f"anthropic SDK not installed: {e}")
    client = anthropic.Anthropic()
    try:
        resp = client.messages.create(
            model=LLM_MODEL,
            max_tokens=200,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # content is a list of blocks
        if getattr(resp, "content", None):
            blocks = resp.content
            txt = "".join([b.text for b in blocks if getattr(b, "type", "") == "text"]) or str(blocks[0])
            return txt.strip()
        return ""
    except Exception as e:
        raise RuntimeError(f"Anthropic API error: {e}")


def _looks_valid_shimmer(s: str) -> bool:
    if not s or "→" not in s:
        return False
    left, right = s.split("→", 1)
    if " " in left:
        return False
    right = right.strip()
    if not (right.startswith("[") and right.endswith("]")):
        return False
    try:
        parts = [x.strip() for x in right[1:-1].split(",") if x.strip()]
        if len(parts) != 5:
            return False
        _ = [float(x) for x in parts]
    except Exception:
        return False
    return True

def main():
    global LLM_MODEL
    parser = argparse.ArgumentParser(description="Generate Shimmer training data.")
    parser.add_argument("--test", action="store_true", help="Run with only the first prompt.")
    args = parser.parse_args()

    if not os.path.exists(PROMPTS_FILE): exit(f"Error: '{PROMPTS_FILE}' not found.")
    with open(PROMPTS_FILE, "r") as f:
        prompts = [line.strip() for line in f if line.strip()]
    
    if args.test:
        print("--- Running in Test Mode (one prompt) ---")
        prompts = prompts[:1]

    print(f"Found {len(prompts)} prompts.")

    # Preflight providers with sentinel prompts
    provider_models = [("google", GOOGLE_MODEL_DEFAULT), ("openai", OPENAI_MODEL_DEFAULT)]
    # Try to include Anthropic if key/SKD are present
    try:
        if os.getenv("ANTHROPIC_API_KEY"):
            _ = __import__("anthropic")
            provider_models.append(("anthropic", ANTHROPIC_MODEL_DEFAULT))
    except Exception:
        pass
    sentinels = [
        "Okay, will do.",
        "Plan dataset d12 in one hour.",
        "What was the error for rn42?",
        "Model m05 is 75% trained.",
        "The previous task is complete.",
        "Payment system crashed during peak hours.",
    ]
    passing = []
    print("Preflight: testing providers on sentinels…")
    for prov, model in provider_models:
        ok = True
        old_model = LLM_MODEL
        LLM_MODEL = model
        try:
            for s in sentinels:
                if prov == "google":
                    out = get_google_completion(s, EN2SH_SYSTEM_PROMPT)
                elif prov == "openai":
                    out = get_openai_completion(s, EN2SH_SYSTEM_PROMPT)
                else:
                    out = get_anthropic_completion(s, EN2SH_SYSTEM_PROMPT)
                sh = _normalize_shimmer(out)
                if not _looks_valid_shimmer(sh):
                    strict = EN2SH_SYSTEM_PROMPT + "\nIMPORTANT: Output exactly '<routing><action><tokens>→[v1,v2,v3,v4,v5]' with NO SPACES in the container and the real Unicode arrow."
                    if prov == "google":
                        out2 = get_google_completion(s, strict)
                    elif prov == "openai":
                        out2 = get_openai_completion(s, strict)
                    else:
                        out2 = get_anthropic_completion(s, strict)
                    sh = _normalize_shimmer(out2)
                if not _looks_valid_shimmer(sh):
                    ok = False
                    break
        except Exception:
            ok = False
        finally:
            LLM_MODEL = old_model
        print(f"  {prov}:{model} -> {'PASS' if ok else 'FAIL'}")
        if ok:
            passing.append((prov, model))

    if not passing:
        print(f"No providers passed preflight; falling back to '{LLM_PROVIDER}:{LLM_MODEL}'.")
        passing = [(LLM_PROVIDER, LLM_MODEL)]
    else:
        print("Providers selected: " + ", ".join([f"{p}:{m}" for p, m in passing]))

    translations = []
    glosses = []
    used_providers = []

    for i, prompt in enumerate(prompts):
        prov, model = passing[i % len(passing)]
        used_providers.append((prov, model))
        print(f"  Translating prompt {i+1}/{len(prompts)} with {prov}:{model}…")
        old_model = LLM_MODEL
        LLM_MODEL = model
        try:
            if prov == "google":
                out = get_google_completion(prompt, EN2SH_SYSTEM_PROMPT)
            elif prov == "openai":
                out = get_openai_completion(prompt, EN2SH_SYSTEM_PROMPT)
            else:
                out = get_anthropic_completion(prompt, EN2SH_SYSTEM_PROMPT)
        finally:
            LLM_MODEL = old_model
        shimmer = _normalize_shimmer(out)
        if not _looks_valid_shimmer(shimmer):
            strict = EN2SH_SYSTEM_PROMPT + "\nIMPORTANT: Output exactly '<routing><action><tokens>→[v1,v2,v3,v4,v5]' with NO SPACES in the container and the real Unicode arrow."
            old_model = LLM_MODEL
            LLM_MODEL = model
            try:
                if prov == "google":
                    out2 = get_google_completion(prompt, strict)
                elif prov == "openai":
                    out2 = get_openai_completion(prompt, strict)
                else:
                    out2 = get_anthropic_completion(prompt, strict)
            finally:
                LLM_MODEL = old_model
            shimmer = _normalize_shimmer(out2)
        translations.append(shimmer)

        print(f"  Generating gloss {i+1}/{len(prompts)} with {prov}:{model}…")
        old_model = LLM_MODEL
        LLM_MODEL = model
        try:
            if prov == "google":
                gloss = get_google_completion(shimmer, SH2EN_SYSTEM_PROMPT)
            elif prov == "openai":
                gloss = get_openai_completion(shimmer, SH2EN_SYSTEM_PROMPT)
            else:
                gloss = get_anthropic_completion(shimmer, SH2EN_SYSTEM_PROMPT)
        finally:
            LLM_MODEL = old_model
        gloss_str = _extract_json_braces(gloss)
        try:
            gloss_json = json.loads(gloss_str)
        except (json.JSONDecodeError, TypeError):
            gloss_json = {"error": "failed to parse gloss", "raw_output": gloss_str}
        glosses.append(gloss_json)

    with open(TRAINING_FILE, "w", encoding="utf-8") as f, open(os.path.splitext(TRAINING_FILE)[0] + ".providers.tsv", "w", encoding="utf-8") as side:
        line_no = 0
        for idx, (prompt, shimmer) in enumerate(zip(prompts, translations)):
            record = {"messages": [{"role": "user", "content": prompt}, {"role": "assistant", "content": shimmer}]}
            f.write(json.dumps(record, ensure_ascii=False) + "\n"); line_no += 1
            prov, model = used_providers[idx]
            side.write(f"{line_no}\t{prov}\t{model}\n")
        for idx, (shimmer, gloss) in enumerate(zip(translations, glosses)):
            record = {"messages": [{"role": "user", "content": shimmer}, {"role": "assistant", "content": json.dumps(gloss, ensure_ascii=False)}]}
            f.write(json.dumps(record, ensure_ascii=False) + "\n"); line_no += 1
            prov, model = used_providers[idx]
            side.write(f"{line_no}\t{prov}\t{model}\n")

    print("\n---")
    print("✅ Success!")
    if args.test:
        print("Test run successful. You can now run the script without the --test flag.")
    else:
        print(f"Training data generated in '{TRAINING_FILE}'.")

if __name__ == "__main__":
    main()
