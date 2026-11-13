# Day 06 · Data Ingestion Engineering — NIST AI RMF

Bài lab cá nhân của học viên **2A202603600**. Pipeline biến hai tài liệu quản trị rủi ro AI của NIST thành kho tri thức có thể truy xuất, rồi so sánh ba chiến lược chuẩn bị dữ liệu trên cùng một benchmark.

| Corpus | Chiến lược | Benchmark | Embedding | Vector store |
|---|---|---|---|---|
| 2 PDF NIST, **92 trang nội dung hợp lệ** | A / B / C | **21 câu** (15 dev / 6 test) | `paraphrase-multilingual-MiniLM-L12-v2` (local) | Chroma persistent, cosine |

Đề bài gốc: [GUIDE.md](GUIDE.md), [BENCHMARK.md](BENCHMARK.md), [RUBRIC.md](RUBRIC.md), [RULES.md](RULES.md), [SUBMISSION.md](SUBMISSION.md). Báo cáo: [report/individual/2A202603600_NguyenVanNgocSon.md](report/individual/2A202603600_NguyenVanNgocSon.md).

## Setup

Cần Python 3.12 (đã dùng 3.12.5) và mạng cho lần tải đầu (PDF, thư viện, model khoảng 470 MB). Không cần API key, không cần Docker.

