#!/usr/bin/env python3
"""
Batch translator: English .txt (one request per line) → .shimmer (one Shimmer message per line)

Each non-empty input line is converted with the Authoring Template. Blank lines are preserved.

Usage:
  python3 shimmer_batch_en2sh.py \
    --in /path/in.txt --out /path/out.shimmer \
    --provider ollama --model shimmer-qwen:latest --routing AB --action auto

Notes:
- Keep each line to one coherent instruction/statement. If you need multiple messages, use multiple lines.
- You can set defaults for routing/action/deadline/session/deliverables via flags.
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
TOOLS = os.path.join(ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.append(TOOLS)

from shimmer_cli import (
    read_prompt_sections,
    build_authoring_prompt,
    call_ollama,
    call_openai,
    extract_container_line,
)


def main():
    ap = argparse.ArgumentParser(description="Batch translate English .txt to .shimmer (text containers)")
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--provider", choices=["ollama", "openai"], default="ollama")
    ap.add_argument("--model", default="qwen2.5:latest")
    ap.add_argument("--routing", default=None)
    ap.add_argument("--action", default=None, help="P|q|c|a|p|e or 'auto'")
    ap.add_argument("--deadline", type=int, default=None)
    ap.add_argument("--deliver", action="append", default=None, help="e.g., f01 (repeatable)")
    ap.add_argument("--session", default=None)
    args = ap.parse_args()

    sections = read_prompt_sections(os.path.join(ROOT, "LLM_Prompt_Template.md"))
    system_txt = sections.get("System (Common)") or sections.get("System") or "You are a strict Shimmer protocol agent."

    total = 0
    converted = 0
    with open(args.inp, "r", encoding="utf-8") as fin, open(args.out, "w", encoding="utf-8") as fout:
        for raw in fin:
            line = raw.rstrip("\n")
            if not line.strip():
                fout.write("\n")
                continue
            total += 1
            sys_txt, usr_txt = build_authoring_prompt(
                system_txt,
                english_text=line,
                routing=args.routing,
                action=args.action,
                deadline=args.deadline,
                deliver=args.deliver,
                session=args.session,
            )
            if args.provider == "ollama":
                out = call_ollama(sys_txt, usr_txt, model=args.model)
            else:
                out = call_openai(sys_txt, usr_txt, model=args.model)
            cont = extract_container_line(out)
            fout.write(cont + "\n")
            converted += 1

    print(f"Processed: {total}, converted: {converted}")


if __name__ == "__main__":
    main()

