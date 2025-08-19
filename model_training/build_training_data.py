#!/usr/bin/env python3
"""
Builds a JSONL training corpus for Shimmer adapters using shared prompts.

Features
- Uses the shared LLM prompt template (LLM_Prompt_Template.md)
- Supports providers: ollama, openai, google
- Validates Shimmer outputs (format/ranges) and optional compactness scoring
- Flexible CLI: choose prompts file, output path, provider/model, test count

Output
- JSONL with conversational records suitable for adapter fine-tuning.
  Two records per prompt by default:
    1) English → Shimmer
    2) Shimmer → English gloss (compact JSON)

Examples
  python3 model_training/build_training_data.py \
    --prompts model_training/prompts.txt \
    --out model_training/training_data.jsonl \
    --provider ollama --model qwen2.5:latest --test 5 --validate --min-compactness 80

  python3 model_training/build_training_data.py \
    --provider openai --model gpt-4o-mini

  python3 model_training/build_training_data.py \
    --provider google --model models/gemini-1.5-pro-latest
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import List, Tuple, Optional

# Resolve repo root and tools for imports
ROOT = os.path.dirname(os.path.dirname(__file__))
TOOLS_DIR = os.path.join(ROOT, "tools")
if TOOLS_DIR not in sys.path:
    sys.path.append(TOOLS_DIR)

# Reuse prompt building and provider helpers
from shimmer_cli import (
    read_prompt_sections,
    build_authoring_prompt,
    build_glossing_prompt,
    call_ollama,
    call_openai,
    extract_container_line,
    extract_json,
)

# Validation helpers
try:
    # parse_message returns (container_info, vector_info, errors)
    from compliance_check import parse_message as parse_shimmer
except Exception:
    parse_shimmer = None  # optional

try:
    # Compactness scoring (optional)
    from sjl_policy_lint import score_line as compactness_score
except Exception:
    compactness_score = None


def call_google(system_txt: str, user_txt: str, model: str) -> str:
    """Minimal Google Generative AI call using the official SDK.

    Requires environment variable GOOGLE_API_KEY.
    """
    try:
        import google.generativeai as genai
    except Exception as e:
        raise RuntimeError(f"google.generativeai not installed: {e}")

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set")

    genai.configure(api_key=api_key)
    cfg = genai.types.GenerationConfig(temperature=0.0)
    model_obj = genai.GenerativeModel(model, system_instruction=system_txt, generation_config=cfg)
    resp = model_obj.generate_content(user_txt)
    text = getattr(resp, "text", None) or ""
    text = str(text).strip()
    if not text:
        # Provide diagnostics for safety blocks if present
        raise RuntimeError(f"Empty response from Google API: {getattr(resp, 'prompt_feedback', None)}")
    return text


def normalize_container(line: str) -> str:
    """Normalize common model quirks to strict Shimmer text.
    - Ensure Unicode arrow →
    - Remove spaces on the container side (left of →)
    - Strip code fences and markdown
    """
    if not line:
        return line
    text = line.strip()
    # Strip code fences if present
    if text.startswith("```"):
        text = text.strip("`")
        text = text.replace("json\n", "").replace("JSON\n", "")
    # Normalize arrows
    text = text.replace("\\u2192", "→").replace("u2192", "→").replace("->", "→")
    if "→" not in text:
        return text
    left, right = text.split("→", 1)
    left = left.replace(" ", "")
    return f"{left}→{right.strip()}"


def validate_shimmer(line: str) -> Tuple[bool, List[str]]:
    if not parse_shimmer:
        return True, []
    c, v, errs = parse_shimmer(line)
    ok = (len(errs) == 0) and bool(v and v.get("values") and (len(v["values"]) in (4, 5)))
    return ok, list(errs)


def score_compactness(line: str) -> Tuple[Optional[int], List[str]]:
    if not compactness_score:
        return None, []
    score, issues = compactness_score(line)
    return score, issues


def write_jsonl(path: str, records: List[dict], append: bool = False) -> None:
    mode = "a" if append else "w"
    with open(path, mode, encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def run_once(english: str, provider: str, model: str, system_txt: str,
             validate: bool, min_compactness: Optional[int]) -> Tuple[Optional[str], Optional[dict], dict]:
    """Translate EN→SH, then SH→EN gloss. Returns (shimmer_line, gloss_json, stats)."""
    # Build prompts
    sys_txt, usr_txt = build_authoring_prompt(system_txt, english_text=english, routing=None, action=None,
                                              deadline=None, deliver=None, session=None)

    # Call provider
    if provider == "ollama":
        out = call_ollama(sys_txt, usr_txt, model=model)
    elif provider == "openai":
        out = call_openai(sys_txt, usr_txt, model=model)
    elif provider == "google":
        out = call_google(sys_txt, usr_txt, model=model)
    else:
        raise RuntimeError(f"Unknown provider: {provider}")

    shimmer_line = normalize_container(extract_container_line(out))

    stats = {"validated": False, "validation_errors": [], "compactness": None, "compactness_issues": []}

    if validate:
        ok, errs = validate_shimmer(shimmer_line)
        stats["validated"] = ok
        stats["validation_errors"] = errs
        if not ok:
            # One more try: prompt again with a stronger nudge
            sys_txt2 = system_txt + "\nImportant: Output must be exactly '<container>→[v1,v2,v3,v4,v5]' with NO spaces before the arrow."
            if provider == "ollama":
                out2 = call_ollama(sys_txt2, usr_txt, model=model)
            elif provider == "openai":
                out2 = call_openai(sys_txt2, usr_txt, model=model)
            else:
                out2 = call_google(sys_txt2, usr_txt, model=model)
            shimmer_line = normalize_container(extract_container_line(out2))
            ok2, errs2 = validate_shimmer(shimmer_line)
            stats["validated"] = ok2
            stats["validation_errors"] = errs2

    sc, issues = score_compactness(shimmer_line)
    if sc is not None:
        stats["compactness"] = sc
        stats["compactness_issues"] = issues
        if (min_compactness is not None) and (sc < min_compactness):
            # If available, do a light penalty nudge and retry once
            sys_txt3 = system_txt + "\nKeep tokens compact. Avoid spaces and verbose tokens."
            if provider == "ollama":
                out3 = call_ollama(sys_txt3, usr_txt, model=model)
            elif provider == "openai":
                out3 = call_openai(sys_txt3, usr_txt, model=model)
            else:
                out3 = call_google(sys_txt3, usr_txt, model=model)
            shimmer_line = normalize_container(extract_container_line(out3))
            sc2, issues2 = score_compactness(shimmer_line)
            stats["compactness"] = sc2
            stats["compactness_issues"] = issues2

    # Now build a gloss for the produced shimmer_line
    sys2, usr2 = build_glossing_prompt(system_txt, shimmer_msg=shimmer_line)
    if provider == "ollama":
        g_out = call_ollama(sys2, usr2, model=model)
    elif provider == "openai":
        g_out = call_openai(sys2, usr2, model=model)
    else:
        g_out = call_google(sys2, usr2, model=model)
    gloss_text = extract_json(g_out)
    gloss_json = None
    try:
        gloss_json = json.loads(gloss_text)
    except Exception:
        gloss_json = {"raw": gloss_text}

    return shimmer_line, gloss_json, stats


def main():
    ap = argparse.ArgumentParser(description="Generate Shimmer training data (JSONL)")
    ap.add_argument("--prompts", default=os.path.join(os.path.dirname(__file__), "prompts.txt"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "training_data.jsonl"))
    ap.add_argument("--append", action="store_true", help="Append to output instead of overwrite")
    ap.add_argument("--provider", choices=["ollama", "openai", "google"], default="ollama")
    ap.add_argument("--model", default="qwen2.5:latest")
    ap.add_argument("--test", type=int, default=None, help="Only use the first N prompts")
    ap.add_argument("--sleep", type=float, default=0.0, help="Sleep seconds between calls")
    ap.add_argument("--validate", action="store_true", help="Validate shimmer outputs with compliance checker")
    ap.add_argument("--min-compactness", type=int, default=None, help="Minimum compactness score (requires sjl_policy_lint)")
    args = ap.parse_args()

    # Read system prompt
    sections = read_prompt_sections(os.path.join(ROOT, "LLM_Prompt_Template.md"))
    system_txt = sections.get("System (Common)") or "You are a strict Shimmer protocol agent."

    if not os.path.exists(args.prompts):
        print(f"Error: prompts file not found: {args.prompts}", file=sys.stderr)
        sys.exit(1)
    with open(args.prompts, "r", encoding="utf-8") as f:
        prompts = [ln.strip() for ln in f if ln.strip()]
    if args.test is not None:
        prompts = prompts[: max(0, args.test)]

    print(f"Found {len(prompts)} prompts. Provider='{args.provider}', model='{args.model}'.")
    print(f"Output: {args.out} ({'append' if args.append else 'overwrite'})")
    if args.validate:
        print("Validation: enabled")
    if args.min_compactness is not None:
        print(f"Compactness threshold: {args.min_compactness}")

    records: List[dict] = []
    failures = 0

    for i, en in enumerate(prompts, 1):
        print(f"[{i}/{len(prompts)}] Translating…", end=" ")
        try:
            sh, gloss, stats = run_once(
                english=en,
                provider=args.provider,
                model=args.model,
                system_txt=system_txt,
                validate=args.validate,
                min_compactness=args.min_compactness,
            )
            if not sh:
                raise RuntimeError("empty shimmer output")

            # Write two records per prompt
            records.append({
                "messages": [
                    {"role": "user", "content": en},
                    {"role": "assistant", "content": sh},
                ]
            })
            records.append({
                "messages": [
                    {"role": "user", "content": sh},
                    {"role": "assistant", "content": json.dumps(gloss, ensure_ascii=False)},
                ]
            })
            status_bits = []
            if stats.get("validated"):
                status_bits.append("valid")
            if stats.get("compactness") is not None:
                status_bits.append(f"score={stats['compactness']}")
            print("OK" + (" (" + ", ".join(status_bits) + ")" if status_bits else ""))
        except Exception as e:
            failures += 1
            print(f"FAIL: {e}")
        if args.sleep:
            time.sleep(args.sleep)

    if not records:
        print("No records generated.")
        sys.exit(2)

    # Persist
    write_jsonl(args.out, records, append=args.append)

    print("---")
    print(f"✅ Done. Wrote {len(records)} records for {len(prompts)} prompts → {args.out}")
    if failures:
        print(f"Warnings: {failures} prompt(s) failed; skipped.")


if __name__ == "__main__":
    main()

