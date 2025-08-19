#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec


SHIM_ARROW = "→"
ACTION_MEANINGS = {
    "c": "complete",
    "p": "progress",
    "a": "acknowledge",
    "q": "query",
    "P": "plan",
    "e": "error",
}

# Common lookalikes mapping to ASCII action codes
CONFUSABLES = {
    "ε": "e",  # Greek epsilon
    "е": "e",  # Cyrillic ie
    "а": "a",  # Cyrillic a
    "с": "c",  # Cyrillic es
    "ρ": "p",  # Greek rho
    "Ρ": "P",  # Greek Rho uppercase
}


def load_validator():
    spec = spec_from_file_location("cc", str(Path(__file__).resolve().parents[1] / "tools" / "compliance_check.py"))
    cc = module_from_spec(spec)
    spec.loader.exec_module(cc)  # type: ignore
    return cc


def normalize_action(container_text: str) -> str:
    """If the action letter (3rd char) is a confusable, fix it to ASCII."""
    if len(container_text) < 3:
        return container_text
    a = container_text[2]
    if a in ACTION_MEANINGS:
        return container_text
    if a in CONFUSABLES:
        return container_text[:2] + CONFUSABLES[a] + container_text[3:]
    return container_text


def build_gloss_from_shimmer(cc, shimmer_line: str) -> dict:
    container, vector, errs = cc.parse_message(shimmer_line)
    routing = container["routing"][:2] if container and container.get("routing") else shimmer_line.split(SHIM_ARROW,1)[0][:2]
    cont_text = container.get("container_text", "")
    action_code = cont_text[2] if len(cont_text) >= 3 else container.get("action")
    meaning = ACTION_MEANINGS.get(action_code, "unknown")
    deadline = container.get("deadline_seconds")
    toks = container.get("tokens", {}) if container else {}
    deliverables = toks.get("deliverables", [])
    meta = []
    for k in ("rn", "session", "shard", "ctag"):
        for t in toks.get(k, []):
            meta.append(t)
    vec = vector.get("values") if vector else None
    if vec and len(vec) == 5:
        a, s, c, u, conf = vec
        vector_gloss = f"Action={a:.1f}, Subject={s:.1f}, Context={c:.1f}, Urgency={u:.1f}, Confidence={conf:.2f}"
    elif vec and len(vec) == 4:
        a, s, c, u = vec
        vector_gloss = f"Action={a:.1f}, Subject={s:.1f}, Context={c:.1f}, Urgency={u:.1f}"
    else:
        vector_gloss = ""
    # Simple one-paragraph summary
    dl_txt = f", deadline {deadline}s" if deadline else ""
    meta_txt = ("; metadata=" + ",".join(meta)) if meta else ""
    deliv_txt = ("; deliverables=" + ",".join(deliverables)) if deliverables else ""
    one_para = f"Routing {routing}; action {meaning} ({action_code}){dl_txt}{deliv_txt}{meta_txt}. {vector_gloss}".strip()
    return {
        "routing": routing,
        "action": {"code": action_code, "meaning": meaning},
        "metadata": meta,
        "deadline_seconds": deadline,
        "deliverables": deliverables,
        "vector_gloss": vector_gloss,
        "one_paragraph_summary": one_para,
    }


def main():
    src = Path(__file__).with_name("training_data.jsonl")
    if not src.exists():
        print(f"FATAL: {src} not found")
        sys.exit(1)
    dst = Path(__file__).with_name("training_data.fixed.jsonl")
    cc = load_validator()
    lines = src.read_text(encoding="utf-8").splitlines()

    out = []
    last_shimmer = None
    fixed_counts = {"shimmer_action": 0, "gloss_routing": 0, "gloss_missing": 0}

    for line in lines:
        try:
            rec = json.loads(line)
        except Exception:
            out.append(line)
            continue
        msgs = rec.get("messages", [])
        if len(msgs) != 2:
            out.append(line)
            continue
        asst = msgs[1].get("content", "")
        # Shimmer line
        if SHIM_ARROW in asst and asst.strip().endswith("]"):
            left, right = asst.split(SHIM_ARROW, 1)
            new_left = normalize_action(left)
            if new_left != left:
                fixed_counts["shimmer_action"] += 1
            last_shimmer = f"{new_left}{SHIM_ARROW}{right}"
            msgs[1]["content"] = last_shimmer
            out.append(json.dumps(rec, ensure_ascii=False))
            continue

        # Gloss line (JSON)
        try:
            js = json.loads(asst)
        except Exception:
            # regenerate from shimmer if possible
            if last_shimmer:
                fixed_counts["gloss_missing"] += 1
                new_js = build_gloss_from_shimmer(cc, last_shimmer)
                msgs[1]["content"] = json.dumps(new_js, ensure_ascii=False)
                out.append(json.dumps(rec, ensure_ascii=False))
            else:
                out.append(line)
            continue

        required = {"routing","action","metadata","deadline_seconds","deliverables","vector_gloss","one_paragraph_summary"}
        missing = required - set(js.keys())
        expected_routing = None
        if last_shimmer and SHIM_ARROW in last_shimmer:
            expected_routing = last_shimmer.split(SHIM_ARROW,1)[0][:2]

        changed = False
        if expected_routing and js.get("routing") != expected_routing:
            js["routing"] = expected_routing
            fixed_counts["gloss_routing"] += 1
            changed = True
        if missing or not isinstance(js.get("action"), (str, dict)):
            # Regenerate full gloss to ensure keys and structure
            fixed_counts["gloss_missing"] += 1
            js = build_gloss_from_shimmer(cc, last_shimmer) if last_shimmer else js
            changed = True

        if changed:
            msgs[1]["content"] = json.dumps(js, ensure_ascii=False)
            out.append(json.dumps(rec, ensure_ascii=False))
        else:
            out.append(line)

    dst.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("Wrote:", dst)
    print("Fix counts:", fixed_counts)


if __name__ == "__main__":
    main()

