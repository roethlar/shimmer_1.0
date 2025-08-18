#!/usr/bin/env python3
"""
Shimmer v1.0 Compliance Checker (text containers)

Validates a Shimmer text message of the form:
  <routing><action><metadata><temporal><deliverables>→[v1,v2,v3,v4(,v5)]

Checks:
- Container grammar basics (routing/action tokens)
- Vector arity (4 or 5), ranges, and transmission quantization (<=1 dp for first 4; <=2 for confidence)
- Optional parity values (computed; informative)

Usage:
  python3 compliance_check.py "ABPrn01τ300f06→[0.5,0.9,0.1,0.9,0.96]"

Exit code 0 on OK, 1 on errors.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import hashlib

ARROW = "→"

ROUTING_RE = re.compile(r"^\s*(?P<routing>.{2})(?P<rest>.*)$")
ACTION_RE = re.compile(r"^(?P<action>[cpaqPe])(.*)$")
TEMP_RE = re.compile(r"τ(\d+)")
RN_RE = re.compile(r"rn\d+")
S_RE = re.compile(r"s:\w+|s\d+")
SHARD_RE = re.compile(r"@s\d+")
CTAG_RE = re.compile(r"ctag[.:|a-zA-Z0-9_()\-]+")
DELIV_RE = re.compile(r"[fdrm]\d{2}")


def parse_message(msg: str):
    if ARROW not in msg:
        return None, None, ["missing_arrow_separator"]
    left, right = msg.split(ARROW, 1)
    left = left.strip()
    right = right.strip()
    errs = []

    m = ROUTING_RE.match(left)
    if not m:
        errs.append("bad_routing_prefix")
        routing = ""
        rest = left
    else:
        routing = m.group("routing")
        rest = m.group("rest")

    m2 = ACTION_RE.match(rest)
    if not m2:
        errs.append("bad_action_code")
        action = ""
        meta_tail = rest
    else:
        action = m2.group("action")
        meta_tail = rest[1:]

    # tokens
    tokens = {
        "rn": RN_RE.findall(meta_tail),
        "session": S_RE.findall(meta_tail),
        "shard": SHARD_RE.findall(meta_tail),
        "ctag": CTAG_RE.findall(meta_tail),
        "deliverables": DELIV_RE.findall(meta_tail),
    }
    deadline = None
    t = TEMP_RE.search(meta_tail)
    if t:
        try:
            deadline = int(t.group(1))
        except Exception:
            errs.append("bad_temporal_number")

    # vector
    v_err = []
    vec = None
    if not (right.startswith("[") and right.endswith("]")):
        v_err.append("vector_brackets_missing")
    else:
        try:
            nums = [x.strip() for x in right[1:-1].split(",") if x.strip()]
            vals = [float(x) for x in nums]
            if len(vals) not in (4, 5):
                v_err.append("vector_arity_not_4_or_5")
            else:
                vec = vals
        except Exception:
            v_err.append("vector_parse_error")

    return (
        {
            "routing": routing,
            "action": action,
            "deadline_seconds": deadline,
            "tokens": tokens,
            "container_text": left,
        },
        {"raw": right, "values": vec},
        errs + v_err,
    )


def in_range(x: float, lo: float, hi: float) -> bool:
    return (x >= lo - 1e-9) and (x <= hi + 1e-9)


def dp_ok(x: float, max_dp: int) -> bool:
    s = f"{x}"
    if "." not in s:
        return True
    frac = s.split(".", 1)[1]
    return len(frac) <= max_dp


def parity_t9(vec: list[float]) -> int:
    """T9+ parity: sum(round(10*axes) + round(100*conf)) % 4."""
    if not vec:
        return 0
    total = 0
    for i, v in enumerate(vec):
        if i < 4:
            total += round(10 * v)
        else:
            total += round(100 * v)
    return total % 4


def parity2b(container_text: str, vec: list[float]) -> int:
    h = hashlib.sha256(container_text.encode("utf-8")).digest()[0]
    s = 0
    if vec:
        for i, v in enumerate(vec):
            s += round(10 * v) if i < 4 else round(100 * v)
    return (h ^ (s & 0xFF)) % 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("message", help="Shimmer text message: <container>→[vector]")
    args = ap.parse_args()

    container, vector, errs = parse_message(args.message)
    warnings = []
    errors = list(errs)

    if not errors and vector["values"]:
        vec = vector["values"]
        # Ranges
        ranges_ok = True
        for i, v in enumerate(vec):
            if i < 4 and not in_range(v, -1.0, 1.0):
                ranges_ok = False
            if i == 4 and not in_range(v, 0.0, 1.0):
                ranges_ok = False
        if not ranges_ok:
            errors.append("vector_out_of_range")

        # Decimal places (transmission quantization)
        if len(vec) >= 4:
            for i in range(4):
                if not dp_ok(vec[i], 1):
                    warnings.append("vector_axis_more_than_1dp")
        if len(vec) == 5 and not dp_ok(vec[4], 2):
            warnings.append("confidence_more_than_2dp")

    # Parity values (informative)
    pt9 = parity_t9(vector["values"]) if vector["values"] else None
    p2b = parity2b(container["container_text"], vector["values"]) if (container and vector["values"]) else None

    report = {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "container": container,
        "vector": vector,
        "parity": {"t9": pt9, "p2b": p2b},
    }
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()

