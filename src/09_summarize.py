"""Summarise manual labels and mechanical metadata checks into results/audit_summary.json."""
import csv
from collections import Counter
from common import ROOT, write_json

AUDIT = ROOT / 'results' / 'audit'


def read(name):
    with (AUDIT / name).open(encoding='utf-8') as f:
        return list(csv.DictReader(f))


def main():
    coherence, grounding, meta = read('coherence_labels.csv'), read('grounding_labels.csv'), read('metadata_audit.csv')
    out = {'labeller': 'AI-assisted (Claude Code) draft labels, reviewed and accepted by the student without changes; author bias noted',
           'strategies': {}}
    for s in 'ABCDE':
        c = [int(r['label_0_2']) for r in coherence if r['strategy'] == s]
        entry = {'coherence_mean_of_2': round(sum(c) / len(c), 2) if c else None, 'coherence_n': len(c),
                 'coherence_counts_0_1_2': [c.count(0), c.count(1), c.count(2)]}
        for split in ('test', 'test2'):
            g = [int(r['label_0_2']) for r in grounding if r['strategy'] == s and r.get('split', 'test') == split]
            m = [r for r in meta if r['strategy'] == s and r.get('split', 'test') == split]
            fq = {}
            for r in m:
                if r['filter_requested']:
                    fq.setdefault(r['question_id'], []).append(r['satisfies_filter'] == 'True')
            gc = Counter(g)
            entry[split] = {
                'metadata_all_fields_correct': f"{sum(r['all_fields_correct'] == 'True' for r in m)}/{len(m)}",
                'filter_compliance': f"{sum(all(v) for v in fq.values())}/{len(fq)}" if fq else 'N/A',
                'grounding_counts_0_1_2': [gc[0], gc[1], gc[2]],
                'grounding_mean_of_2': round(sum(g) / len(g), 2) if g else None, 'grounding_n': len(g)}
        out['strategies'][s] = entry
    write_json(ROOT / 'results' / 'audit_summary.json', out)
    for s, v in out['strategies'].items():
        print(s, 'coherence', v['coherence_mean_of_2'], v['coherence_counts_0_1_2'], '| test', v['test'], '| test2', v['test2'])


if __name__ == '__main__':
    main()
