#!/usr/bin/env python3
"""
SJL Symbolizer: rewrite verbose English ctag.* metadata into Unicode-symbol tokens.

Conservative mappings focused on whisper_debug_coordination.sjl patterns.
Usage:
  echo "<SJL line>" | tools/sjl_symbolize.py
  tools/sjl_symbolize.py input.sjl > output.sjl
"""
import re
import sys
from typing import Iterable


# Match a ctag.* run up to (but not including) τ, the arrow, or the vector '['
CTAG_RE = re.compile(r"(ctag\.[^τ\[→]*)")


def symbolize_ctag(token: str) -> str:
    # Input like 'ctag.status:chunked_wav_infinite_loops_all_engines'
    body = token[len("ctag."):]

    # Basic splits
    parts = re.split(r"[:_]", body)
    parts = [p for p in parts if p]

    out_tokens: list[str] = []

    # Status keywords → ctag.σ:…
    if any(p in {"status", "urgent", "failed", "ready", "ack"} for p in parts):
        if "failed" in parts:
            out_tokens.append("ctag.σ:✗")
        elif "urgent" in parts:
            out_tokens.append("ctag.σ:‼")
        elif "ready" in parts:
            out_tokens.append("ctag.σ:✓")
        elif "ack" in parts:
            out_tokens.append("ctag.σ:✓")

    # Loop/pend detection
    if any(p in {"loop", "loops", "looping", "pending"} for p in parts):
        out_tokens.append("ctag.σ:⟳")

    # Implementation/fix → μ
    if any(p in {"impl", "implement", "fix", "rep", "repetition"} for p in parts):
        # crude short-code
        code = "rep_fix" if "rep" in parts or "repetition" in parts or "fix" in parts else "impl"
        out_tokens.append(f"ctag.μ:{code}")

    # Knowledge/query domain → κ (params/arch)
    if any(p in {"ask", "params", "parameters", "archive", "arch"} for p in parts):
        sub = []
        if any(p in {"params", "parameters"} for p in parts):
            sub.append("params")
        if any(p in {"archive", "arch"} for p in parts):
            sub.append("arch")
        if sub:
            out_tokens.append("ctag.κ:" + ":".join(sub))

    
    # Fallback: nothing matched → return original token
    return "".join(out_tokens) or token


def symbolize_line(line: str) -> str:
    # Only process metadata segment before the arrow or vector
    # Replace each ctag.* occurrence conservatively
    def repl(m: re.Match[str]) -> str:
        return symbolize_ctag(m.group(1))
    return CTAG_RE.sub(repl, line)


def run(lines: Iterable[str]) -> None:
    for raw in lines:
        line = raw.rstrip("\n")
        if not line.strip():
            print(line)
            continue
        try:
            print(symbolize_line(line))
        except Exception:
            print(line)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            run(f)
    else:
        run(sys.stdin)
