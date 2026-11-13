"""Failure diagnosis: for each question x strategy, locate the chunk(s) that contain the full
evidence quote and report (a) whether any chunk contains it at all (fragmentation), (b) its rank
among ALL chunks in the collection, and (c) whether the quote starts beyond the model's
max_seq_length (i.e. in the truncated tail that was never embedded).
"""
import csv
import json
from common import ROOT, ARTIFACTS, PROCESSED, iter_jsonl

RESULTS = ROOT / 'results'


def squash(text):
    return ' '.join(text.split())


def main():
    import chromadb
    from sentence_transformers import SentenceTransformer
    ingest = json.loads((ARTIFACTS / 'ingestion_metrics.json').read_text(encoding='utf-8'))
    encoder = SentenceTransformer(ingest['embedding_model'])
    tok = encoder.tokenizer
    max_len = encoder.max_seq_length
    client = chromadb.PersistentClient(path=str(ARTIFACTS / 'chroma'))
    questions = list(iter_jsonl(ROOT / 'benchmark' / 'questions.jsonl'))
    qvecs = encoder.encode([q['question'] for q in questions], normalize_embeddings=True)
    rows = []
    for strategy in 'ABC':
        coll = client.get_collection(f'nist_rmf_{strategy.lower()}')
        chunks = list(iter_jsonl(PROCESSED / f'chunks_{strategy}.jsonl'))
        n_all = coll.count()
        for q, vec in zip(questions, qvecs):
            golds = [(q['gold_source_id'], q['gold_page'], q['evidence_quote'])] + \
                    [(a['source_id'], a['page'], a['evidence_quote']) for a in q.get('alternative_gold', [])]
            containing = [(c, quote) for c in chunks for s, p, quote in golds
                          if c['metadata']['document_id'] == s and c['metadata']['page'] == p
                          and squash(quote) in squash(c['text'])]
            use_filter = strategy == 'C' and bool(q.get('filter'))
            opts = {'query_embeddings': [vec.tolist()], 'n_results': n_all, 'include': []}
            if use_filter:
                opts['where'] = q['filter']
            ranked = coll.query(**opts)['ids'][0]
            best = None
            for c, quote in containing:
                rank = ranked.index(c['id']) + 1 if c['id'] in ranked else None
                # token position where the quote starts inside the chunk
                start_char = squash(c['text']).find(squash(quote))
                prefix_tokens = len(tok(squash(c['text'])[:start_char], add_special_tokens=True)['input_ids'])
                quote_tokens = len(tok(squash(quote), add_special_tokens=False)['input_ids'])
                info = {'chunk_id': c['id'], 'rank_in_collection': rank,
                        'quote_start_token': prefix_tokens, 'quote_end_token': prefix_tokens + quote_tokens,
                        'quote_fully_embedded': prefix_tokens + quote_tokens <= max_len,
                        'quote_start_truncated': prefix_tokens >= max_len}
                if best is None or (rank or 10**9) < (best['rank_in_collection'] or 10**9):
                    best = info
            rows.append({'strategy': strategy, 'question_id': q['id'], 'split': q['split'], 'type': q['type'],
                         'filter_applied': json.dumps(q['filter']) if use_filter else '',
                         'chunks_containing_full_evidence': len(containing),
                         'evidence_fragmented': len(containing) == 0,
                         **(best or {'chunk_id': '', 'rank_in_collection': '', 'quote_start_token': '',
                                     'quote_end_token': '', 'quote_fully_embedded': '', 'quote_start_truncated': ''}),
                         'collection_size_searched': len(ranked)})
    path = RESULTS / 'failure_diagnosis.csv'
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    for s in 'ABC':
        sr = [r for r in rows if r['strategy'] == s]
        print(f"{s}: evidence fragmented (no chunk holds full quote) {sum(r['evidence_fragmented'] for r in sr)}/21 | "
              f"quote not fully inside embedded window {sum(r['quote_fully_embedded'] is False for r in sr)}/21 | "
              f"quote starts in truncated tail {sum(r['quote_start_truncated'] is True for r in sr)}/21")
    print('written', path)


if __name__ == '__main__':
    main()