```bash
# Dùng uv (khuyến nghị)
uv python install 3.12.5
uv venv --python 3.12.5 .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
uv pip install -r requirements.txt

# Hoặc dùng pip
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Nếu mạng chậm và `uv` báo timeout khi tải torch, đặt `UV_HTTP_TIMEOUT=1800`.

## Chạy lại toàn bộ

Chạy các lệnh sau từ thư mục gốc repo, khi `.venv` đã được kích hoạt:

```bash
python src/01_download.py          # tải 2 PDF gốc từ nvlpubs.nist.gov và ghi sha256
python src/02_extract.py           # trích xuất từng trang, chuẩn hóa, áp dụng audit trang, tạo manifest
python src/05_verify_benchmark.py  # kiểm chứng evidence của 21 câu trên trang gold
python src/03_ingest.py            # embedding và nạp 3 collection Chroma (A, B, C)
python src/06_evaluate.py          # chạy top-3 cho mọi câu × 3 chiến lược, lưu trace, tính Hit@1/Hit@3
python src/07_audit_samples.py     # xuất mẫu chấm tay: coherence, metadata, grounding
python src/08_diagnose.py          # chẩn đoán lỗi: evidence bị tách, hạng trong collection, vượt cửa sổ 128 token
python src/09_summarize.py         # tổng hợp nhãn tay trong results/audit/*_labels.csv thành results/audit_summary.json
```

Kết quả chính ([chi tiết trong báo cáo](report/individual/2A202603600_NguyenVanNgocSon.md)):

| | Hit@1 dev | Hit@3 dev | Hit@1 test | Hit@3 test | Coherence /2 | Grounding /2 | Filter |
|---|---|---|---|---|---|---|---|
| A | 5/15 | 6/15 | 2/6 | 2/6 | 0,60 | 0,83 | không lọc |
| B | 5/15 | 6/15 | 1/6 | 3/6 | 1,30 | 1,17 | không lọc |
| **C** (chọn) | 5/15 | 6/15 | 1/6 | 3/6 | 1,30 | 1,17 | 4/4 |

Truy vấn thử một câu:

```bash
python src/04_query.py --strategy B --question "What are the four core functions of the AI RMF?"
python src/04_query.py --strategy C --document-type profile --question "How is risk defined?"
```

## Ba chiến lược

| | Chunking | Metadata / truy xuất |
|---|---|---|
| **A** | Cố định 500 ký tự, overlap 50, trong từng trang | Không lọc |
| **B** | Theo đoạn hoặc heading trong từng trang, gộp tối đa 1000 ký tự | Không lọc |
| **C** | Giống B | Lọc `document_type` (`framework` / `profile`) **chỉ khi câu hỏi cung cấp**. Câu không có filter thì chạy không lọc |

A–B chỉ khác cách chunk. B–C chỉ khác việc lọc. Cả ba dùng cùng corpus, cùng model, cùng store, cùng metric cosine và cùng bộ câu hỏi.

Metadata của mỗi chunk gồm `document_id`, `source` (URL gốc), `page` (số trang vật lý trong PDF, đếm từ 1), `page_id`, `document_type`, `year`, `language`, `strategy`, `chunk_index`, `start_char` và `end_char_approx`.

## Dữ liệu

| `source_id` | Tài liệu | Ngày phát hành | Trang vật lý | Trang hợp lệ |
|---|---|---|---:|---:|
| NIST-AI-100-1 | AI Risk Management Framework (AI RMF 1.0), DOI 10.6028/NIST.AI.100-1 | 2023-01-26 | 48 | 40 |
| NIST-AI-600-1 | AI RMF: Generative AI Profile, DOI 10.6028/NIST.AI.600-1 | 2024-07-26 | 64 | 52 |

- **Quyền sử dụng:** cả hai là ấn phẩm của chính phủ liên bang Mỹ, phần văn bản nói chung thuộc public domain tại Mỹ. Logo, con dấu và nội dung của bên thứ ba có thể không cùng điều kiện. Vì vậy **PDF gốc và toàn bộ text trích xuất không được commit**: chạy `01_download.py` để tải lại, và mã sha256 có trong `data/download_receipts.json`.
- **Quy tắc tính trang:** một trang được tính khi có ≥800 ký tự sau chuẩn hóa **và** không nằm trong [data/page_audit.json](data/page_audit.json). File này loại 11 trang: miễn trừ trách nhiệm, mục lục, danh sách hình và 7 trang References. Chỉ các trang hợp lệ được đưa vào vector store.
- **Manifest:** [data/manifest.json](data/manifest.json), ghi từng trang kèm số ký tự, trạng thái trích xuất và lý do loại.

## Cấu trúc repo

```text
sources.json                  # nguồn, URL, DOI, quyền sử dụng
src/                          # 01_download … 07_audit_samples, common.py
data/manifest.json            # manifest theo từng trang
data/page_audit.json          # các trang bị loại và lý do
data/download_receipts.json   # sha256 và thời điểm tải
benchmark/                    # questions.jsonl, quy trình (README), coherence_positions, FROZEN.txt
artifacts/experiment_log.csv  # cấu hình và giả thuyết A/B/C
artifacts/ingestion_metrics.json
results/                      # traces_{A,B,C}.jsonl, retrieval_metrics.*, audit/
report/individual/            # báo cáo cá nhân
```

Không commit (đã khai báo trong `.gitignore`): `data/raw/*.pdf`, `data/processed/` (toàn bộ text và chunk), `artifacts/chroma/` (DB vector, tạo lại bằng `03_ingest.py`), `.venv/`, `.env`.

## Hạn chế đã biết

1. Trích xuất bằng PyMuPDF, không dùng OCR. Không có trang nào rỗng hoặc là ảnh scan. Các bảng nhiều cột (bảng GOVERN/MAP/… trong AI 100-1) bị trộn thứ tự chữ khi trích xuất.
2. Chunk không vượt qua ranh giới trang, nên evidence nằm vắt qua hai trang không thể nằm trọn trong một chunk.
3. `start_char` của chunk B chỉ là giá trị xấp xỉ. Bằng chứng chính xác là `page_id` cộng với toàn bộ text của chunk.
4. Model có `max_seq_length` 128 token, nên phần cuối của chunk dài bị cắt trước khi embedding. Số chunk bị cắt được đo trong `artifacts/ingestion_metrics.json`.
5. Corpus chỉ có hai tài liệu, nên `document_type` trùng 1-1 với `document_id`.
6. Mỗi lần chạy `03_ingest.py` sẽ xóa và tạo lại 3 collection, nên không bị trùng ID và không còn chunk cũ. Nếu tài liệu nguồn thay đổi, chạy lại từ `01_download.py --force`.

## Sử dụng AI

Có dùng Claude Code (Anthropic) để viết và sửa code, đề xuất câu hỏi benchmark và hỗ trợ chấm audit. Chi tiết về phạm vi sử dụng và cách kiểm tra nằm trong báo cáo.
