#!/usr/bin/env python3
"""
SJL Policy Linter — compactness and English usage scoring

Input: SJL-Text lines (<container>→[vector]) from stdin or file
Output: JSON lines with {line, ok, score, issues}
Exit: 0 if all ok or --min-score not set; 1 if any score < --min-score

Usage:
  python3 sjl_policy_lint.py --file SkippyTM/coord.sjl --min-score 80 | jq .
"""

from __future__ import annotations

import argparse
import json
import re
import sys

ARROW = "→"

ALLOWED_TOKEN_RE = re.compile(r"^(rn\d+|s:[a-z0-9]+|s\d+|@s\d+|[fdrm]\d{2}|ctag[.:|a-zA-Z0-9_()\-]+)$")
LETTERS_UNDERSCORE_RE = re.compile(r"^[A-Za-z_]+$")


def score_line(line: str) -> tuple[int, list[str]]:
    score = 100
    issues = []
    if ARROW not in line:
        return 0, ["missing_arrow"]
    left, right = line.split(ARROW, 1)
    if " " in left:
        score -= 20
        issues.append("spaces_in_container")
    # routing + action
    if len(left) >= 3:
        action = left[2]
        if not (action in "cpqaeP"):
            score -= 10
            issues.append("invalid_action_code")
        elif action.isupper() and action != "P":
            score -= 10
            issues.append("uppercase_action")
    # tokens compactness
    meta = left[3:]
    tokens = re.findall(r"[A-Za-z0-9_:.@]+", meta)
    for t in tokens:
        if not ALLOWED_TOKEN_RE.match(t):
            if LETTERS_UNDERSCORE_RE.match(t) and len(t) > 24:
                score -= 10
                issues.append(f"verbose_token:{t}")
    # vector dp checks
    v = right.strip()
    if v.startswith("[") and v.endswith("]"):
        parts = [p.strip() for p in v[1:-1].split(",") if p.strip()]
        for i, p in enumerate(parts):
            if "." in p:
                dp = len(p.split(".", 1)[1])
                if i < 4 and dp > 1:
                    score -= 5
                    issues.append("axis>1dp")
                if i == 4 and dp > 2:
                    score -= 3
                    issues.append("conf>2dp")
    return max(score, 0), issues


def iter_lines(path: str | None):
    if path:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                yield line.rstrip("\n")
    else:
        for line in sys.stdin:
            yield line.rstrip("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--min-score", type=int, default=None)
    args = ap.parse_args()

    all_ok = True
    for line in iter_lines(args.file):
        if not line.strip():
            continue
        score, issues = score_line(line)
        ok = (args.min_score is None) or (score >= args.min_score)
        if not ok:
            all_ok = False
        print(json.dumps({"line": line, "ok": ok, "score": score, "issues": issues}, ensure_ascii=False))
    if args.min_score is not None and not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()

