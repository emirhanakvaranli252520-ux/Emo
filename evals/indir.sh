#!/usr/bin/env bash
# Eval veri setlerini evals/veri/ altına indirir (repoya eklenmez).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p veri
HF=https://huggingface.co/datasets
curl -fsSL -o veri/hallucination-benchmark.json \
  "$HF/LawChatAI/turkish-legal-statutory-hallucination-benchmark/resolve/main/turkish-legal-hallucination-benchmark.json"
curl -fsSL -o veri/turklegalrag-benchmark.csv \
  "$HF/CtnkyaABC/turkish-law-corpus/resolve/main/benchmark/benchmark.csv"
ls -la veri
