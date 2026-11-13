"""Run every benchmark question against strategies A, B, C; save full top-3 traces and metrics.

Hit definition (benchmark/README.md): a retrieved chunk whose document_id + page match a gold
entry AND whose text contains the full evidence quote (whitespace-normalised).
C applies the metadata filter only to questions that carry one; other questions run unfiltered.
"""
import csv
import json
import time
from datetime import datetime, timezone
from common import ROOT, ARTIFACTS, iter_jsonl, write_json, write_jsonl

RESULTS = ROOT / 'results'
STRATEGIES = 'ABCDE'
TOP_K = 3


def squash(text):
    return ' '.join(text.split())


def gold_entries(q):
    yield q['gold_source_id'], q['gold_page'], q['evidence_quote']
    for alt in q.get('alternative_gold', []):
        yield alt['source_id'], alt['page'], alt['evidence_quote']


def judge(q, metadata, text):
    page_hit = evidence_hit = False
    for source_id, page, quote in gold_entries(q):
        if metadata['document_id'] == source_id and int(metadata['page']) == int(page):
            page_hit = True
            if squash(quote) in squash(text):
                evidence_hit = True
    return page_hit, evidence_hit


def ratio(rows, key):
    return {'n': sum(r[key] for r in rows), 'N': len(rows)}


def main():
    import chromadb
    from sentence_transformers import SentenceTransformer
    ingest = json.loads((ARTIFACTS / 'ingestion_metrics.json').read_text(encoding='utf-8'))
    model_name = ingest['embedding_model']
    encoder = SentenceTransformer(model_name)
    client = chromadb.PersistentClient(path=str(ARTIFACTS / 'chroma'))
    questions = list(iter_jsonl(ROOT / 'benchmark' / 'questions.jsonl')) + list(iter_jsonl(ROOT / 'benchmark' / 'questions_test2.jsonl'))
    run_at = datetime.now(timezone.utc).isoformat()

    t0 = time.perf_counter()
    qvecs = encoder.encode([q['question'] for q in questions], normalize_embeddings=True)
    embed_seconds = time.perf_counter() - t0

    summary, csv_rows = [], []
    for strategy in STRATEGIES:
        coll = client.get_collection(f'nist_rmf_{strategy.lower()}')
        traces = []
        t1 = time.perf_counter()
        for q, vec in zip(questions, qvecs):
            use_filter = strategy in ('C', 'E') and bool(q.get('filter'))
            opts = {'query_embeddings': [vec.tolist()], 'n_results': TOP_K,
                    'include': ['metadatas', 'documents', 'distances']}
            if use_filter:
                opts['where'] = q['filter']
            res = coll.query(**opts)
            results = []
            for rank, (cid, doc, meta, dist) in enumerate(zip(res['ids'][0], res['documents'][0], res['metadatas'][0], res['distances'][0]), start=1):
                page_hit, evidence_hit = judge(q, meta, doc)
                results.append({'rank': rank, 'chunk_id': cid, 'cosine_distance': round(dist, 6),
                                'similarity': round(1 - dist, 6), 'metadata': meta, 'text': doc,
                                'page_hit': page_hit, 'evidence_hit': evidence_hit})
            flt = q.get('filter') or {}
            compliant = all(all(r['metadata'].get(k) == v for k, v in flt.items()) for r in results) if flt else None
            traces.append({
                'run_at': run_at, 'strategy': strategy, 'question_id': q['id'], 'split': q['split'],
                'type': q['type'], 'question': q['question'], 'expected_answer': q['expected_answer'],
                'gold': [{'source_id': s, 'page': p, 'evidence_quote': e} for s, p, e in gold_entries(q)],
                'filter_requested': q.get('filter'), 'filter_applied': q['filter'] if use_filter else None,
                'hit_at_1': bool(results and results[0]['evidence_hit']),
                'evidence_hit_at_3': any(r['evidence_hit'] for r in results),
                'page_hit_at_3': any(r['page_hit'] for r in results),
                'filter_compliant_top3': compliant, 'results': results})
        query_seconds = time.perf_counter() - t1
        write_jsonl(RESULTS / f'traces_{strategy}.jsonl', traces)

        for split in ('dev', 'test', 'test2', 'all'):
            rows = [t for t in traces if (split == 'all' and t['split'] in ('dev', 'test')) or t['split'] == split]
            frows = [t for t in rows if t['filter_requested']]
            row = {'strategy': strategy, 'split': split,
                   'hit_at_1': ratio(rows, 'hit_at_1'),
                   'evidence_hit_at_3': ratio(rows, 'evidence_hit_at_3'),
                   'page_hit_at_3': ratio(rows, 'page_hit_at_3'),
                   'filter_compliance': ratio(frows, 'filter_compliant_top3') if frows else 'N/A',
                   'query_seconds_all_questions': round(query_seconds, 3)}
            summary.append(row)
            fc = row['filter_compliance']
            csv_rows.append([strategy, split, f"{row['hit_at_1']['n']}/{row['hit_at_1']['N']}",
                             f"{row['evidence_hit_at_3']['n']}/{row['evidence_hit_at_3']['N']}",
                             f"{row['page_hit_at_3']['n']}/{row['page_hit_at_3']['N']}",
                             fc if fc == 'N/A' else f"{fc['n']}/{fc['N']}"])

    write_json(RESULTS / 'retrieval_metrics.json', {
        'run_at': run_at, 'embedding_model': model_name, 'top_k': TOP_K,
        'question_embedding_seconds': round(embed_seconds, 3),
        'hit_definition': 'document_id+page match a gold entry AND chunk contains full evidence quote (whitespace-normalised)',
        'metrics': summary})
    with (RESULTS / 'retrieval_metrics.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['strategy', 'split', 'hit@1', 'evidence_hit@3', 'page_hit@3 (supplementary)', 'filter_compliance'])
        w.writerows(csv_rows)
    for r in csv_rows:
        print(' | '.join(r))


if __name__ == '__main__':
    main()
