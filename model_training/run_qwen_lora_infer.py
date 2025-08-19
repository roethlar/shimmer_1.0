#!/usr/bin/env python3
import os
import sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextStreamer

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
    # Load PEFT LoRA adapter
    try:
        from peft import PeftModel
    except Exception as e:
        print("FATAL: peft not installed. pip install peft", file=sys.stderr)
        raise
    model = PeftModel.from_pretrained(model, str(lora_dir))
    model.eval()
    return tok, model


def generate(tok, model, prompt: str, max_new_tokens: int = 256):
    inputs = tok(prompt, return_tensors="pt").to(model.device)
    out = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        temperature=0.0,
        eos_token_id=tok.eos_token_id,
    )
    text = tok.decode(out[0], skip_special_tokens=True)
    # Return only the completion past the prompt
    return text[len(prompt):].strip()


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("en2sh", "sh2en"):
        print("Usage: run_qwen_lora_infer.py en2sh 'text' | sh2en '<container>→[vector]'")
        sys.exit(1)

    cmd = sys.argv[1]
    text = sys.argv[2]

    base_id = os.environ.get("HF_QWEN", "Qwen/Qwen2.5-7B-Instruct")
    lora_dir = Path(__file__).resolve().parent / "adapters" / "qwen_lora"
    if not lora_dir.exists():
        print(f"FATAL: LoRA adapter not found at {lora_dir}. Run train_ollama_qwen.sh first.")
        sys.exit(1)

    tok, model = load_qwen_with_lora(base_id, lora_dir)

    sections = read_prompt_sections(str(ROOT / "LLM_Prompt_Template.md"))
    system_txt = sections.get("System (Common)") or "You are a strict Shimmer protocol agent."

    if cmd == "en2sh":
        sys_txt, usr_txt = build_authoring_prompt(system_txt, english_text=text, routing=None, action=None, deadline=None, deliver=None, session=None)
    else:
        sys_txt, usr_txt = build_glossing_prompt(system_txt, shimmer_msg=text)

    # Compose a simple chat prompt for Qwen
    chat = f"<|im_start|>system\n{sys_txt}<|im_end|>\n<|im_start|>user\n{usr_txt}<|im_end|>\n<|im_start|>assistant\n"
    out = generate(tok, model, chat, max_new_tokens=256)
    print(out.strip())


if __name__ == "__main__":
    main()

