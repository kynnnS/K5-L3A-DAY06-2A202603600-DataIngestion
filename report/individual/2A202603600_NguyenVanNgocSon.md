# Báo cáo cá nhân — Day 6

> Học viên: Nguyen Van Ngoc Son · MSSV 2A202603600 · L3A · Chạy ngày 2026-11-13 trên MacBook Apple M5, embedding chạy trên MPS.
> Mọi số liệu dưới đây lấy từ file kết quả thật trong `results/` và `artifacts/`. Nhãn chấm tay là bản nháp có AI hỗ trợ; học viên phải đọc lại và sửa nếu không đồng ý trước khi nộp (xem mục cuối).

## Dữ liệu và pipeline

- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:**
  - Chủ đề: quản trị rủi ro AI. Corpus gồm NIST AI 100-1 *AI Risk Management Framework (AI RMF 1.0)* (2023-01-26, DOI 10.6028/NIST.AI.100-1) và NIST AI 600-1 *AI RMF: Generative AI Profile* (2024-07-26, DOI 10.6028/NIST.AI.600-1). Tải từ `nvlpubs.nist.gov` ngày 2026-11-13; sha256 ghi trong `data/download_receipts.json`.
  - Quyền: là ấn phẩm của chính phủ liên bang Mỹ, phần văn bản nói chung thuộc public domain tại Mỹ. Nội dung của bên thứ ba, logo và con dấu không mặc nhiên cùng điều kiện, nên PDF gốc và toàn bộ text **không** được commit; người chấm tái tạo bằng `src/01_download.py`.
  - Số trang: 112 trang vật lý (48 + 64). 103 trang có ≥800 ký tự sau chuẩn hóa. Sau khi loại 11 trang trong `data/page_audit.json` (AI 100-1: p3 miễn trừ, p4 mục lục, p5 danh sách hình; AI 600-1: p3 giới thiệu NIST và miễn trừ, p58–p64 References), còn **92 trang hợp lệ** (40 + 52), tổng 237.314 ký tự.
  - Quy tắc: trang vật lý trong PDF (đếm từ 1, không phải số in trên trang), ≥800 ký tự **và** không bị loại trong file audit. Chỉ các trang hợp lệ được đưa vào vector store.
- **Chuẩn hóa, lỗi và giới hạn:**
  - PyMuPDF 1.28.2 `get_text(sort=True)`, Unicode NFKC, bỏ soft hyphen, nối lại từ bị ngắt dòng bằng gạch nối, gộp khoảng trắng thừa. Không có trang rỗng hay scan (0/112), nên không cần OCR.
  - Lỗi quan sát được:
    - **Bảng nhiều cột** (Table 1–4 của AI 100-1, các bảng action của AI 600-1) bị trộn thứ tự chữ giữa các cột. Lỗi này ảnh hưởng trực tiếp tới coherence, xem các vị trí pos04 và pos07–09.
    - AI 100-1 p16 là hình, text trích ra lộn xộn (411 ký tự, không tính).
    - AI 100-1 p39 và AI 600-1 p50 là nội dung thật nhưng ngắn (<800 ký tự) nên không được index.
    - Bước nối từ bị ngắt gạch nối đôi khi dính sai, ví dụ "highor", "humanAI", "apmaximize".
