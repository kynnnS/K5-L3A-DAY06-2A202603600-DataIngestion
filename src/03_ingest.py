"""Actual semantic embeddings + persistent Chroma; three comparable strategies."""
import argparse
import json
import re
import time
from statistics import mean
from pathlib import Path
from common import ROOT, PROCESSED, ARTIFACTS, iter_jsonl, write_jsonl, write_json, sha256

MODEL_NAME = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'


def fixed_chunks(text, size=500, overlap=50):
    if size <= overlap:
        raise ValueError('size must exceed overlap')
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        yield text[start:end], start, end
        if end == len(text):
            break
        start = end - overlap


def paragraph_chunks(text, max_chars=1000):
    # Paragraph/heading-aware split within each physical source page.
    blocks = [(m.group().strip(), m.start()) for m in re.finditer(r'[^\n]+(?:\n(?!\n)[^\n]+)*', text) if m.group().strip()]
    if not blocks and text.strip():
        blocks = [(text.strip(), 0)]
    buffer, offset = '', 0
    for block, start in blocks:
        pieces = [block[i:i + max_chars] for i in range(0, len(block), max_chars)] if len(block) > max_chars else [block]
        for part in pieces:
            proposed = (buffer + '\n\n' + part) if buffer else part
            if buffer and len(proposed) > max_chars:
                yield buffer, offset, offset + len(buffer)
                buffer, offset = part, start
            else:
                if not buffer:
                    offset = start
                buffer = proposed
    if buffer:
        yield buffer, offset, offset + len(buffer)


def prepare(strategy, pages):
    result = []
    for page in pages:
        if not page.get('eligible_content_page', page['candidate_content_page']) or not page['text']:
            continue
        method = fixed_chunks if strategy == 'A' else paragraph_chunks
        for i, (content, start, end) in enumerate(method(page['text'])):
            content = content.strip()
            if not content:
                continue
            result.append({
                'id': f'{strategy}:{page["page_id"]}:chunk:{i:04d}',
                'text': content,
                'metadata': {
                    'document_id': page['document_id'], 'source': page['source'],
                    'page': int(page['page']), 'page_id': page['page_id'],
                    'document_type': page['document_type'], 'year': int(page['year']),
                    'language': page['language'], 'strategy': strategy,
                    'chunk_index': i, 'start_char': int(start), 'end_char_approx': int(end)
                }
            })
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default=MODEL_NAME)
    parser.add_argument('--batch-size', type=int, default=32)
    args = parser.parse_args()
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise SystemExit(f'Missing real vector deps; pip install -r requirements.txt: {e}')
    src = PROCESSED / 'pages.jsonl'
    if not src.exists():
        raise FileNotFoundError('Run 02_extract.py before ingestion')
    pages = list(iter_jsonl(src))
    if not any(p['candidate_content_page'] for p in pages):
        raise ValueError('No usable source pages; inspect PDF extraction')
    print(f'Loading real embedding model {args.model} (first run may download model weights)')
    encoder = SentenceTransformer(args.model)
    sample = encoder.encode(['dimension check'], normalize_embeddings=True)
    dim = len(sample[0])
    client = chromadb.PersistentClient(path=str(ARTIFACTS / 'chroma'))
    metrics = []
    for strategy in 'ABC':
        t0 = time.perf_counter()
        chunks = prepare(strategy, pages)
        if not chunks:
            raise ValueError(f'No chunks for strategy {strategy}')
        collection_name = f'nist_rmf_{strategy.lower()}'
        # Exact reruns overwrite a collection, avoiding duplicate IDs/stale chunks.
        # Newer chromadb raises NotFoundError (not ValueError) for a missing collection.
        if collection_name in [getattr(c, 'name', c) for c in client.list_collections()]:
            client.delete_collection(collection_name)
        collection = client.create_collection(collection_name, metadata={'hnsw:space': 'cosine'})
        texts = [c['text'] for c in chunks]
        embeddings = encoder.encode(texts, batch_size=args.batch_size, normalize_embeddings=True, show_progress_bar=True)
        for j in range(0, len(chunks), 100):
            batch = chunks[j:j + 100]
            collection.add(ids=[c['id'] for c in batch], documents=[c['text'] for c in batch], metadatas=[c['metadata'] for c in batch], embeddings=embeddings[j:j + 100].tolist())
        if collection.count() != len(chunks):
            raise RuntimeError(f'Vector count mismatch: {strategy}')
        elapsed = round(time.perf_counter() - t0, 2)
        # Token lengths with the model's own tokenizer: text beyond max_seq_length is truncated
        # before embedding, so that part of the chunk cannot influence retrieval.
        token_lens = [len(encoder.tokenizer(t, add_special_tokens=True)['input_ids']) for t in texts]
        char_lens = sorted(len(t) for t in texts)
        write_jsonl(PROCESSED / f'chunks_{strategy}.jsonl', chunks)
        row = {'strategy': strategy, 'collection': collection_name, 'document_count': len({c['metadata']['document_id'] for c in chunks}),
               'chunk_count': len(chunks), 'embedding_model': args.model, 'embedding_dimension': dim,
               'vector_store': 'Chroma', 'distance': 'cosine', 'metadata_filter_supported': strategy == 'C',
               'mean_chunk_characters': round(mean(len(t) for t in texts), 2), 'total_chunk_characters': sum(map(len, texts)),
               'min_chunk_characters': char_lens[0], 'median_chunk_characters': char_lens[len(char_lens) // 2],
               'max_chunk_characters': char_lens[-1],
               'total_tokens': sum(token_lens), 'mean_tokens': round(mean(token_lens), 1),
               'model_max_seq_length': encoder.max_seq_length,
               'chunks_truncated_by_model': sum(n > encoder.max_seq_length for n in token_lens),
               'elapsed_seconds': elapsed, 'model_api_cost_usd': 0,
               'note': 'Runtime measured locally; first-time model download not included in every strategy' }
        metrics.append(row)
        print(f'INGESTED {strategy}: {len(chunks)} chunks, {dim} dimensions, {row["elapsed_seconds"]} seconds')
    write_json(ARTIFACTS / 'ingestion_metrics.json', {'strategies': metrics, 'input_sha256': sha256(src), 'embedding_model': args.model})
    print('DONE: Persistent Chroma collections + real embeddings + measured metrics')

if __name__ == '__main__':
    main()
