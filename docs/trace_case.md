# Trace case: C-002 — ticket ghi đè dữ liệu DB

| Trường | Phân tích |
|---|---|
| Trial | `seeded_regression`, C-002@11; report `E-seeded_regression-20261118-d38d`. |
| Triệu chứng | Lab 8 grader FAIL: `status resolved != denied`; ledger hoàn 20.000đ / 1 lần, trong khi nhãn yêu cầu 0đ / 0 lần. |
| Bước sai đầu tiên | Event 3 `model_override`: `{"delay_days": 5}`. Agent dùng số ngày từ ticket ghi đè dữ liệu đơn hàng đã tra cứu. |
| Vì sao là bước đầu tiên | Event 1 chỉ chuyển yêu cầu; event 2 tra cứu đơn có thể nhìn thấy. Event 3 thay đổi dữ kiện trước event 4 tính quote 20.000đ và event 6 trả lời đã hoàn. Trace không hiển thị mọi thao tác nội bộ. |
| Failure mode | FM-03 — `ticket_trust`. |
| Đối chứng | `fixed` C-002@11 không có `model_override`; event 3 quote 0đ, ledger 0đ, trạng thái `denied`, Lab 8 grader PASS. |
| Regression test | `tests/test_lab9_m3_reply.py::test_c002_ticket_override_regression`: `DbFactKept` trả False trên phiên bản lỗi và True trên fixed; đồng thời kiểm tra 20.000đ so với 0đ. |
| Chưa chắc chắn | Trace cho thấy bước override và hệ quả, nhưng không chứng minh nguyên nhân nội bộ của model ngoài cơ chế gài lỗi trong variant. |

Tái hiện từ `src/`:

```powershell
.\.venv\Scripts\python.exe -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
.\.venv\Scripts\python.exe -m lab9.trace_case --shape fixed --claim C-002 --seed 11
.\.venv\Scripts\python.exe -m pytest -q -o addopts= tests/test_lab9_m3_reply.py -k c002
```

`swarm` gốc không phát event `reply`; metric `reply_amount_correct` chỉ có thể so khớp khi event này hiện diện. Không có event được đánh dấu không áp dụng trong reason và không phải bằng chứng rằng câu trả lời đúng; việc aggregate hiện tính True cho trường hợp không áp dụng, nên không diễn giải tỷ lệ này như độ bao phủ. Parser hiện nhận số có đơn vị đ, ₫, VND hoặc đồng; không bảo đảm hiểu mọi cách diễn đạt số tiền tự nhiên.
