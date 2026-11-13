"""Export the fixed manual-audit samples (coherence, metadata, grounding) to results/audit/.

Labels are filled in afterwards in the *_labels.csv files; this script never invents labels.
The metadata sheet also records a mechanical check: is the chunk text really on the page that
its metadata claims, and do source / document_type / year match sources.json?
"""
import csv
import json
from common import ROOT, PROCESSED, read_json, iter_jsonl

RESULTS = ROOT / 'results'
AUDIT = RESULTS / 'audit'


def squash(text):
    return ' '.join(text.split())


def chunk_span(chunk, page_text):
    """Span of the chunk in raw page coordinates. D/E chunks are whitespace-normalised, so they
    are located in the normalised page text and mapped back to a raw offset."""
    pos = page_text.find(chunk['text'])
    if pos >= 0:
        return pos, pos + len(chunk['text']), 'exact'
    flat, target = squash(page_text), squash(chunk['text'])
    fpos = flat.find(target)
    if fpos >= 0:
        # map normalised offsets back to raw offsets (a whitespace run counts as one character)
        start = end = None
        k = 0
        for i, ch in enumerate(page_text):
            if ch.isspace() and (i == 0 or page_text[i - 1].isspace()):
                continue
            if k == fpos and start is None:
                start = i
            k += 1
            if k == fpos + len(target):
                end = i + 1
                break
        if start is not None and end is not None:
            return start, end, 'normalised'
    m = chunk['metadata']
    return m['start_char'], m['end_char_approx'], 'metadata_approx'


def main():
    AUDIT.mkdir(parents=True, exist_ok=True)
    pages = {p['page_id']: p for p in iter_jsonl(PROCESSED / 'pages.jsonl')}
    sources = {s['source_id']: s for s in read_json(ROOT / 'sources.json')}
    positions = read_json(ROOT / 'benchmark' / 'coherence_positions.json')['positions']

    # 1) Coherence: chunk covering each fixed position, per strategy.
    rows = []
    for strategy in 'ABCDE':
        chunks = [c for c in iter_jsonl(PROCESSED / f'chunks_{strategy}.jsonl')]
        for pos in positions:
            page_text = pages[pos['page_id']]['text']
            covering = []
            for c in chunks:
                if c['metadata']['page_id'] != pos['page_id']:
                    continue
                start, end, how = chunk_span(c, page_text)
                if start <= pos['char_offset'] < end:
                    covering.append((c, how))
            c, how = covering[0] if covering else (None, 'none')
            rows.append({'strategy': strategy, 'position_id': pos['position_id'], 'page_id': pos['page_id'],
                         'char_offset': pos['char_offset'], 'chunk_id': c['id'] if c else '',
                         'covering_chunks': len(covering), 'span_method': how,
                         'chunk_chars': len(c['text']) if c else 0,
                         'chunk_text': c['text'] if c else '', 'label_0_2': '', 'reason': ''})
    write_csv(AUDIT / 'coherence_samples.csv', rows)

    # 2) Metadata + 3) Grounding: all test questions, top-3, per strategy.
    meta_rows, ground_rows = [], []
    for strategy in 'ABCDE':
        for t in iter_jsonl(RESULTS / f'traces_{strategy}.jsonl'):
            if t['split'] not in ('test', 'test2'):
                continue
            for r in t['results']:
                m = r['metadata']
                page = pages.get(m['page_id'])
                src = sources.get(m['document_id'], {})
                text_on_page = bool(page) and squash(r['text']) in squash(page['text'])
                checks = {
                    'text_on_claimed_page': text_on_page,
                    'page_id_consistent': bool(page) and page['document_id'] == m['document_id'] and page['page'] == m['page'],
                    'source_matches': m['source'] == src.get('url'),
                    'document_type_matches': m['document_type'] == src.get('document_type'),
                    'year_matches': m['year'] == int(src.get('issued_at', '0000')[:4]),
                }
                flt = t['filter_requested'] or {}
                meta_rows.append({'strategy': strategy, 'split': t['split'], 'question_id': t['question_id'], 'rank': r['rank'],
                                  'chunk_id': r['chunk_id'], 'document_id': m['document_id'], 'page': m['page'],
                                  'document_type': m['document_type'], 'year': m['year'], **checks,
                                  'all_fields_correct': all(checks.values()),
                                  'filter_requested': json.dumps(flt) if flt else '',
                                  'satisfies_filter': all(m.get(k) == v for k, v in flt.items()) if flt else ''})
            ground_rows.append({'strategy': strategy, 'split': t['split'], 'question_id': t['question_id'], 'question': t['question'],
                                'expected_answer': t['expected_answer'],
                                'gold': '; '.join(f"{g['source_id']} p{g['page']}" for g in t['gold']),
                                'evidence_hit_at_3_auto': t['evidence_hit_at_3'],
                                'top3': '\n---\n'.join(f"[{r['rank']}] {r['metadata']['document_id']} p{r['metadata']['page']} (sim {r['similarity']:.3f})\n{r['text']}" for r in t['results']),
                                'label_0_2': '', 'reason': ''})
    write_csv(AUDIT / 'metadata_audit.csv', meta_rows)
    write_csv(AUDIT / 'grounding_samples.csv', ground_rows)
    print(f'coherence rows: {len(rows)} | metadata rows: {len(meta_rows)} | grounding rows: {len(ground_rows)}')
    print('Mechanical metadata check, all fields correct:', sum(r['all_fields_correct'] for r in meta_rows), '/', len(meta_rows))


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


if __name__ == '__main__':
    main()
