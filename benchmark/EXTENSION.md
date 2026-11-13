# Extension protocol: strategies D/E and fresh holdout test2

Written 2026-11-13 **after** the A/B/C results (dev and test) were seen and **before** D/E were implemented or any question in test2 was run. This is a post-hoc extension. It does not replace the pre-registered A/B/C results in `README.md` of this folder.

## Why

The A/B/C analysis (`results/failure_diagnosis.csv`) found that:
- A splits evidence across chunks (6/21 questions).
- 239/330 B chunks exceed the model's 128-token window, so their tail is never embedded (evidence beyond the window in 4/21 questions).
- B creates heading-only chunks that take top-3 slots.

As a result, the A–B comparison mixes "chunking strategy" with "chunk exceeds the model window".

## Design (fixed before implementation)

| | Chunking | Filter |
|---|---|---|
| **D** | Sentence-aware packing within each page. Whitespace is normalised, the page is split into sentences (and before bullet `•`), and consecutive sentences are packed while the chunk stays ≤128 tokens with the model's own tokenizer (special tokens included). A single sentence longer than 128 tokens is split on word boundaries. No overlap, same as B. | none |
| **E** | Same chunks as D | `document_type`, only for questions that carry a filter, same as C |

Corpus, eligible pages, metadata fields, embedding model, Chroma and cosine metric are unchanged.
- **B vs D** changes only the chunking rule: paragraph ≤1000 chars vs sentence-packed ≤128 tokens.
- **D vs E** changes only the filter.

## Hypotheses (written before running)

- D: 0 chunks over the model window. Fewer evidence splits than A, because chunks end on sentence boundaries. Dev Evidence Hit@3 ≥ B.
- Risk: with no overlap and a 128-token cap, evidence spanning two sentence groups (long quotes such as q04, q18) may still be split.
- Coherence: should be above A, because there are no mid-word cuts. It may be below B, because chunks are shorter and carry less context.
- E: filter compliance 100% on filter questions. Hit changes only on those questions.

## Fresh holdout: test2

- `questions_test2.jsonl` has 7 new questions (q22–q28) written from pages that no earlier question uses: AI 100-1 p21, p22; AI 600-1 p12, p14.
- 2 of them are filter questions (q27 profile, q28 framework), each targeting a concept both documents state (bias amplification, privacy).
- Evidence is verified by `src/05_verify_benchmark.py`. The file is committed before any strategy is run on it.
- The original test set (q16–q21) **has been seen** and is reported for D/E only as a non-independent check.

## Selection rule for the extension (fixed now)

1. Among A–E, the highest dev Evidence Hit@3.
2. Tie-break: dev Hit@1.
3. Tie-break: fewer chunks.
4. If two strategies differ only by the filter (B/C, D/E), prefer the filtered one when its dev filter compliance is higher.

The chosen strategy and all others are then reported once on test2.

**Known bias:** D was designed after looking at dev and test failures, so dev results favour D. Test2 is the only unbiased comparison.
