"""Summarise manual labels and mechanical metadata checks into results/audit_summary.json."""
import csv
import json
from collections import Counter
from common import ROOT, write_json

AUDIT = ROOT / 'results' / 'audit'


def read(name):
    with (AUDIT / name).open(encoding='utf-8') as f:
        return list(csv.DictReader(f))


def main():
    coherence, grounding, meta = read('coherence_labels.csv'), read('grounding_labels.csv'), read('metadata_audit.csv')
    out = {'labeller': 'AI-assisted (Claude Code) draft labels, to be reviewed by the student; author bias noted',
           'strategies': {}}
    for s in 'ABC':
        c = [int(r['label_0_2']) for r in coherence if r['strategy'] == s]
        g = [int(r['label_0_2']) for r in grounding if r['strategy'] == s]
        m = [r for r in meta if r['strategy'] == s]
        f = [r for r in m if r['filter_requested']]
        fq = {}
        for r in f:
            fq.setdefault(r['question_id'], []).append(r['satisfies_filter'] == 'True')
        gc = Counter(g)
        out['strategies'][s] = {
            'coherence_mean_of_2': round(sum(c) / len(c), 2), 'coherence_n': len(c),
            'coherence_counts_0_1_2': [c.count(0), c.count(1), c.count(2)],
            'metadata_all_fields_correct': f"{sum(r['all_fields_correct'] == 'True' for r in m)}/{len(m)}",
            'filter_compliance_test_questions': f"{sum(all(v) for v in fq.values())}/{len(fq)}" if fq else 'N/A',
            'grounding_counts_0_1_2': [gc[0], gc[1], gc[2]],
            'grounding_mean_of_2': round(sum(g) / len(g), 2), 'grounding_n': len(g)}
    write_json(ROOT / 'results' / 'audit_summary.json', out)
    for s, v in out['strategies'].items():
        print(s, v)


if __name__ == '__main__':
    main()