- **Embedding model/provider/version/số chiều, vector store/version, metric, lệnh chạy và chi phí:**
  - Model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, chạy local qua sentence-transformers 5.7.0 và torch 2.15.0. Số chiều **384**, `max_seq_length` **128 token** (đọc từ model lúc chạy). Vector chuẩn hóa L2; query và document mã hóa giống nhau, không có prefix.
  - Store: Chroma 1.5.9 `PersistentClient`, lưu tại `artifacts/chroma/`, collection `nist_rmf_a/b/c`, cosine (`hnsw:space=cosine`). Đây là approximate search (HNSW).
  - Lệnh chạy: xem README (`01` → `09`). **Chi phí API: 0 USD.**
  - Thời gian ingest (embedding và ghi, lần chạy cuối): A 1,62 s; B 0,91 s; C 0,93 s; D 1,63 s; E 1,61 s (D/E gồm cả bước đếm token khi chunk). Mã hóa 28 câu hỏi (dev, test, test2) mất 0,12 s; truy vấn 28 câu mất 0,03–0,12 s mỗi chiến lược (lần đầu chậm hơn do khởi động). Không tính thời gian tải model lần đầu.
  - **Nạp lại:** chạy `03_ingest.py` 2 lần trên cùng phiên bản dữ liệu (sha256 input trùng nhau). Số chunk A/B/C = 561/330/330 ở cả hai lần, bằng `collection.count()` và bằng số ID duy nhất, tức **không nhân đôi** (`results/reingest_check.txt`). Mỗi lần ingest xóa và tạo lại collection; nếu tài liệu đổi thì chạy lại `01_download.py --force`, nhờ vậy không còn chunk cũ.
- **Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn:**
  - Bắt buộc: `document_id` (str), `source` (str, URL gốc), `page` (int, trang vật lý), `page_id` (str).
  - Trường lọc: `document_type` (str, `framework` hoặc `profile`), lấy từ tiêu đề chính thức trong `sources.json`. Hai tài liệu định nghĩa nhiều khái niệm gần như giống hệt nhau (risk, AI Actors, Human-AI configuration), nên người dùng cần giới hạn phạm vi theo tài liệu.
  - Trường phụ: `year` (int), `language`, `strategy`, `chunk_index`, `start_char`, `end_char_approx`.

## Cấu hình và benchmark

- **A / B / C (tham số cụ thể, khác biệt duy nhất B–C):**
  - **A:** cắt cố định 500 ký tự, overlap 50, trong từng trang, không lọc. Kết quả: 561 chunk, trung vị 500 ký tự, trung bình 107 token.
  - **B:** tách theo đoạn (dòng trống) trong từng trang, gộp tối đa 1000 ký tự, đoạn dài hơn bị cắt cứng ở ký tự thứ 1000. Không lọc. Kết quả: 330 chunk, trung vị 820 ký tự, trung bình 163 token.
  - **C:** đúng các chunk của B, thêm `where={"document_type": …}` **chỉ với 4 câu có filter**; 17 câu còn lại chạy không lọc nên trùng hệt B.
  - A–B chỉ khác cách chunk. **B–C chỉ khác việc lọc.**
- **≥20 câu: phân chia ≥15 dev / ≥5 test, câu metadata filter và cách kiểm chứng evidence:**
  - 21 câu trong `benchmark/questions.jsonl`: q01–q15 là dev, q16–q21 là test. Loại câu: trực tiếp, diễn đạt lại, điều kiện/ngoại lệ, metadata_filter.
  - Test lấy các trang và chủ đề mà dev không dùng. 4 câu filter: q14, q15 (dev) và q20, q21 (test). Mỗi câu nhắm vào khái niệm mà **cả hai** tài liệu đều nêu, và giá trị filter do người dùng nêu trong câu hỏi.
  - Kiểm chứng: `05_verify_benchmark.py` xác nhận 21/21 evidence (cùng 2 evidence thay thế) có nguyên văn trên trang gold, và trang gold là trang được index.
  - Bộ câu hỏi chốt trước lần chạy truy xuất đầu tiên: sha256 trong `benchmark/FROZEN.txt`, commit `244886e`. Sau khi xem kết quả, không câu nào bị sửa.
- **Tiêu chí chọn chiến lược đã chốt trước khi xem test** (`benchmark/README.md`): (1) dev Evidence Hit@3 cao nhất; (2) nếu hòa thì xét dev Hit@1; (3) nếu vẫn hòa thì chọn cấu hình ít chunk hơn và ingest nhanh hơn.

