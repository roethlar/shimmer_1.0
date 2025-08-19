#!/usr/bin/env bash
set -euo pipefail

# One-shot: fine-tune a Qwen LoRA on the fixed dataset and create an Ollama model.

DATASET="$(dirname "$0")/training_data.fixed.jsonl"
[[ -f "$DATASET" ]] || { echo "FATAL: $DATASET not found. Run the generator + repair first." >&2; exit 1; }

if ! command -v python3 >/dev/null 2>&1; then
  echo "FATAL: python3 not found" >&2; exit 1
fi

OUTDIR="$(dirname "$0")/adapters"
mkdir -p "$OUTDIR"

# Qwen base (HuggingFace)
HF_QWEN="Qwen/Qwen2.5-7B-Instruct"

echo "[1/3] Training LoRA: Qwen (HF/TRL/PEFT)"
HF_QWEN="$HF_QWEN" python3 "$(dirname "$0")/train_qwen_lora.py"

cat >"$(dirname "$0")/Modelfile.qwen" <<'MF'
FROM qwen2.5:latest
SYSTEM """
You are a Shimmer language expert. You can translate between English and the Shimmer protocol language, and you can answer questions about the Shimmer specification.
"""
# Point to the adapter directory so Ollama can read adapter_config.json
ADAPTER ./adapters/qwen_lora
MF

echo "[2/3] Creating Ollama model shimmer-qwen"
ollama create shimmer-qwen -f "$(dirname "$0")/Modelfile.qwen"

echo "[3/3] Sanity test (en→sh)"
python3 "$(dirname "$0")/../tools/shimmer_cli.py" en2sh "Plan dataset 03 in 30 minutes" --provider ollama --model shimmer-qwen || true

echo "Done. Model: shimmer-qwen"
