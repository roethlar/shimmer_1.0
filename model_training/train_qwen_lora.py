#!/usr/bin/env python3
import os
import json
from pathlib import Path

import torch
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    DataCollatorForLanguageModeling,
    Trainer,
)
from peft import LoraConfig, get_peft_model


def load_openai_jsonl(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        msgs = obj.get("messages", [])
        if len(msgs) != 2:
            continue
        user = msgs[0].get("content", "").strip()
        asst = msgs[1].get("content", "").strip()
        if not user or not asst:
            continue
        # Simple chat format for SFT
        text = f"User: {user}\nAssistant: {asst}"
        rows.append({"text": text})
    return Dataset.from_list(rows)


def main():
    root = Path(__file__).resolve().parent
    data_path = root / "training_data.fixed.jsonl"
    if not data_path.exists():
        raise SystemExit(f"FATAL: {data_path} not found. Run the generator + repair first.")

    out_dir = root / "adapters" / "qwen_lora"
    out_dir.mkdir(parents=True, exist_ok=True)

    base_model = os.environ.get("HF_MODEL", "openai/gpt-oss-20b)

    ds = load_openai_jsonl(data_path)

    # Speed opts for Ada/RTX class GPUs
    torch.backends.cuda.matmul.allow_tf32 = True
    try:
        torch.set_float32_matmul_precision("high")
    except Exception:
        pass

    tok = AutoTokenizer.from_pretrained(base_model, use_fast=True, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    model = AutoModelForCausalLM.from_pretrained(base_model, torch_dtype="auto", device_map="auto", trust_remote_code=True)

    peft_cfg = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        bias="none",
        task_type="CAUSAL_LM",
    )

    # Wrap with PEFT LoRA for efficient training
    model = get_peft_model(model, peft_cfg)

    # Tokenize dataset to LM inputs
    max_len = int(os.environ.get("MAX_SEQ_LEN", "2048"))
    def _tok(batch):
        # Let the data collator handle dynamic padding and labels creation (mlm=False)
        enc = tok(
            batch["text"],
            truncation=True,
            max_length=max_len,
            padding=False,
            return_attention_mask=True,
        )
        return enc
    ds_tok = ds.map(_tok, batched=True, remove_columns=["text"])  # keep it simple

    per_bs = int(os.environ.get("BATCH", "2"))
    grad_acc = int(os.environ.get("GRAD_ACCUM", "4"))
    epochs = int(os.environ.get("EPOCHS", "3"))

    args = TrainingArguments(
        output_dir=str(out_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=per_bs,
        gradient_accumulation_steps=grad_acc,
        learning_rate=2e-4,
        logging_steps=10,
        save_strategy="epoch",
        fp16=False,
        bf16=True,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        report_to=[],
    )

    collator = DataCollatorForLanguageModeling(tokenizer=tok, mlm=False, pad_to_multiple_of=8)

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=ds_tok,
        data_collator=collator,
        tokenizer=tok,
    )

    trainer.train()
    # Save adapter
    model.save_pretrained(str(out_dir))

    # Pick safetensors file for Ollama ADAPTER
    safes = list(out_dir.glob("*adapter_model.safetensors")) or list(out_dir.glob("*.safetensors"))
    if safes:
        # symlink/copy canonical path
        target = root / "adapters" / "qwen_lora.safetensors"
        try:
            if target.exists():
                target.unlink()
            target.symlink_to(safes[0])
        except Exception:
            import shutil
            shutil.copyfile(safes[0], target)

    print("Saved LoRA adapter to:", out_dir)


if __name__ == "__main__":
    main()
