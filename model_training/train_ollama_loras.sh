#!/usr/bin/env bash
set -euo pipefail

# Minimal, end-to-end LoRA fine-tune + Ollama model creation for three bases.
# Requires: Python + `pip install unsloth`, GPU with enough VRAM.

DATASET="$(dirname "$0")/training_data.fixed.jsonl"
[[ -f "$DATASET" ]] || { echo "FATAL: $DATASET not found. Run the generator + repair first." >&2; exit 1; }

if ! command -v python3 >/dev/null 2>&1; then
  echo "FATAL: python3 not found" >&2; exit 1
fi

if ! python3 -c 'import unsloth' >/dev/null 2>&1; then
  echo "Unsloth not found. Install with: pip install unsloth" >&2
  exit 1
fi

OUTDIR="$(dirname "$0")/adapters"
mkdir -p "$OUTDIR"

# HuggingFace base model IDs (edit if you prefer different sizes)
HF_QWEN="Qwen/Qwen2.5-7B-Instruct"
HF_MISTRAL="mistralai/Mistral-7B-Instruct-v0.3"
HF_LLAMA="meta-llama/Llama-3.2-8B-Instruct"

echo "[1/6] Training LoRA: Qwen"
unsloth finetune \
  --model "$HF_QWEN" \
  --dataset "$DATASET" \
  --format openai \
  --output "$OUTDIR/qwen_lora.safetensors" \
  --r 16 --alpha 32 --lr 2e-4 --epochs 2 --bf16

echo "[2/6] Training LoRA: Mistral"
unsloth finetune \
  --model "$HF_MISTRAL" \
  --dataset "$DATASET" \
  --format openai \
  --output "$OUTDIR/mistral_lora.safetensors" \
  --r 16 --alpha 32 --lr 2e-4 --epochs 2 --bf16

echo "[3/6] Training LoRA: Llama"
unsloth finetune \
  --model "$HF_LLAMA" \
  --dataset "$DATASET" \
  --format openai \
  --output "$OUTDIR/llama_lora.safetensors" \
  --r 16 --alpha 32 --lr 2e-4 --epochs 2 --bf16

cat >"$(dirname "$0")/Modelfile.qwen" <<'MF'
FROM qwen2.5:latest
SYSTEM """
You are a Shimmer language expert. You can translate between English and the Shimmer protocol language, and you can answer questions about the Shimmer specification.
"""
ADAPTER ./adapters/qwen_lora.safetensors
MF

cat >"$(dirname "$0")/Modelfile.mistral" <<'MF'
FROM mistral:7b-instruct
SYSTEM """
You are a Shimmer language expert. You can translate between English and the Shimmer protocol language, and you can answer questions about the Shimmer specification.
"""
ADAPTER ./adapters/mistral_lora.safetensors
MF

cat >"$(dirname "$0")/Modelfile.llama" <<'MF'
FROM llama3.2:latest
SYSTEM """
You are a Shimmer language expert. You can translate between English and the Shimmer protocol language, and you can answer questions about the Shimmer specification.
"""
ADAPTER ./adapters/llama_lora.safetensors
MF

echo "[4/6] Creating Ollama models"
ollama create shimmer-qwen -f "$(dirname "$0")/Modelfile.qwen"
ollama create shimmer-mistral -f "$(dirname "$0")/Modelfile.mistral"
ollama create shimmer-llama -f "$(dirname "$0")/Modelfile.llama"

echo "[5/6] Sanity tests (en→sh)"
python3 "$(dirname "$0")/../tools/shimmer_cli.py" en2sh "Plan dataset 03 in 30 minutes" --provider ollama --model shimmer-qwen || true
python3 "$(dirname "$0")/../tools/shimmer_cli.py" en2sh "Plan dataset 03 in 30 minutes" --provider ollama --model shimmer-mistral || true
python3 "$(dirname "$0")/../tools/shimmer_cli.py" en2sh "Plan dataset 03 in 30 minutes" --provider ollama --model shimmer-llama || true

echo "[6/6] Done. Models: shimmer-qwen, shimmer-mistral, shimmer-llama"

