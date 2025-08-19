#!/usr/bin/env python3
"""
Shimmer CLI (v1.0)

One-liners to translate between English and Shimmer using a local Ollama model or an API model.

Commands:
  - en2sh: English → Shimmer (returns single line: <container>→[...])
  - sh2en: Shimmer → English (returns compact JSON gloss)

Providers:
  - ollama  (default host http://localhost:11434)
  - openai  (needs OPENAI_API_KEY)

Examples:
  shimmer-cli en2sh "Plan dataset 03 in 30 minutes" \
    --provider ollama --model qwen2.5:latest --routing AB --deadline 1800

  shimmer-cli sh2en "ABPrn02τ1800d03→[0.5,0.6,0.5,0.9,0.92]" \
    --provider openai --model gpt-4o-mini
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(__file__))
PROMPT_PATH = os.path.join(ROOT, "LLM_Prompt_Template.md")


def http_post(url: str, payload: dict, headers: dict, timeout: int = 60) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e}")


def read_prompt_sections(path: str) -> dict:
    text = open(path, "r", encoding="utf-8").read()
    sections = {}
    cur = None
    buf = []
    for line in text.splitlines():
        if line.strip().startswith("## "):
            # flush
            if cur:
                sections[cur] = "\n".join(buf).strip()
            cur = line.strip()[3:].strip()
            buf = []
        else:
            buf.append(line)
    if cur:
        sections[cur] = "\n".join(buf).strip()
    return sections


def build_authoring_prompt(system_txt: str, english_text: str, routing: str | None, action: str | None,
                            deadline: int | None, deliver: list[str] | None, session: str | None) -> tuple[str, str]:
    user = []
    user.append("Instruction: Convert the English request into a Shimmer text container and a T9+ vector per the spec. Use 1 decimal for the first 4 axes. Include Confidence in [0,1]. Output ONLY the container and vector on a single line.")
    user.append("\nInput:\n\"\"\"\n" + english_text + "\n\"\"\"")
    hints = []
    if routing:
        hints.append(f"routing: {routing}")
    if action:
        hints.append(f"action: {action}")
    if deadline is not None:
        hints.append(f"deadline_seconds: {deadline}")
    if deliver:
        hints.append(f"deliverables: {' '.join(deliver)}")
    if session:
        hints.append(f"session: {session}")
    if hints:
        user.append("\nOptional hints:\n- " + "\n- ".join(hints))
    # keep one concise example
    user.append("\nFew-shot example:\nEN: Plan to deliver dataset 03 in 30 minutes; technical task; high urgency.\nOUT: ABPrn02τ1800d03→[0.5,0.6,0.5,0.9,0.92]\n\nNow convert the input.")
    return system_txt, "\n".join(user)


def build_glossing_prompt(system_txt: str, shimmer_msg: str) -> tuple[str, str]:
    user = []
    user.append("Instruction: Read a Shimmer text container with vector and produce a concise English gloss that explains routing, action, metadata, deadline (if any), deliverables, and the vector meaning. Keep it to one short paragraph.")
    user.append("\nInput:\n" + shimmer_msg)
    user.append("\nOutput keys:\n- routing: source→dest\n- action: code + meaning\n- metadata: list\n- deadline_seconds: number or none\n- deliverables: list\n- vector_gloss: short plain-English summary of action/subject/context/urgency with confidence\n- one_paragraph: fluent 1–2 sentences suitable for humans\n\nReturn a compact JSON object with those keys.")
    return system_txt, "\n".join(user)


def call_ollama(system_txt: str, user_txt: str, model: str, host: str | None = None) -> str:
    base = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    url = base.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_txt},
            {"role": "user", "content": user_txt},
        ],
    }
    resp = http_post(url, payload, headers={})
    if "message" in resp and isinstance(resp["message"], dict):
        return resp["message"].get("content", "").strip()
    if "choices" in resp and resp["choices"]:
        return resp["choices"][0]["message"]["content"].strip()
    if "output" in resp:
        return str(resp["output"]).strip()
    raise RuntimeError("Unexpected Ollama response")


def call_openai(system_txt: str, user_txt: str, model: str, base_url: str | None = None, api_key: str | None = None) -> str:
    base = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    url = base + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_txt},
            {"role": "user", "content": user_txt},
        ],
        "temperature": 0,
    }
    resp = http_post(url, payload, headers={"Authorization": f"Bearer {key}"})
    try:
        return resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise RuntimeError(f"Unexpected OpenAI response: {e}: {resp}")


def extract_container_line(text: str) -> str:
    for line in text.splitlines():
        if "→[" in line and "]" in line:
            return line.strip()
    return text.strip()


def extract_json(text: str) -> str:
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        return m.group(0)
    return text.strip()


def main():
    ap = argparse.ArgumentParser(prog="shimmer-cli", description="English ↔ Shimmer using LLMs")
    sub = ap.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--provider", choices=["ollama", "openai"], default="ollama")
    common.add_argument("--model", default="qwen2.5:latest")

    a = sub.add_parser("en2sh", parents=[common], help="English → Shimmer")
    a.add_argument("text", help="English text to convert")
    a.add_argument("--routing", default=None)
    a.add_argument("--action", default=None)
    a.add_argument("--deadline", type=int, default=None)
    a.add_argument("--deliver", action="append", default=None, help="e.g., f01 (repeatable)")
    a.add_argument("--session", default=None)

    b = sub.add_parser("sh2en", parents=[common], help="Shimmer → English")
    b.add_argument("message", help="Shimmer message '<container>→[vector]' to gloss")

    args = ap.parse_args()

    sections = read_prompt_sections(PROMPT_PATH)
    system_txt = sections.get("System (Common)") or sections.get("System") or "You are a strict Shimmer protocol agent."

    if args.cmd == "en2sh":
        sys_txt, usr_txt = build_authoring_prompt(
            system_txt,
            english_text=args.text,
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
        print(extract_container_line(out))
        return

    if args.cmd == "sh2en":
        sys_txt, usr_txt = build_glossing_prompt(system_txt, shimmer_msg=args.message)
        if args.provider == "ollama":
            out = call_ollama(sys_txt, usr_txt, model=args.model)
        else:
            out = call_openai(sys_txt, usr_txt, model=args.model)
        js = extract_json(out)
        print(js)
        return


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

