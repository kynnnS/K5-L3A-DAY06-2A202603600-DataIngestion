"""Check every gold evidence quote exists verbatim (whitespace-normalized) on its gold page.

Run before any retrieval. Also checks split sizes and filter coverage required by BENCHMARK.md.
"""
import sys
from collections import Counter
from common import ROOT, PROCESSED, iter_jsonl

BENCH = ROOT / 'benchmark' / 'questions.jsonl'


def squash(text):
    return ' '.join(text.split())


def gold_entries(q):
    yield q['gold_source_id'], q['gold_page'], q['evidence_quote']
    for alt in q.get('alternative_gold', []):
        yield alt['source_id'], alt['page'], alt['evidence_quote']


def main():
    pages = {(p['document_id'], p['page']): p for p in iter_jsonl(PROCESSED / 'pages.jsonl')}
    questions = list(iter_jsonl(BENCH))
    test2_path = ROOT / 'benchmark' / 'questions_test2.jsonl'
    test2 = list(iter_jsonl(test2_path)) if test2_path.exists() else []
    errors = []
    for q in questions + test2:
        for source_id, page, quote in gold_entries(q):
            p = pages.get((source_id, page))
            if p is None:
                errors.append(f'{q["id"]}: page {source_id} p{page} not found')
            elif squash(quote) not in squash(p['text']):
                errors.append(f'{q["id"]}: evidence not found on {source_id} p{page}')
            elif not p.get('eligible_content_page'):
                errors.append(f'{q["id"]}: gold page {source_id} p{page} is not an eligible (indexed) page')
            if q.get('filter') and q['filter'].get('document_type') != p['document_type']:
                errors.append(f'{q["id"]}: filter does not match gold page document_type')
    ids = [q['id'] for q in questions + test2]
    if test2:
        print(f'Fresh holdout test2: {len(test2)} questions, {sum(bool(q.get("filter")) for q in test2)} with filter')
        if any(q['split'] != 'test2' for q in test2):
            errors.append('questions_test2.jsonl must only contain split=test2')
    splits = Counter(q['split'] for q in questions)
    filtered = Counter(q['split'] for q in questions if q.get('filter'))
    print(f'Questions: {len(questions)} | splits: {dict(splits)} | filter questions: {dict(filtered)}')
    if len(set(ids)) != len(ids):
        errors.append('duplicate question IDs')
    if len(questions) < 20 or splits['dev'] < 15 or splits['test'] < 5:
        errors.append('need >=20 questions with >=15 dev and >=5 test')
    if sum(filtered.values()) < 3 or filtered['test'] < 1:
        errors.append('need >=3 filter questions with >=1 in test')
    for e in errors:
        print('ERROR', e)
    if errors:
        sys.exit(1)
    print('BENCHMARK VERIFIED: every evidence quote found verbatim on its gold page.')


if __name__ == '__main__':
    main()
