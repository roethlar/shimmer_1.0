#!/usr/bin/env bash
set -euo pipefail

# Train a LoRA on a local FP16 base (no HF), then create an Ollama model.
# Usage:
#   BASE_DIR=/path/to/base  OLLAMA_BASE=llama3.2:latest  bash model_training/train_ollama_local_lora.sh

[[ -n "${BASE_DIR:-}" ]] || { echo "FATAL: set BASE_DIR to local FP16 base dir" >&2; exit 1; }
[[ -n "${OLLAMA_BASE:-}" ]] || { echo "FATAL: set OLLAMA_BASE to an existing Ollama base tag" >&2; exit 1; }

DIR="$(dirname "$0")"
ADAPTER_DIR="$DIR/adapters/local_lora"

echo "[1/3] Training LoRA on local base: $BASE_DIR"
BASE_DIR="$BASE_DIR" BATCH="${BATCH:-4}" GRAD_ACCUM="${GRAD_ACCUM:-2}" EPOCHS="${EPOCHS:-3}" MAX_SEQ_LEN="${MAX_SEQ_LEN:-2048}" \
  python3 "$DIR/train_local_lora.py"

echo "[2/3] Creating Modelfile.local for Ollama base: $OLLAMA_BASE"
cat >"$DIR/Modelfile.local" <<MF
FROM $OLLAMA_BASE

SYSTEM """
You are a Shimmer language expert. You can translate between English and the Shimmer protocol language, and you can answer questions about the Shimmer specification.
"""

# Point ADAPTER to the directory that contains adapter_config.json
ADAPTER ./adapters/local_lora
MF

echo "[3/3] Creating Ollama model shimmer-local"
ollama create shimmer-local -f "$DIR/Modelfile.local"
echo "Done. Try: ollama run shimmer-local"

