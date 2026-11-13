# Benchmark protocol (frozen before any retrieval run)

Written and verified on 2026-11-13 **before** any retrieval or scoring. Nothing in this folder may be changed after test results are seen; if that happens it is recorded in the report and the test set is no longer an independent holdout.

## Files

| File | Content |
|---|---|
| `questions.jsonl` | 21 questions: `id`, `split`, `type`, `question`, `expected_answer`, `gold_source_id`, `gold_page`, `evidence_quote`, `filter`, `alternative_gold` |
| `coherence_positions.json` | The 10 fixed source positions for the chunk-coherence audit |

Verify with `python src/05_verify_benchmark.py`. It checks that every evidence quote (primary and alternative) exists verbatim, after whitespace normalisation, on its gold page; that every gold page is an eligible (indexed) page; that the filter value matches the gold page metadata; and that the split and filter counts are met.

## Split: 15 dev / 6 test

- **Dev (q01–q15):** AI 100-1 sections 1–3 and 5 (Framing Risk, Trustworthiness, Core, Appendix C) and AI 600-1 sections 1–2 (Introduction, the 12 GAI risks, confabulation), the action-ID convention and the red-teaming definition (A.1.5).
- **Test (q16–q21):** different pages and topics that no dev question uses: AI 100-1 Appendix B (p43), section 4 Effectiveness (p24) and the bias categories (p23); AI 600-1 Value Chain risk (p9), content provenance (p55) and the profile's definition of risk (p6).
- Question types: direct, paraphrase, condition/exception and metadata_filter. There are 4 filter questions: q14 and q15 in dev, q20 and q21 in test.

**Leakage risks (recorded honestly):**
- The two test filter questions (q20, q21) use the same template as the dev filter questions ("In the <document> …"). Tuning on dev could therefore favour this phrasing.
- q20 (test) and q15 (dev) both sit on AI 600-1 pages near the start of section 2 or in the action tables. The pages differ (p6 vs p17), but neighbouring chunks may overlap in topic.
- q10 (dev) has an alternative gold on p51 (Appendix A). Test question q19 uses p55 in the same appendix, but the page and topic differ.
- The question author is also the person who labels the audit (author bias). See the report.

## Filter design

- The filter field is `document_type` ∈ {`framework`, `profile`}, taken from `sources.json` (the publication's own title: Framework vs Generative AI Profile).
- The filter value is **supplied by the user in the question** ("In the Generative AI Profile…"). It is treated as context known before retrieval, never derived from the gold answer.
- Strategy C applies the filter **only** to questions whose `filter` is non-null. For the other 17 questions C runs unfiltered, so its result equals B for them by construction.
- **Limitation:** the corpus has only two documents, so `document_type` maps 1:1 to `document_id`. The filter tests scope restriction, not discrimination among many documents.
- Each filter question targets a concept that **both** documents state in similar wording (risk definition, AI Actors definition, human-AI configuration, bias). Without the filter, the other document's page is a strong distractor.

## Metrics (identical for A, B and C)

- **Hit** = a retrieved chunk whose `document_id` and `page` match a gold entry (primary or alternative) **and** whose text contains the full evidence quote (whitespace-normalised).
- **Hit@1** = questions with a hit at rank 1 / questions in the split. **Evidence Hit@3** = questions with at least one hit in the top 3 / questions in the split. Reported as n/N, separately for dev and test.
- **Supplementary (does not replace the main metric):** Page Hit@3, meaning the gold page appears in the top 3 even if the quote is split across chunks. This is used to diagnose evidence fragmentation.
- **Filter compliance** = filter questions whose 3 results all satisfy the filter / filter questions in the split. Reported as N/A when the split has none.

## Manual audit (labelled after the runs, using fixed samples)

- **Coherence:** for each strategy, the chunk covering each of the 10 positions in `coherence_positions.json` (rule: eligible pages sorted by `page_id`, indices round(i·(N−1)/9), offset at the middle of the page). Scale 0 = cut mid-idea or missing subject, cannot be understood; 1 = partially understandable, missing context; 2 = self-contained, complete idea.
- **Metadata:** all 6 test questions × top 3 × each strategy. Check `document_id`, `source`, `page` and `document_type` against the source page, i.e. that the chunk text really is on that page of that document.
- **Grounding:** all 6 test questions × each strategy, judged on the top 3. Scale 0 = no evidence; 1 = evidence present but missing a needed condition or context; 2 = sufficient to answer and traceable. This scores retrieved evidence, **not** the correctness of an LLM answer.

## Strategy selection rule (fixed before looking at test)

1. Highest **dev Evidence Hit@3**.
2. Tie-break: higher dev Hit@1.
3. Tie-break: fewer chunks and lower ingest time.

Test results are reported once, after the strategy is chosen on dev, and are not used for tuning.
