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


def load_openai_jsonl(path: Path) -> Dataset:
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
        rows.append({"text": f"User: {user}\nAssistant: {asst}"})
    return Dataset.from_list(rows)


def main():
    root = Path(__file__).resolve().parent
    data_path = root / "training_data.fixed.jsonl"
    if not data_path.exists():
        data_path = root / "training_data.jsonl"
    if not data_path.exists():
        raise SystemExit("FATAL: training_data.fixed.jsonl or training_data.jsonl not found")

    base_dir = os.environ.get("BASE_DIR")
    if not base_dir:
        raise SystemExit("FATAL: BASE_DIR env var not set (path to local FP16 base)")
    base_dir = str(Path(base_dir).resolve())

    out_dir = root / "adapters" / "local_lora"
    out_dir.mkdir(parents=True, exist_ok=True)

    ds = load_openai_jsonl(data_path)

    # Fast math
    torch.backends.cuda.matmul.allow_tf32 = True
    try:
        torch.set_float32_matmul_precision("high")
    except Exception:
        pass

    # Load local base (no HF)
    tok = AutoTokenizer.from_pretrained(base_dir, use_fast=True, local_files_only=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_dir, torch_dtype="auto", device_map="auto", local_files_only=True
    )

    # Generic LoRA for LLaMA/Mistral/Qwen-style proj names
    targets = os.environ.get("LORA_TARGETS", "q_proj,k_proj,v_proj,o_proj").split(",")
    peft_cfg = LoraConfig(
        r=int(os.environ.get("LORA_R", "16")),
        lora_alpha=int(os.environ.get("LORA_ALPHA", "32")),
        lora_dropout=float(os.environ.get("LORA_DROPOUT", "0.05")),
        target_modules=[t.strip() for t in targets if t.strip()],
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, peft_cfg)

    max_len = int(os.environ.get("MAX_SEQ_LEN", "2048"))

    def _tok(batch):
        return tok(batch["text"], truncation=True, max_length=max_len, padding=False, return_attention_mask=True)

    ds_tok = ds.map(_tok, batched=True, remove_columns=["text"])  # simple SFT

    per_bs = int(os.environ.get("BATCH", "4"))
    grad_acc = int(os.environ.get("GRAD_ACCUM", "2"))
    epochs = int(os.environ.get("EPOCHS", "3"))

    args = TrainingArguments(
        output_dir=str(out_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=per_bs,
        gradient_accumulation_steps=grad_acc,
        learning_rate=float(os.environ.get("LR", "2e-4")),
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
    model.save_pretrained(str(out_dir))
    print("Saved LoRA adapter to:", out_dir)


if __name__ == "__main__":
    main()

