#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from typing import Tuple

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.append(str(TOOLS))
from shimmer_cli import read_prompt_sections, build_authoring_prompt, build_glossing_prompt  # type: ignore


def load_qwen_with_lora(base_id: str, lora_dir: Path):
    tok = AutoTokenizer.from_pretrained(base_id, use_fast=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    torch.backends.cuda.matmul.allow_tf32 = True
    try:
        torch.set_float32_matmul_precision("high")
    except Exception:
        pass
    model = AutoModelForCausalLM.from_pretrained(
        base_id, torch_dtype="auto", device_map="auto"
    )
    from peft import PeftModel
    model = PeftModel.from_pretrained(model, str(lora_dir))
    model.eval()
    return tok, model


def chat_pack(system_txt: str, user_txt: str) -> str:
    return f"<|im_start|>system\n{system_txt}<|im_end|>\n<|im_start|>user\n{user_txt}<|im_end|>\n<|im_start|>assistant\n"


def generate(tok, model, prompt: str, max_new_tokens: int = 256) -> str:
    inputs = tok(prompt, return_tensors="pt").to(model.device)
    out = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        temperature=0.0,
        eos_token_id=tok.eos_token_id,
    )
    text = tok.decode(out[0], skip_special_tokens=True)
    return text[len(prompt):].strip()


def main():
    try:
        from flask import Flask, request, jsonify
    except Exception:
        print("FATAL: Flask not installed. pip install flask", file=sys.stderr)
        sys.exit(1)

    base_id = os.environ.get("HF_QWEN", "Qwen/Qwen2.5-7B-Instruct")
    lora_dir = Path(__file__).resolve().parent / "adapters" / "qwen_lora"
    if not lora_dir.exists():
        print(f"FATAL: LoRA adapter not found at {lora_dir}", file=sys.stderr)
        sys.exit(1)

    tok, model = load_qwen_with_lora(base_id, lora_dir)

    sections = read_prompt_sections(str(ROOT / "LLM_Prompt_Template.md"))
    system_txt = sections.get("System (Common)") or "You are a strict Shimmer protocol agent."

    app = Flask(__name__)

    @app.post("/en2sh")
    def en2sh():
        data = request.get_json(force=True)
        text = data.get("text", "")
        sys_txt, usr_txt = build_authoring_prompt(system_txt, english_text=text, routing=None, action=None, deadline=None, deliver=None, session=None)
        prompt = chat_pack(sys_txt, usr_txt)
        out = generate(tok, model, prompt)
        return jsonify({"output": out})

    @app.post("/sh2en")
    def sh2en():
        data = request.get_json(force=True)
        text = data.get("text", "")
        sys_txt, usr_txt = build_glossing_prompt(system_txt, shimmer_msg=text)
        prompt = chat_pack(sys_txt, usr_txt)
        out = generate(tok, model, prompt)
        return jsonify({"output": out})

    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()

