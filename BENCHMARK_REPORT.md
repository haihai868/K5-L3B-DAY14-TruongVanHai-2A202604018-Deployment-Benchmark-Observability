# Benchmark & Observability Report — Day 14

> Mọi con số được lấy trực tiếp từ các file báo cáo JSON, CSV và kiểm thử thực tế.

**Họ tên:** Trương Văn Hải  
**MSSV:** 2A202604018  
**Lớp:** K5-L3B  
**Ngày chạy:** 2026-11-26  
**Môi trường:** Windows 11, Docker Desktop (WSL2), Python 3.13, 12 CPUs, 8GB RAM  

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Đảm bảo 95% người dùng nhận phản hồi nhanh dưới 0.5s, duy trì trải nghiệm người dùng mượt mà |
| Error rate `/ask` | < 2.0 % | Cho phép dung sai hợp lý trước các lỗi tạm thời từ LLM upstream provider (429/503) |
| Accuracy trên golden dataset | ≥ 80.0 % | Đảm bảo câu trả lời của agent đạt chuẩn kỹ thuật, không bị ảo giác (hallucination) |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 3.93 | 210.2 | 248.2 | 1721.1 | 1.00% | PASS |
| 10 | 41.45 | 212.0 | 250.7 | 1668.7 | 0.67% | PASS |
| 50 | 39.71 | 569.4 | 3413.7 | 4906.4 | 0.33% | FAIL |
| 100 | 37.10 | 1041.7 | 5559.9 | 5810.7 | 1.67% | FAIL |

**Nhận xét:** RPS không tăng tuyến tính theo concurrency. Khi tăng concurrency từ 1 lên 10, RPS tăng vọt từ 3.93 lên 41.45 req/s nhờ cơ chế bất đồng bộ (asyncio). Tuy nhiên, khi tăng tiếp lên 50 và 100, RPS bị nghẽn ở mức ~37–40 req/s, trong khi latency p50 và p95 tăng gấp nhiều lần (hiện tượng bão hòa hàng đợi - queue saturation). Để xử lý concurrency cao hơn, bắt buộc phải scale ngang thêm instance.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 227.6 | 493.9 | 544.3 |
| 0.03 (mặc định) | 240.6 | 480.9 | 1681.7 |
| 0.1 | 361.3 | 1704.0 | 1733.4 |

**Nhận xét:** Chỉ số nhạy nhất với request chậm là p99 (và p95 khi slow rate lên 10%). Latency trung bình (avg) che giấu tail latency vì chỉ tăng từ 227.6 ms lên 361.3 ms, trong khi thực tế có tới 10% người dùng phải chờ hơn 1.7 giây. Do đó SLO không được đặt theo average mà phải dùng p95 hoặc p99.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.5 | 109.0 | 111.6 |
| Tổng cost (USD) | $0.000409 | $0.000759 | $0.000772 |
| Cost / câu đúng (USD) | $0.000409 | $0.000036 | $0.000034 |
| Quality gate | FAIL | PASS | PASS |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | token, hết hạn, chữ ký | Bổ sung entry JWT vào `KNOWLEDGE_BASE`: giải thích JWT là token tự chứa thông tin, có thời hạn hết hạn và chữ ký số |
| `scaling-03` | cpu, memory, custom metrics | Bổ sung entry HPA vào `KNOWLEDGE_BASE`: giải thích Kubernetes HPA scale dựa trên CPU, Memory và custom metrics |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**
Agent v2 dùng RAG (tìm kiếm tài liệu trong Knowledge Base) nên prompt dài hơn, tiêu tốn token nhiều hơn (111.6 vs 57.5) và chi phí tổng tăng từ $0.000409 lên $0.000772. Tuy nhiên, nhờ độ chính xác tăng vọt từ 4.3% lên 100%, **chi phí trên mỗi câu trả lời đúng (Cost per correct answer)** của v2 rẻ hơn gấp 12 lần so với v1 ($0.000034 vs $0.000409). Đây là trade-off hoàn toàn xứng đáng trong production.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals) — `screenshots/grafana-dashboard.png`
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian) — `screenshots/jaeger-slow-trace.png`
- [x] Một trace lỗi trong Jaeger (có event `exception`) — `screenshots/jaeger-error-trace.png`
- [x] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing** — `screenshots/prometheus-alert-firing.png`

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | ~1m05s | Error rate (đỏ khi > 5%) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | ~2m10s | Latency (p95 / p99) |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | ~2m05s | Cost USD/h (vượt $2/h) |
| D | `docker pause` 1 instance | `AgentInstanceDown` | ~35s | Instances up (giảm từ 2 xuống 1) |
| E | `AGENT_VERSION=v1` | (Không có alert nào) | N/A | Retrieval hit ratio / Agent Info |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Thí nghiệm E hạ cấp agent xuống `v1` (không có retrieval/RAG). Về mặt hạ tầng hệ thống, service vẫn trả về HTTP 200, CPU/RAM bình thường, latency thậm chí còn giảm do prompt ngắn hơn, nên các metric hạ tầng và Golden Signals (Latency, Traffic, Errors, Saturation) đều hiển thị "xanh" và không vi phạm alert.
Để phát hiện sự cố suy giảm chất lượng câu trả lời (quality regression / degraded output) trong production, cần áp dụng các biện pháp:
1. **Periodic Synthetic Quality Evals (CI/CD & Cron):** Chạy định kỳ bộ kiểm thử đánh giá câu trả lời trên golden dataset (tương tự `run_eval.py`) hoặc dùng LLM-as-a-judge để chấm điểm độ chuẩn xác, liên quan và tỷ lệ hallucination.
2. **Theo dõi LLM Application Metrics:** Giám sát metric `agent_retrieval_hits_total` (retrieval hit ratio tụt về 0) và `llm_tokens_total` (số token đầu vào/ra giảm bất thường) trên dashboard Grafana.
3. **User Feedback & Thumbs-up/down:** Theo dõi tỷ lệ phản hồi tiêu cực từ người dùng cuối (tỷ lệ downvote tăng đột biến sẽ kích hoạt alert nghiệp vụ).

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: `c07b217367432ba4c189a130e23dbd7c`
- Tổng thời gian: `1951.1 ms`
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (`1656.4 ms`, chiếm `84.9%` tổng thời gian request)
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-26T10:00:17.809743+00:00", "level": "INFO", "service": "observable-agent", "instance": "e8d472c7111e", "event": "llm_call", "trace_id": "c07b217367432ba4c189a130e23dbd7c", "span_id": "4b7a1d35d81d099f", "request_id": "c89c61dde5de", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 83, "output_tokens": 44, "cost_usd": 3.9e-05, "llm_ms": 1656.4}
```

Dòng log kết thúc request:
```json
{"ts": "2026-11-26T10:00:17.810572+00:00", "level": "INFO", "service": "observable-agent", "instance": "e8d472c7111e", "event": "http_request", "trace_id": "c07b217367432ba4c189a130e23dbd7c", "span_id": "4b7a1d35d81d099f", "request_id": "c89c61dde5de", "method": "POST", "route": "/ask", "status": 200, "ms": 1951.1}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 20.32 | 200 | 300 | 1700 | 8 (1.38%) |
| 3 | 38.32 | 200 | 340 | 1700 | 7 (0.67%) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