## Kết quả

Hit = chunk đúng tài liệu và trang gold **và** chứa trọn evidence. Nguồn: `results/retrieval_metrics.csv`, `artifacts/ingestion_metrics.json`.

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian ingest | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 5/15 | 6/15 | 561 | 1,62 s | 0 |
| A | test | 2/6 | 2/6 | | | |
| B | dev | 5/15 | 6/15 | 330 | 0,91 s | 0 |
| B | test | 1/6 | 3/6 | | | |
| C | dev | 5/15 | 6/15 | 330 | 0,93 s | 0 |
| C | test | 1/6 | 3/6 | | | |

Chỉ số phụ, không thay thế chỉ số chính: Page Hit@3 (trang gold có trong top-3 dù evidence bị tách) đạt A 11/15 dev và 3/6 test; B và C 10/15 dev và 3/6 test.

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | 0,60 (10) · 0/1/2 = 4/6/0 | 18/18 | dev 0/2 · test 1/2 (không lọc) | 3/1/2 · 0,83 (6) |
| B | 1,30 (10) · 0/1/2 = 0/7/3 | 18/18 | dev 1/2 · test 1/2 (không lọc) | 2/1/3 · 1,17 (6) |
| C | 1,30 (10) · trùng chunk B | 18/18 | **dev 2/2 · test 2/2** | 2/1/3 · 1,17 (6) |

Đường dẫn trace, nhãn thủ công và cách chọn mẫu:
- Trace: `results/traces_{A,B,C}.jsonl`, gồm top-3 với ID, text, cosine distance, metadata và nhãn hit.
- Chẩn đoán lỗi: `results/failure_diagnosis.csv`, cho biết hạng của chunk chứa evidence trong toàn bộ collection và vị trí token của evidence so với cửa sổ 128 token.
- Nhãn: `results/audit/coherence_labels.csv`, `grounding_labels.csv`, `metadata_audit.csv`; tổng hợp trong `results/audit_summary.json`.
- Mẫu chấm, cố định trước khi chạy:
  - Coherence: 10 vị trí giữa trang của 10 trang hợp lệ cách đều nhau (`benchmark/coherence_positions.json`).
  - Metadata: 6 câu test × top-3 × 3 chiến lược = 54 bản ghi. Mỗi bản ghi được kiểm tra text chunk có thật trên đúng trang mà metadata ghi không, và `source`, `document_type`, `year` có khớp `sources.json` không.
  - Grounding: 6 câu test × 3 chiến lược.

## Phân tích và kết luận

- **So sánh A–B (chỉ đổi cách chunk):**
  - Evidence Hit@3 trên dev **bằng nhau (6/15)**. Trên test, B hơn A 1 câu (3/6 so với 2/6). Hit@1 trên toàn bộ: A 7/21, B 6/21. Mẫu nhỏ, chênh 1 câu không đủ để kết luận.
  - Hai kiểu lỗi ngược chiều nhau triệt tiêu lẫn nhau:
    - **A làm vỡ evidence**: 6/21 câu không có chunk A nào chứa trọn evidence (q02, q04, q06, q08, q18, q20), so với 2/21 ở B. Vì vậy A tìm đúng trang nhiều hơn (Page Hit@3 14/21 so với 13/21) nhưng không ghi được hit.
    - **B vượt cửa sổ model**: 239/330 chunk B (72%) dài hơn 128 token và bị cắt khi embedding, so với 25/561 (4%) ở A. Có 4/21 câu mà evidence nằm một phần ngoài phần được embedding.
  - Về chất lượng, B tốt hơn rõ: coherence 1,30 so với 0,60, grounding 1,17 so với 0,83. B cũng ít chunk hơn 41% và ingest nhanh hơn.
  - **Lỗi phụ của B: chunk chỉ có tiêu đề.** B tạo 11/330 chunk ngắn dưới 100 ký tự, gồm tiêu đề lặp đầu trang ("NIST AI 100-1 AI RMF 1.0"), dòng "Page 31", hay heading đứng một mình. Các chunk này chiếm 5/63 vị trí top-3, so với 2/63 ở A. Ví dụ ở q06, hạng 2 của B là chunk tiêu đề 57 ký tự "3. AI Risks and Trustworthiness" trên chính trang gold, đẩy chunk chứa evidence xuống hạng 4.
