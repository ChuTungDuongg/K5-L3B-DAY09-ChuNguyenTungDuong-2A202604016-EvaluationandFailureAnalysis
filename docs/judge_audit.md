# Judge audit — M2

Chạy từ `src/` bằng `python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 10` và lệnh tương tự với `judge_helpful_public.csv`. Judge dùng verdict replay lưu sẵn trong CSV, không gọi model. Quy ước: **FAIL là lớp dương**, vì mục tiêu là phát hiện lỗi.

| Tiêu chí | n | κ | Precision | Recall | Ma trận (TP, FP, FN, TN) | Kết quả | Quyết định |
|---|---:|---:|---:|---:|---|---|---|
| tone_ok | 100 | 0,757 | 0,857 | 0,800 | 24, 4, 6, 66 | Đạt κ ≥ 0,6, P ≥ 0,8, R ≥ 0,7 | Có thể dùng cho giọng điệu theo các ngưỡng công khai, tiếp tục theo dõi. |
| helpful | 100 | 0,375 | 1,000 | 0,300 | 9, 0, 21, 70 | Không đạt κ và recall | Không dùng làm gate: bỏ sót 21/30 câu người chấm FAIL. |

Tỷ lệ FAIL judge tone quan sát 0,280, hiệu chỉnh Rogan–Gladen là 0,300; helpful lần lượt 0,090 và 0,300. Đây là ước lượng dùng sensitivity và specificity tính từ chính tập replay, không phải kiểm định độc lập hay bằng chứng cho dữ liệu mới.

## Audit các trường hợp bất đồng

Đánh giá dưới đây dựa trên câu trả lời và ghi chú trong CSV; các nhận xét về giọng điệu phụ thuộc rubric và ngữ cảnh khách hàng. Với các trường hợp sai tiền, giá trị ledger được lấy từ ghi chú CSV, không phải một lần truy vấn ledger độc lập.

| Case | Người / judge | Nhận định | Hành động sửa rubric hoặc cách chấm |
|---|---|---|---|
| H-008 | FAIL / PASS | Đồng ý người theo ghi chú: “em”, “nha” quá suồng sã trong ngữ cảnh dịch vụ. | Nêu rõ yêu cầu xưng hô và ví dụ giọng thân thiện nhưng quá suồng sã. |
| H-029 | FAIL / PASS | Đồng ý người: “không cần nhắn thêm” có thể mang giọng ra lệnh, dù có từ “vui lòng”. | Đánh giá cả câu, không coi một từ lịch sự là đủ để PASS. |
| H-042 | PASS / FAIL | Đồng ý người: câu trả lời ngắn nhưng rõ, không có căn cứ bắt buộc xin lỗi chỉ vì ngắn. | Không bắt buộc lời xin lỗi trong mọi câu; nêu khi nào cần xin lỗi. |
| H-051 | PASS / FAIL | Theo ghi chú CSV, từ “refund” được phép; đồng ý người trong rubric này. | Ghi rõ thuật ngữ tiếng Anh được phép, không tự động phạt. |
| H-070 | FAIL / PASS | Đồng ý người: emoji cười không phù hợp với ngữ cảnh khiếu nại theo rubric. | Thêm ví dụ emoji không phù hợp và xem xét ngữ cảnh. |
| HL-015 | FAIL / PASS | Đồng ý người theo ghi chú: reply nói 55.000đ, ledger ghi 40.000đ. | Cấp ledger cho bộ chấm; kiểm tra số tiền bằng code, không suy từ giọng văn. |
| HL-016 | FAIL / PASS | Đồng ý người theo ghi chú: reply nói 55.000đ nhưng ledger ghi 35.000đ dù lời văn lịch sự. | Tách tính đúng sự thật khỏi độ lịch sự; sai tiền phải FAIL. |

H-081 có ghi chú “nhãn người sai ... judge đúng” nhưng CSV ghi human=PASS, judge=FAIL và chỉ cung cấp reply ngắn. Thông tin này chưa đủ để xác định nhãn đúng hoặc loại sai sót trong ghi chú; cần đối chiếu ticket và rubric gốc trước khi sửa dữ liệu. Không tự sửa nhãn trong CSV.

## Kết luận và giới hạn

Judge helpful có precision 1,000 trong mẫu này nhưng recall 0,300: khi báo lỗi thì cả 9 trường hợp đều trùng nhãn người, song 21 lỗi bị cho qua. Vì vậy precision cao không đủ để dùng nó làm gate. Trường hợp tiền phải được kiểm bằng code đối chiếu ledger; sau khi sửa rubric hoặc dữ liệu cần gán nhãn người độc lập và đánh giá trên tập held-out mới.

Các con số là kết quả trên CSV công khai và dựa trên nhãn người hiện có; không khẳng định mọi nhãn đúng hay kết quả tổng quát sang khách hàng thực tế. CSV chỉ lưu verdict replay, vì vậy không suy ra chắc chắn cơ chế nội bộ của judge từ các bất đồng.
