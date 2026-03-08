#!/usr/bin/env python3
"""
test_score.py — Sanity-check LLM scoring without running LinkedIn.

Usage (from project root):
    python scripts/test_score.py

What it does:
    1. Loads your private/profile_summary.txt
    2. Scores a hardcoded sample job with the configured model
    3. Prints the JSON result and whether an email would be triggered
"""
import json
import sys
from pathlib import Path

# Add project root to path so 'app.*' imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
import yaml

load_dotenv(Path("secrets/.env"))

with open("config/search.yaml") as f:
    cfg = yaml.safe_load(f)

# ── Check profile exists ──────────────────────────────────────────────────────
profile_path = Path("private/profile_summary.txt")
if not profile_path.exists():
    print("ERROR: private/profile_summary.txt not found.")
    print("Run:  cp private/profile_summary.example.txt private/profile_summary.txt")
    print("Then fill in your actual background.")
    sys.exit(1)

profile = profile_path.read_text().strip()

# ── Sample job (edit freely to test different scenarios) ──────────────────────
SAMPLE_JOB = {
    "title":       "Senior Computational Biologist — Single-Cell Genomics",
    "company":     "Acme Biotech",
    "location":    "San Francisco, CA (Hybrid)",
    "url":         "https://www.linkedin.com/jobs/view/9999999999/",
    "description": """\
We are hiring a Senior Computational Biologist to join our single-cell genomics team.

Responsibilities:
- Develop and maintain bioinformatics pipelines for scRNA-seq, ATAC-seq, and spatial
  transcriptomics data
- Apply machine learning methods to discover novel cell states and disease biomarkers
- Collaborate closely with experimental scientists on study design and data interpretation
- Contribute to peer-reviewed publications and internal research reports

Requirements:
- PhD in Bioinformatics, Computational Biology, or a closely related field
- 3+ years of hands-on experience with single-cell genomics data analysis
- Proficient in Python (scanpy, anndata) and/or R (Seurat, Bioconductor)
- Familiarity with deep learning (PyTorch or TensorFlow) is a strong plus
- Cloud computing experience (AWS or GCP) preferred
- Track record of publications in peer-reviewed journals

What we offer:
- Competitive base salary: $155,000–$195,000
- Equity (series B, fast-growing company)
- Flexible hybrid schedule (2 days on-site in SF)
- Comprehensive health benefits
""",
}

# ── Run scoring ───────────────────────────────────────────────────────────────
from app.score_jobs import score_job

model     = cfg.get("llm_model", "claude-sonnet-4-5")
threshold = int(cfg.get("fit_threshold", 60))

print(f"\nScoring: {SAMPLE_JOB['title']} @ {SAMPLE_JOB['company']}")
print(f"Model:   {model}   |   Threshold: {threshold}")
print("─" * 60)

result = score_job(SAMPLE_JOB, profile, model=model)

if result:
    print(json.dumps(result, indent=2))
    print("─" * 60)
    score = result["fit_score"]
    if score >= threshold:
        print(f"✓  Would TRIGGER email alert  ({score} >= {threshold})")
    else:
        print(f"✗  Would NOT trigger alert  ({score} < {threshold})")
else:
    print("ERROR: Scoring failed — check ANTHROPIC_API_KEY and model name.")
    sys.exit(1)