- **So sánh B–C (chỉ đổi lọc):**
  - 17/21 câu trùng hệt nhau theo thiết kế. Trên 4 câu filter, C đạt tuân thủ **4/4** so với 2/4 ở B. Ví dụ ở q20, B để lọt một chunk của framework ở hạng 3 (AI 100-1 p47), còn C chỉ trả về chunk của profile.
  - Tuy nhiên filter **không đổi Hit nào**: q20 và q21 đều trúng ở cả B lẫn C, q14 và q15 trượt ở cả hai. Filter giúp chunk evidence leo hạng trong phạm vi tìm (q15 từ hạng 48/330 lên 18/183; q14 từ 16/330 lên 14/147), nhưng không đủ để vào top-3. Nút thắt nằm ở embedding chứ không phải ở phạm vi tìm.
- **Ví dụ lỗi:**
  1. **q11 (dev), AI 600-1 p17**, hỏi về các tiền tố GV/MP/MS/MG. A trúng ở hạng 1, còn B và C trượt. Trong chunk B, evidence "GV = Govern; MP = Map; …" nằm ở **token 162–181**, sau giới hạn 128 token. Phần đó không bao giờ được embedding nên chunk chỉ xếp hạng 7. Đây là lỗi do kích thước chunk không khớp cửa sổ model, không phải do cách chia đoạn sai.
  2. **q18 (test), AI 600-1 p9**, hỏi định nghĩa Value Chain and Component Integration. Cả ba chiến lược đều trượt và **không chunk nào chứa trọn evidence**. A cắt đoạn 330 ký tự qua ranh giới cửa sổ 500 ký tự. B gộp cả mục 11–12 thành một khối dài hơn 1000 ký tự rồi **cắt cứng giữa từ** ("improper supplier vetting acr|oss"). Top-1 còn lệch hẳn chủ đề (A: AI 600-1 p7; B và C: residual risk AI 100-1 p13).
  3. **q04 (dev), AI 100-1 p13**, hỏi điều kiện phải dừng hệ thống AI. Evidence dài 330 ký tự: ở A bị tách ra 2 chunk (chỉ trúng trang), ở B nằm trọn trong 1 chunk nhưng chunk đó xếp hạng 4, ngay ngoài top-3.
  4. **q10 (dev), AI 600-1 p6**, hỏi về Public Working Group. Chunk chứa evidence xếp hạng 113/330 (B) và 169/561 (A), dù evidence nằm trong cửa sổ embedding. Đây là giới hạn ngữ nghĩa của model nhỏ với tên riêng và từ viết tắt ("GAI PWG").
- **Chiến lược chọn, đánh đổi, điều kiện áp dụng:**
  - Áp dụng tiêu chí đã chốt: (1) dev Evidence Hit@3 hòa 6/15 cả ba; (2) dev Hit@1 hòa 5/15; (3) B và C dùng 330 chunk so với 561 của A, nên **loại A**.
  - Tiêu chí đã chốt **không phân biệt được B với C**: cùng chunk, thời gian ingest chênh vài phần trăm giây, chỉ là nhiễu.
  - Mình chọn **C**, dựa trên một lý do **không nằm trong tiêu chí chốt trước** và ghi rõ như vậy: trên dev, C tuân thủ filter 2/2 so với 1/2 của B, trong khi không mất gì ở câu không filter. Kết quả test chỉ được xem sau khi chọn: C đạt Hit@1 1/6 và Evidence Hit@3 3/6.
  - Điều kiện áp dụng: C chỉ có ích khi người dùng thật sự cung cấp phạm vi tài liệu. Nếu muốn đánh đổi để được Hit@1 cao hơn ở câu hỏi ngắn, A có lợi; nhưng A cho chunk khó đọc (coherence 0,60).
