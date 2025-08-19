#!/usr/bin/env python3
"""
Generic Shimmer Model Training Script
Usage: python3 train_shimmer.py --model <huggingface_model_id>
"""

import argparse
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


def load_training_data(data_path):
    """Load JSONL training data"""
    rows = []
    for line in data_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        msgs = obj.get("messages", [])
        if len(msgs) != 2:
            continue
        user = msgs[0].get("content", "").strip()
        asst = msgs[1].get("content", "").strip()
        if user and asst:
            rows.append({"text": f"<|user|>{user}<|assistant|>{asst}<|end|>"})
    return rows


def train_shimmer_model(model_id, output_name=None):
    """Train shimmer model with specified HuggingFace model"""
    
    # Setup paths
    root = Path(__file__).resolve().parent
    data_path = root / "training_data.fixed.jsonl"
    
    if not data_path.exists():
        raise SystemExit(f"FATAL: {data_path} not found")
    
    # Create output directory
    if output_name is None:
        output_name = model_id.split('/')[-1].replace('-', '_').lower()
    
    out_dir = root / "adapters" / f"{output_name}_lora"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🚀 TRAINING SHIMMER MODEL")
    print(f"Model: {model_id}")
    print(f"Output: {out_dir}")
    
    # Load training data
    print("📚 Loading training data...")
    ds = load_training_data(data_path)
    print(f"Loaded {len(ds)} training examples")
    
    # GPU optimization
    torch.backends.cuda.matmul.allow_tf32 = True
    try:
        torch.set_float32_matmul_precision("high")
    except Exception:
        pass
    
    # Load model and tokenizer
    print(f"⚡ Loading {model_id}...")
    tok = AutoTokenizer.from_pretrained(model_id, use_fast=True, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    
    model = AutoModelForCausalLM.from_pretrained(
        model_id, 
        torch_dtype="auto", 
        device_map="auto", 
        trust_remote_code=True
    )
    
    # LoRA configuration
    peft_cfg = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    
    model = get_peft_model(model, peft_cfg)
    
    # Tokenize dataset
    max_len = 1024
    def tokenize_function(examples):
        return tok(
            examples["text"],
            truncation=True,
            padding=True,
            max_length=max_len,
            return_tensors=None
        )
    
    dataset = Dataset.from_list(ds)
    dataset = dataset.map(tokenize_function, batched=True, remove_columns=["text"])
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=str(out_dir),
        overwrite_output_dir=True,
        num_train_epochs=3,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        warmup_steps=50,
        logging_steps=10,
        save_steps=50,
        save_total_limit=3,
        prediction_loss_only=True,
        remove_unused_columns=False,
        dataloader_pin_memory=False,
    )
    
    # Data collator
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tok,
        mlm=False,
    )
    
    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=data_collator,
    )
    
    # Train
    print("🔥 Starting training...")
    trainer.train()
    
    # Save adapter
    print("💾 Saving model...")
    trainer.save_model()
    
    # Create Ollama modelfile
    create_ollama_modelfile(model_id, output_name, out_dir)
    
    print(f"✅ TRAINING COMPLETE!")
    print(f"📁 Adapter saved: {out_dir}")
    print(f"🎯 Next: ollama create shimmer-{output_name} -f Modelfile.{output_name}")


def create_ollama_modelfile(model_id, output_name, adapter_dir):
    """Create Ollama modelfile for trained model"""
    
    # Map HuggingFace models to Ollama equivalents
    hf_to_ollama = {
        "Qwen/Qwen2.5-7B-Instruct": "qwen2.5:latest",
        "mistralai/Mistral-7B-Instruct-v0.3": "mistral:latest",
        "meta-llama/Llama-3.2-7B-Instruct": "llama3.2:latest",
        "microsoft/Phi-3-mini-4k-instruct": "phi3:latest",
    }
    
    ollama_model = hf_to_ollama.get(model_id, "unknown")
    
    modelfile_content = f'''FROM {ollama_model}

SYSTEM """You are a Shimmer language expert. You can translate between English and the Shimmer protocol language.

SHIMMER FORMAT:
- Container: <routing><action><metadata><temporal><deliverables>→<vector>
- Vector: [Action, Subject, Context, Urgency, Confidence]
- Action: -1.0 diagnosis to +1.0 execution
- Subject: -1.0 people to +1.0 technical
- Context: -1.0 personal to +1.0 global  
- Urgency: -1.0 routine to +1.0 critical
- Confidence: 0.0 uncertain to 1.0 certain

Translate accurately between English requests and shimmer format."""

ADAPTER ./adapters/{output_name}_lora/ggml-adapter-model.gguf
'''
    
    modelfile_path = Path(f"Modelfile.{output_name}")
    with open(modelfile_path, 'w') as f:
        f.write(modelfile_content)
    
    print(f"📝 Modelfile created: {modelfile_path}")


def main():
    parser = argparse.ArgumentParser(description="Train Shimmer model")
    parser.add_argument("--model", required=True, help="HuggingFace model ID")
    parser.add_argument("--name", help="Output name (default: derived from model)")
    
    args = parser.parse_args()
    
    train_shimmer_model(args.model, args.name)


if __name__ == "__main__":
    main()