1. **Hiệu quả scaling:** Khi scale từ 1 instance lên 3 instance qua Nginx Load Balancer, tổng thông lượng (throughput) tăng gần gấp đôi từ **20.32 RPS lên 38.32 RPS** với cùng 100 concurrent users. Tỷ lệ lỗi (failures) giảm từ 1.38% xuống 0.67% do tải được phân phối đều hơn.
2. **Chỉ số p95 và p99:** Giá trị p95 ở 1 instance là 300 ms và ở 3 instance là 340 ms (chênh lệch không đáng kể), trong khi p99 giữ nguyên ở mức 1700 ms. Điều này cho thấy p95/p99 bị chi phối bởi độ trễ upstream của mô hình LLM (`MOCK_SLOW_RATE=0.03` gây trễ ngẫu nhiên ~1.6 - 1.7s) chứ không phải do hàng đợi Nginx.
3. **Nút thắt hệ thống (Bottleneck):** Nút thắt chính là thời gian xử lý I/O của cuộc gọi LLM upstream và giới hạn tài nguyên CPU/RAM trên container đơn lẻ. Scaling theo chiều ngang giúp tăng RPS và giảm hàng đợi, nhưng không thể giảm latency vốn có của mỗi lần sinh text từ mô hình LLM nếu không dùng streaming hoặc caching kết quả (semantic cache).

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. **SLO phải dựa trên Percentiles (p95/p99) thay vì Average:** Độ trễ trung bình thường che giấu tail latency nguy hiểm (nơi một lượng người dùng chịu thời gian chờ lớn gấp 8-10 lần bình thường).
  2. **Liên kết 3 trụ cột (Metrics - Traces - Logs):** Metrics qua Prometheus/Grafana cho biết "hệ thống có đang gặp vấn đề không"; Tracing qua OpenTelemetry/Jaeger chỉ ra chính xác "span/thành phần nào gây nghẽn"; và Structured JSON Logs chứa `trace_id` giúp trích xuất toàn bộ ngữ cảnh chi tiết của sự cố.
  3. **Độ chính xác và Trade-off Chi phí trong AI Agent:** Agent phức tạp hơn (như RAG v2) tiêu tốn nhiều token và tiền hơn trên mỗi request, nhưng độ chính xác tăng từ 4.3% lên 100%, giúp chi phí trên mỗi câu trả lời đúng (Cost per correct answer) rẻ hơn 12 lần.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?
  1. **Semantic Cache Hit Ratio:** Đo lường tỷ lệ các câu hỏi trùng lặp hoặc tương đồng được trả về ngay từ cache (Redis) để giảm 90% chi phí và độ trễ LLM.
  2. **Alert Token Quota / Rate-limit từ Upstream Provider:** Giám sát số mã lỗi 429 từ OpenAI/Anthropic/Gemini và thời gian retry-after để tự động chuyển vùng hoặc fallback sang mô hình nhỏ hơn.
  3. **LLM Hallucination / Toxicity / Guardrail Violations Rate:** Đếm số lần guardrail phát hiện nội dung độc hại, injection prompt, hoặc thông tin nhạy cảm để kích hoạt cảnh báo an ninh bảo mật tức thì.