- **Hạn chế của dữ liệu, nhãn, test nhỏ, đo thời gian/chi phí:**
  - Test chỉ có 6 câu, mỗi câu chiếm khoảng 17 điểm phần trăm, và các chiến lược chỉ chênh nhau 1 câu. Không thể kết luận chiến lược nào tốt nhất ngoài corpus này.
  - Corpus chỉ có 2 tài liệu, nên `document_type` trùng 1-1 với `document_id`. Filter chỉ kiểm tra được việc giới hạn phạm vi.
  - Ảnh hưởng của cách chunk bị **lẫn với giới hạn 128 token** của model: B gần như luôn bị cắt, nên so sánh A–B một phần là so sánh "chunk vừa cửa sổ" với "chunk vượt cửa sổ". Phần mở rộng D (≤128 token) tách riêng được yếu tố này (xem bên dưới).
  - Nhãn coherence và grounding do một người chấm (bản nháp có AI hỗ trợ, học viên đọc lại), không có người chấm thứ hai, nên có thiên lệch. Câu filter ở test dùng cùng mẫu câu với dev.
  - Thời gian đo một lần trên Apple M5/MPS, không lặp lại. Thời gian ingest dưới 2 giây nên chủ yếu là nhiễu, không dùng để xếp hạng.
- **Nếu làm lại hoặc mở rộng, cải tiến gì?**
  - Đặt giới hạn chunk theo **token của model** (≤128) và cắt theo câu thay vì cắt cứng ở 1000 ký tự; hoặc đổi sang model có cửa sổ 512 token. Đây là cách sửa trực tiếp lỗi ở q11 và q18.
  - Trích bảng bằng `page.find_tables()` để không trộn cột (sửa pos04, pos07–09).
  - Bỏ tiêu đề và chân trang lặp lại ("NIST AI 100-1 AI RMF 1.0", "Page N") khi chuẩn hóa, và gộp chunk dưới khoảng 100 ký tự vào chunk kế bên (sửa lỗi chunk chỉ có tiêu đề ở q06).
  - Cho phép chunk vắt qua 2 trang và ghi metadata khoảng trang.
  - Thêm BM25 (hybrid) cho từ viết tắt và mã như "GAI PWG", "GV-1.1".
  - Thêm trường `section` (Part 1/Part 2/Appendix) để có filter phân biệt được hơn `document_type`.

## Vì sao Hit@3 thấp: phân loại nguyên nhân

`results/failure_taxonomy.csv` phân loại từng câu × chiến lược (28 câu: dev, test và test2) dựa trên `failure_diagnosis.csv`. Hạng của chunk chứa evidence được tính trong **toàn bộ** collection.

| Kết quả (28 câu) | A | B | C | D | E |
|---|---:|---:|---:|---:|---:|
| Hit@1 | 9 | 9 | 9 | 10 | 10 |
| Hit ở hạng 2–3 | 2 | 4 | 4 | 3 | 3 |
| Trượt: evidence bị tách sang nhiều chunk | 6 | 2 | 2 | 1 | 1 |
| Trượt: evidence nằm ngoài cửa sổ 128 token | 0 | 4 | 4 | 0 | 0 |
| Trượt sát nút (chunk evidence ở hạng 4–10) | 1 | 3 | 3 | 5 | 6 |
| Trượt ngữ nghĩa (chunk evidence ở hạng >10) | 10 | 6 | 6 | 9 | 8 |

