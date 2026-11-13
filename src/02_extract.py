"""Extract PDF pages, keep physical page and exact normalized text + quality manifest."""
from datetime import datetime, timezone
import pymupdf as fitz
from common import ROOT, RAW, PROCESSED, read_json, write_json, write_jsonl, normalize, sha256

# Conservative content threshold: short pages are retained for traceability but not counted.
MIN_CONTENT_CHARS = 800

def load_exclusions():
    audit_path = ROOT / 'data' / 'page_audit.json'
    if not audit_path.exists():
        return {}
    return {e['page_id']: e['reason'] for e in read_json(audit_path)['exclusions']}


def main():
    records, manifests = [], []
    exclusions = load_exclusions()
    for src in read_json(ROOT / 'sources.json'):
        path = RAW / src['filename']
        if not path.is_file():
            raise FileNotFoundError(f'Missing {path}; run 01_download.py first')
        pdf = fitz.open(path)
        if pdf.is_encrypted:
            raise ValueError(f'Encrypted source: {path}')
        page_meta = []
        for page_index in range(len(pdf)):
            page = pdf[page_index]
            raw = page.get_text('text', sort=True)
            content = normalize(raw)
            # Exclude known non-body labels but retain the original normalized text for inspection.
            short = len(content) < MIN_CONTENT_CHARS
            has_content = bool(content)
            page_id = f'{src["source_id"]}:pdf:{page_index + 1:03d}'
            excluded_reason = exclusions.get(page_id)
            eligible = (not short) and excluded_reason is None
            record = {
                'page_id': page_id,
                'document_id': src['source_id'],
                'source': src['url'],
                'title': src['title'],
                'page': page_index + 1,  # physical PDF page, 1-based
                'printed_page': None,  # deliberately unknown, do not guess from layout
                'document_type': src['document_type'],
                'year': int(src['issued_at'][:4]),
                'issued_at': src['issued_at'],
                'language': src['language'],
                'text': content,
                'characters': len(content),
                'candidate_content_page': not short,
                'eligible_content_page': eligible,
                'excluded_reason': excluded_reason,
                'extraction_status': 'text' if has_content else 'empty_or_scanned'
            }
            records.append(record)
            page_meta.append({'page_id': record['page_id'], 'page': page_index + 1, 'characters': len(content), 'candidate_content_page': not short, 'eligible_content_page': eligible, 'excluded_reason': excluded_reason, 'status': record['extraction_status']})
        pdf.close()
        manifests.append({
            'source_id': src['source_id'], 'title': src['title'], 'source_path_or_url': src['url'],
            'local_path': str(path.relative_to(ROOT)), 'license_or_permission': src['license_or_permission'],
            'accessed_at': datetime.now(timezone.utc).isoformat(), 'sha256': sha256(path),
            'issued_at': src['issued_at'], 'doi': src['doi'], 'document_type': src['document_type'],
            'physical_pages': len(page_meta), 'candidate_content_pages': sum(p['candidate_content_page'] for p in page_meta),
            'eligible_content_pages': sum(p['eligible_content_page'] for p in page_meta),
            'eligible_page_ids': [p['page_id'] for p in page_meta if p['eligible_content_page']],
            'eligible_characters': sum(p['characters'] for p in page_meta if p['eligible_content_page']),
            'page_ids': [p['page_id'] for p in page_meta], 'pages': page_meta,
            'characters_total': sum(p['characters'] for p in page_meta),
            'review_note': 'Eligible = >=800 normalized characters AND not excluded in data/page_audit.json (cover, front matter, TOC, list of figures, references).'
        })
    write_jsonl(PROCESSED / 'pages.jsonl', records)
    write_json(ROOT / 'data' / 'manifest.json', {
        'documents': manifests,
        'candidate_content_pages_total': sum(m['candidate_content_pages'] for m in manifests),
        'eligible_content_pages_total': sum(m['eligible_content_pages'] for m in manifests),
        'counting_policy': 'PDF physical pages (1-based) with >=800 normalized text characters, minus pages excluded in data/page_audit.json',
        'audit_file': 'data/page_audit.json'})
    print('PDF pages extracted:', len(records))
    print('Candidate content pages (>=800 chars):', sum(m['candidate_content_pages'] for m in manifests))
    print('Eligible content pages (after audit):', sum(m['eligible_content_pages'] for m in manifests))
    print('Empty/scanned pages:', sum(p['extraction_status'] != 'text' for p in records))
    print('Output: data/processed/pages.jsonl and data/manifest.json')

if __name__ == '__main__':
    main()
