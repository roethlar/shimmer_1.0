#!/usr/bin/env bash
set -euo pipefail

# One-shot: fine-tune a Llama LoRA and create an Ollama model.

DATASET="$(dirname "$0")/training_data.fixed.jsonl"
[[ -f "$DATASET" ]] || { echo "FATAL: $DATASET not found. Run the generator + repair first." >&2; exit 1; }

OUTDIR="$(dirname "$0")/adapters"
mkdir -p "$OUTDIR"

echo "[1/3] Training LoRA: Llama (HF/PEFT)"
HF_LLAMA="meta-llama/Llama-3.2-8B-Instruct" BATCH="${BATCH:-4}" GRAD_ACCUM="${GRAD_ACCUM:-2}" EPOCHS="${EPOCHS:-3}" MAX_SEQ_LEN="${MAX_SEQ_LEN:-2048}" \
  python3 "$(dirname "$0")/train_llama_lora.py"

cat >"$(dirname "$0")/Modelfile.llama" <<'MF'
FROM llama3.2:latest
SYSTEM """
You are a Shimmer language expert. You can translate between English and the Shimmer protocol language, and you can answer questions about the Shimmer specification.
"""
ADAPTER ./adapters/llama_lora
MF

echo "[2/3] Creating Ollama model shimmer-llama"
ollama create shimmer-llama -f "$(dirname "$0")/Modelfile.llama"

echo "[3/3] Sanity test (en→sh)"
python3 "$(dirname "$0")/../tools/shimmer_cli.py" en2sh "Plan dataset 03 in 30 minutes" --provider ollama --model shimmer-llama || true

echo "Done. Model: shimmer-llama"