Kết luận:
- Hit@3 chỉ khoảng 40–50% do **hai nhóm nguyên nhân**.
  1. **Lỗi do chuẩn bị dữ liệu.** A tách evidence, B vượt cửa sổ model. Nhóm này **sửa được** bằng cách chunk: D đưa cả hai lỗi về 1 và 0.
  2. **Giới hạn của model embedding.** Đây là nhóm còn lại sau khi đã sửa nhóm 1. Ở mọi chiến lược, 8–10/28 câu có chunk chứa evidence được embedding trọn vẹn nhưng vẫn xếp hạng dưới 10. Ví dụ q10 (hạng 78–169), q17 (hạng 104–136), q03 (hạng 24–42).
- `paraphrase-multilingual-MiniLM-L12-v2` được huấn luyện để so khớp câu diễn đạt lại (paraphrase), không phải để truy xuất câu hỏi → đoạn văn. Model cũng yếu với tên riêng và từ viết tắt ("GAI PWG", "go/no-go").
- Muốn tăng tiếp phải đổi model hoặc thêm BM25. Cả hai đều nằm ngoài phạm vi "giữ nguyên model" của bài, nên được ghi ở phần cải tiến.

## Phần mở rộng (làm sau khi đã xem kết quả A/B/C): D/E và tập holdout mới test2

> Phần này được thiết kế **sau khi đã xem** kết quả dev và test của A/B/C, nên không thay thế kết quả chính ở trên. Thiết kế, giả thuyết, tiêu chí chọn và 7 câu test2 được commit **trước** khi viết code D/E và trước khi chạy test2 (commit `f9fa644`, `benchmark/EXTENSION.md`, sha256 trong `benchmark/FROZEN.txt`). Tập test cũ (q16–q21) đã bị xem nên không còn độc lập với D/E.

- **D:** cắt theo câu và gộp các câu liền nhau tới **≤128 token** (đo bằng tokenizer của model), không overlap. **E** = D + filter. B so với D chỉ đổi luật chunk, D so với E chỉ đổi việc lọc. Mục đích: tách ảnh hưởng của cách chunk khỏi giới hạn 128 token.
- **Test2:** 7 câu mới (q22–q28) lấy từ các trang chưa câu nào dùng (AI 100-1 p21–22; AI 600-1 p12, p14), trong đó 2 câu filter.

| Strategy | Chunk (trung vị ký tự / TB token) | Bị model cắt | Hit@1 dev | Hit@3 dev | Hit@1 test2 | Hit@3 test2 | Coherence /2 | Grounding test2 /2 |
|---|---|---|---|---|---|---|---|---|
| A | 561 (500 / 107) | 25 | 5/15 | 6/15 | 2/7 | 3/7 | 0,60 | 1,00 (3/1/3) |
| B | 330 (820 / 163) | 239 | 5/15 | 6/15 | 3/7 | **4/7** | 1,30 | **1,14** (3/0/4) |
| C | 330 | 239 | 5/15 | 6/15 | 3/7 | **4/7** | 1,30 | **1,14** |
| D | 544 (458 / 100) | **0** | 5/15 | **7/15** | 3/7 | 3/7 | **1,50** | 1,00 (3/1/3) |
| E | 544 | **0** | 5/15 | **7/15** | 3/7 | 3/7 | **1,50** | 1,00 |

