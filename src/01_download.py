"""Download original NIST publications; never replace source data with generated text."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import requests
from common import ROOT, RAW, read_json, write_json, sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    outputs = []
    for src in read_json(ROOT / 'sources.json'):
        target = RAW / src['filename']
        if target.exists() and not args.force:
            print(f'EXISTS {target.name} ({target.stat().st_size:,} bytes)')
        else:
            print(f'DOWNLOADING {src["url"]}')
            with requests.get(src['url'], stream=True, timeout=(15, 120), headers={'User-Agent': 'EducationalResearchDataIngestion/1.0'}) as response:
                response.raise_for_status()
                temp = target.with_suffix('.pdf.part')
                try:
                    with temp.open('wb') as out:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                out.write(chunk)
                    if temp.stat().st_size < 10000 or temp.open('rb').read(5) != b'%PDF-':
                        raise ValueError(f'Invalid PDF response for {src["source_id"]}')
                    temp.replace(target)
                finally:
                    temp.unlink(missing_ok=True)
        if target.open('rb').read(5) != b'%PDF-':
            raise ValueError(f'Not a PDF: {target}')
        outputs.append({**src, 'path': str(target.relative_to(ROOT)), 'bytes': target.stat().st_size, 'sha256': sha256(target), 'accessed_at': datetime.now(timezone.utc).isoformat()})
    write_json(ROOT / 'data' / 'download_receipts.json', outputs)
    print('SOURCE VERIFICATION: OK. Records:', len(outputs))

if __name__ == '__main__':
    main()
