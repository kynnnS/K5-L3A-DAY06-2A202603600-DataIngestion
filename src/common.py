from pathlib import Path
import json
import hashlib
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'
PROCESSED = ROOT / 'data' / 'processed'
ARTIFACTS = ROOT / 'artifacts'

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def write_json(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding='utf-8')

def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')

def iter_jsonl(path):
    with Path(path).open(encoding='utf-8') as f:
        for line in f:
            if line.strip():
                yield json.loads(line)

def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def normalize(text):
    text = unicodedata.normalize('NFKC', text)
    text = text.replace('­', '')
    text = re.sub(r'(?<=\w)-\s*\n\s*(?=\w)', '', text)
    text = re.sub(r'[\t ]+', ' ', text)
    text = re.sub(r'\n[ \t]+', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
