#!/usr/bin/env python3
"""
Batch translator: .shimmer (one message per line) → English .txt

Reads a file where each line is a Shimmer text message:
  <container>→[v1,v2,v3,v4(,v5)]

For each line, calls the Glossing Template via a provider (ollama or openai)
and writes a plain-English paragraph to the output .txt (one paragraph per line).

Usage:
  python3 shimmer_batch_translate.py \
    --in /path/file.shimmer --out /path/out.txt \
    --provider ollama --model qwen2.5:latest

Notes:
- Lines containing only Base64 binary are currently skipped with a warning.
- For maximum privacy/cost control, prefer a local model via --provider ollama.
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
TOOLS = os.path.join(ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.append(TOOLS)

# Reuse prompt reading and provider calls from shimmer_cli
from shimmer_cli import (
    read_prompt_sections,
    build_glossing_prompt,
    call_ollama,
    call_openai,
    extract_json,
)


def looks_like_text_shimmer(line: str) -> bool:
    return "→[" in line and line.strip().endswith("]")


def main():
    ap = argparse.ArgumentParser(description="Batch translate .shimmer (text lines) to English .txt")
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--provider", choices=["ollama", "openai"], default="ollama")
    ap.add_argument("--model", default="qwen2.5:latest")
    args = ap.parse_args()

    sections = read_prompt_sections(os.path.join(ROOT, "LLM_Prompt_Template.md"))
    system_txt = sections.get("System (Common)") or sections.get("System") or "You are a strict Shimmer protocol agent."

    total = 0
    converted = 0
    skipped = 0

    with open(args.inp, "r", encoding="utf-8") as fin, open(args.out, "w", encoding="utf-8") as fout:
        for raw in fin:
            line = raw.strip()
            if not line:
                fout.write("\n")
                continue
            total += 1
            if not looks_like_text_shimmer(line):
                skipped += 1
                fout.write("[skipped non-text shimmer line]\n")
                continue
            sys_txt, usr_txt = build_glossing_prompt(system_txt, shimmer_msg=line)
            if args.provider == "ollama":
                out = call_ollama(sys_txt, usr_txt, model=args.model)
            else:
                out = call_openai(sys_txt, usr_txt, model=args.model)
            js = extract_json(out)
            # extract one_paragraph if present, else dump JSON
            para = None
            try:
                import json
                j = json.loads(js)
                para = j.get("one_paragraph")
            except Exception:
                pass
            fout.write((para or js).strip() + "\n")
            converted += 1

    print(f"Processed: {total}, converted: {converted}, skipped: {skipped}")


if __name__ == "__main__":
    main()

