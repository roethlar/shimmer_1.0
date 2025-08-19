#!/usr/bin/env bash
set -euo pipefail

# One-shot: fine-tune a Mistral LoRA and create an Ollama model.

DATASET="$(dirname "$0")/training_data.fixed.jsonl"
[[ -f "$DATASET" ]] || { echo "FATAL: $DATASET not found. Run the generator + repair first." >&2; exit 1; }

OUTDIR="$(dirname "$0")/adapters"
mkdir -p "$OUTDIR"

echo "[1/3] Training LoRA: Mistral (HF/PEFT)"
HF_MISTRAL="mistralai/Mistral-7B-Instruct-v0.3" BATCH="${BATCH:-4}" GRAD_ACCUM="${GRAD_ACCUM:-2}" EPOCHS="${EPOCHS:-3}" MAX_SEQ_LEN="${MAX_SEQ_LEN:-2048}" \
  python3 "$(dirname "$0")/train_mistral_lora.py"

cat >"$(dirname "$0")/Modelfile.mistral" <<'MF'
FROM mistral:7b-instruct
SYSTEM """
You are a Shimmer language expert. You can translate between English and the Shimmer protocol language, and you can answer questions about the Shimmer specification.
"""
ADAPTER ./adapters/mistral_lora
MF

echo "[2/3] Creating Ollama model shimmer-mistral"
ollama create shimmer-mistral -f "$(dirname "$0")/Modelfile.mistral"

echo "[3/3] Sanity test (en→sh)"
python3 "$(dirname "$0")/../tools/shimmer_cli.py" en2sh "Plan dataset 03 in 30 minutes" --provider ollama --model shimmer-mistral || true

echo "Done. Model: shimmer-mistral"