- Filter tuân thủ trên test2: cả 5 chiến lược đều 2/2. Metadata kiểm tra cơ học: 195/195 bản ghi đúng (test và test2, 5 chiến lược). Trên tập test cũ (đã bị xem): D và E đạt Hit@3 3/6, grounding D 1,17 và E 1,00.
- **Chọn theo tiêu chí mở rộng đã chốt:** dev Evidence Hit@3 cao nhất là D/E (7/15). D và E hòa ở Hit@1 và số chunk, E thắng nhờ dev filter tuân thủ 2/2 so với 1/2, nên **chọn E**.
- **Kết quả trên test2 (không thiên lệch): E chỉ đạt 3/7, thấp hơn B/C (4/7).** Lợi thế 1 câu của D/E trên dev (vốn thiên về D vì D được thiết kế sau khi xem dev) **không lặp lại** trên tập mới. Chênh lệch chỉ 1 câu ở cả hai phía, nằm trong sai số của mẫu nhỏ.
- **Ví dụ D thua B, q28 (test2), AI 100-1 p22:** câu hỏi chứa "AI RMF 1.0 framework". Với D/E, cả 3 kết quả đều là chunk mở đầu bằng **tiêu đề lặp đầu trang "NIST AI 100-1 AI RMF 1.0"** (p47, p25, p8). Chunk D ngắn nên dòng tiêu đề chiếm tỷ trọng lớn trong vector và khớp với tên tài liệu trong câu hỏi. B (chunk dài) lấy đúng định nghĩa ở hạng 1. Cách sửa: bỏ tiêu đề lặp khi chuẩn hóa.
- **Ví dụ D thắng B, q11 (dev), AI 600-1 p17:** evidence nằm ở token 162–181 của chunk B, ngoài cửa sổ nên không được embedding (B xếp hạng 7). Với D, chunk vừa cửa sổ nên lên hạng 1. Ở q16 (test), evidence vẫn nằm trong cửa sổ của B (token 73–99) nhưng chunk B dài, nhiều chủ đề nên chỉ xếp hạng 5. Chunk D ngắn, tập trung vào đúng gạch đầu dòng, nên lên hạng 1.
- **Kết luận phần mở rộng:**
  - D chứng minh lỗi tách evidence và vượt cửa sổ là lỗi do chuẩn bị dữ liệu, và sửa được (coherence tốt nhất: 1,50).
  - Nhưng sửa xong thì Hit@3 không tăng rõ, vì nút thắt chuyển sang model và nhiễu từ tiêu đề trang.
  - Với dữ liệu hiện có, **không có bằng chứng chiến lược nào vượt trội**: B/C và D/E hơn kém nhau 1 câu, đổi chiều giữa dev và test2.
  - Nếu triển khai thật, mình chọn **E kèm bước bỏ tiêu đề trang**. Lý do: không có chunk nào bị cắt, coherence cao nhất, và có filter. Điều này cần kiểm chứng thêm trên một tập holdout lớn hơn.

## Kiểm tra metadata thủ công (học viên)

Kiểm tra bằng script (195/195 bản ghi) xác nhận text của chunk có thật trên trang mà metadata ghi. Ngoài ra, học viên mở PDF gốc kiểm tra thủ công 9 bản ghi top-1 của A, C và E (`results/audit/metadata_manual_check.csv`: mở link `#page=N`, Cmd+F đoạn trích, đối chiếu loại tài liệu):

- Kết quả: **__/9** bản ghi đúng trang và đúng loại tài liệu. Ghi chú: ____ *(học viên điền sau khi kiểm tra)*

## Sử dụng AI và cách kiểm tra

- Công cụ: Claude Code (Anthropic).
- Phạm vi sử dụng:
  - Viết và sửa script `src/`.
  - Đề xuất danh sách trang loại trừ.
  - Soạn 21 câu benchmark từ text trang.
  - Chấm nháp coherence và grounding kèm lý do.
  - Soạn báo cáo này.
- Cách kiểm tra:
  - Evidence được đối chiếu tự động nguyên văn với trang nguồn (`05_verify_benchmark.py`).
  - Metadata được kiểm tra cơ học 195/195 (test và test2, 5 chiến lược) và kiểm tra thủ công 9 bản ghi trên PDF gốc (mục "Kiểm tra metadata thủ công").
  - Mọi chỉ số đều được tính từ trace thật bằng script, không gõ tay.
  - Học viên đối chiếu các trang bị loại với PDF và đọc lại toàn bộ 30 nhãn coherence và 18 nhãn grounding trước khi nộp.
- Bộ câu hỏi và tiêu chí được chốt trước khi chạy và không bị sửa theo kết quả test.
