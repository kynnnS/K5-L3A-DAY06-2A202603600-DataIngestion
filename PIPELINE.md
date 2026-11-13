# Day 06 — Part 1 + Part 2: NIST AI RMF corpus & ingestion

This package provides **reproducible source acquisition** and **real semantic-vector ingestion**. It contains **no fabricated PDF contents, embeddings, runtime logs, or evaluation scores**. Sources and their access URLs were web-verified on 2026-11-13.

## Part 1: Real, verifiable corpus

- NIST AI 100-1: AI Risk Management Framework (AI RMF 1.0), published 2023-01-26. DOI: https://doi.org/10.6028/NIST.AI.100-1
- NIST AI 600-1: AI RMF Generative AI Profile, published 2024-07-26. DOI: https://doi.org/10.6028/NIST.AI.600-1

Source provenance, date, and permission caveats in `sources.json`. Source data must remain genuine. US federal government-authored text is generally public domain in the US; **do not assume third-party content, seals, logos, or every illustration has the same licensing status**. Use official URLs and keep PDFs out of public repository until reuse conditions are checked.

Physical page numbers are 1-based PDF page indices, **not printed page labels**. The manifest records every physical page, extracted character count, and `candidate_content_page` flag. The automatic heuristic (>=800 normalized characters) **is not a human determination of a valid page**. Manually review cover, table of contents, references and scan failures, and claim >=30 eligible pages only after review. No duplicated pages for volume. Raw PDFs are downloaded locally, not redistributed.

## Local setup (Python 3.12.5)

```bash
uv python install 3.12.5
uv venv --python 3.12.5 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
python src/01_download.py
python src/02_extract.py
```

Inspect `data/processed/manifest.json` and `pages.jsonl`. To confirm count, audit pages for cover/TOC/reference; `candidate_content_pages_total` is only a preliminary count.

## Part 2: Real embedding + Chroma persistent vector database

```bash
python src/03_ingest.py
python src/04_query.py --strategy A --question "What are the four core functions of the AI RMF?"
python src/04_query.py --strategy B --question "What are the four core functions of the AI RMF?"
python src/04_query.py --strategy C --document-type framework --question "What are the four core functions of the AI RMF?"
python src/04_query.py --strategy C --document-type profile --question "What risks are associated with generative AI?"
```

Embedding: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (real model, local download; no API key). The output embedding dimension is obtained from the actual model at runtime. Storage: **persistent Chroma**, cosine; collections `nist_rmf_a`, `nist_rmf_b`, `nist_rmf_c`. A: fixed 500 characters + 50 overlap; B: paragraph-oriented <=1000 characters; C: same chunks as B plus optional `document_type` filter on provided query context only. Metadata: `document_id`, `source`, `page`, `page_id`, `document_type`, `year`, `language`, `strategy`, `chunk_index`, `start_char`, `end_char_approx`.

Every ingestion run recreates the three collections to avoid duplicates. Files generated during local execution: `data/download_receipts.json`, `data/processed/pages.jsonl`, `data/processed/manifest.json`, `data/processed/chunks_[ABC].jsonl`, `artifacts/chroma/`, `artifacts/ingestion_metrics.json`. **Benchmark and 20 verified QAs are separate deliverables.**

## Known limitations and QA controls

1. PDF extraction uses PyMuPDF text and no OCR: image-only pages are marked `empty_or_scanned`.
2. Auto count >=800 chars can include long reference pages; manual eligible-page audit is necessary.
3. Paragraph chunking is page-contained, so evidence spanning two pages cannot be in one chunk. Long paragraph breaks may cut mid-sentence.
4. `start_char` for paragraph chunks is approximate when joined with separators; **use page ID and full chunk text as authoritative evidence**.
5. NIST web pages may describe revisions; these DOI-linked PDFs are fixed historical versions (2023 and 2024).
6. Running an API-free local model still requires internet for the first model download.
7. No hardcoded presumed benchmark metrics, scores, or page counts.

Declare AI assistance and check generated code locally before submission.
