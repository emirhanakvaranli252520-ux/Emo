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
# Mizan (AlicanKiraz0) — 20 zor vaka + soru bankası; CC-BY-NC-4.0, yalnız iç değerlendirme
SP=https://huggingface.co/spaces/AlicanKiraz0/Mizan-27B-Turkish-Legal-Decision-Model/resolve/37edd4c5da86311ae10bb724563e3d31a14ba5df
curl -fsSL -o veri/mizan-hard-cases-20.jsonl "$SP/data/examples/hard_cases_20.jsonl"
curl -fsSL -o veri/mizan-question-bank.yaml "$SP/data/question_bank.yaml"
ls -la veri
