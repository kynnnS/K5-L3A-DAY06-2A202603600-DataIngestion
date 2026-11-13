"""Retrieve same query against A/B/C. Optional document_type filter only on C."""
import argparse
import json
from common import ARTIFACTS

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--question', required=True)
    parser.add_argument('--strategy', choices=['A','B','C'], default='C')
    parser.add_argument('--document-type', choices=['framework','profile'])
    parser.add_argument('--top-k', type=int, default=3)
    args = parser.parse_args()
    if args.document_type and args.strategy != 'C':
        raise SystemExit('Only C uses the experimental metadata filter; A/B ignore it by design.')
    import chromadb
    from sentence_transformers import SentenceTransformer
    metrics_path = ARTIFACTS / 'ingestion_metrics.json'
    if not metrics_path.exists():
        raise FileNotFoundError('Run 03_ingest.py first')
    model = json.loads(metrics_path.read_text(encoding='utf-8'))['embedding_model']
    encoder = SentenceTransformer(model)
    client = chromadb.PersistentClient(path=str(ARTIFACTS / 'chroma'))
    coll = client.get_collection(f'nist_rmf_{args.strategy.lower()}')
    query_vector = encoder.encode([args.question], normalize_embeddings=True)[0].tolist()
    opts = {'query_embeddings': [query_vector], 'n_results': args.top_k, 'include': ['metadatas','documents','distances']}
    if args.document_type:
        opts['where'] = {'document_type': args.document_type}
    result = coll.query(**opts)
    for rank, (id_, document, metadata, distance) in enumerate(zip(result['ids'][0], result['documents'][0], result['metadatas'][0], result['distances'][0]), start=1):
        print(f'\n#{rank} id={id_} cosine_distance={distance:.4f}\nsource={metadata["source"]}\nphysical_page={metadata["page"]} type={metadata["document_type"]}\n{document[:1600]}')

if __name__ == '__main__':
    main()
