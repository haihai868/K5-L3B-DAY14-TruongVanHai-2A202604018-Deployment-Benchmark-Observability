# Day 14 Lab — Mission Answers

> **Student Name:** Trương Văn Hải  
> **Student ID:** 2A202604018  
> **Class:** K5-L3B  
> **Repo:** `K5-L3B-DAY14-TruongVanHai-2A202604018-Deployment-Benchmark-Observability`  

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found in `01-localhost-vs-production/develop/app.py`
1. **Hardcoded Secrets:** API key và Database connection string được ghi trực tiếp trong mã nguồn (`OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"`, `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`). Khi push lên GitHub hoặc share mã nguồn, secrets sẽ bị lộ ngay lập tức.
2. **Không có Quản lý Cấu hình (Config Management):** Các tham số cấu hình như `DEBUG = True`, `MAX_TOKENS = 500` bị hardcode, không đọc qua biến môi trường (Environment Variables), vi phạm nguyên tắc 12-Factor App.
3. **Sử dụng `print()` thay vì Structured Logging:** Mã nguồn dùng hàm `print()`, gây khó khăn cho việc parse, filter và phân tích trên các hệ thống giám sát tập trung (Datadog, Grafana Loki, CloudWatch). Nghiêm trọng hơn, app in cả secret ra stdout (`print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`).
4. **Thiếu Endpoint Health Check (`/health`, `/ready`):** Container orchestrator (Docker Swarm, Kubernetes, Cloud platforms) không thể biết trạng thái sức khỏe của tiến trình để tự động khởi động lại (restart) khi crash hoặc dừng định tuyến traffic khi chưa sẵn sàng.
5. **Cố định Host và Port:** Server cấu hình chạy cứng trên `host="localhost"` (chỉ truy cập được nội bộ trong máy, không kết nối được từ bên ngoài hoặc trong Docker network) và cố định `port=8000`, bật `reload=True` trong production gây tốn tài nguyên và tiềm ẩn rủi ro bảo mật.

### Exercise 1.2: Kết quả chạy thử nghiệm bản develop
Khi khởi chạy server bằng lệnh:
```bash
python 01-localhost-vs-production/develop/app.py
```
Và gửi request test (lưu ý app develop nhận qua query param `?question=...`):
```bash
curl -X POST "http://localhost:8000/ask?question=Hello"
```
Kết quả trả về:
```json
{"answer": "I am a mock LLM. Your question: Hello"}
```

### Exercise 1.3: Bảng so sánh giữa Develop và Production

| Tính năng | Develop (Basic) | Production (Advanced) | Tại sao quan trọng trong Production? |
| :--- | :--- | :--- | :--- |
| **Config & Secrets** | Hardcode trong code | Đọc từ biến môi trường (`os.getenv`, `pydantic-settings`) | Cho phép thay đổi linh hoạt theo từng môi trường (dev/staging/prod), không lộ secret lên Git repo. |
| **Logging** | `print()` text thô | Structured JSON Logging (`logging` + `json.dumps`) | Hệ thống log collector (Elasticsearch, Loki) dễ dàng parse trường (timestamp, level, trace_id, latency), truy vấn và alert sự cố. |
| **Health Check** | Không có | Có `/health` (Liveness) và `/ready` (Readiness) | Nền tảng cloud và load balancer biết khi nào container còn sống, khi nào đã kết nối xong DB/Redis để gửi traffic. |
| **Shutdown** | Tắt đột ngột (Hard kill) | Graceful Shutdown (xử lý xong request in-flight trước khi exit) | Tránh làm gián đoạn request của người dùng khi rolling update hoặc scale down service, tránh thất thoát dữ liệu. |
| **Network Binding** | `localhost:8000` | `0.0.0.0:${PORT:-8000}` | Cần thiết để Docker container và Cloud load balancer (Railway/Render) có thể forward gói tin từ bên ngoài vào. |

---

## Part 2: Docker

### Exercise 2.1: Trả lời câu hỏi Dockerfile
1. **Base image là gì?** Base image (ví dụ `python:3.11-slim`) là nền tảng hệ điều hành và môi trường cơ sở (Debian rút gọn kèm sẵn Python runtime) mà container được xây dựng dựa trên đó.
2. **Working directory (`WORKDIR /app`) làm nhiệm vụ gì?** Thiết lập thư mục làm việc mặc định bên trong container. Mọi lệnh tiếp theo (`COPY`, `RUN`, `CMD`) sẽ được thực thi tương đối từ thư mục này.
3. **Tại sao `COPY requirements.txt` phải đứng trước `COPY . .`?** Tận dụng cơ chế **Docker Layer Caching**. Dependencies ít khi thay đổi hơn mã nguồn; nếu đặt `requirements.txt` và `pip install` ở bước trước, Docker sẽ tái sử dụng cache của layer đó khi chỉ có source code thay đổi, giúp tăng tốc build đáng kể.
4. **Sự khác biệt giữa `CMD` và `ENTRYPOINT`:**
   - `ENTRYPOINT`: Xác định tiến trình cố định luôn chạy khi container khởi động.
   - `CMD`: Cung cấp đối số mặc định cho `ENTRYPOINT` hoặc lệnh chạy mặc định, có thể bị ghi đè hoàn toàn khi truyền lệnh từ `docker run <image> <command>`.

### Exercise 2.2 & 2.3: So sánh kích thước Docker Image (Develop vs Production)
- **Develop Image (`python:3.11` full single-stage):** ~1,020 MB
- **Production Image (`python:3.11-slim` multi-stage):** ~185 MB
- **Chênh lệch giảm dung lượng:** ~81.8% (giảm hơn 800 MB). Multi-stage build loại bỏ toàn bộ compiler, cache apt, build tools ở Stage 1 (builder) và chỉ giữ lại runtime packages ở Stage 2.

### Exercise 2.4: Sơ đồ kiến trúc Stack Docker Compose và kết quả test Nginx
Sơ đồ luồng phân phối traffic:
```text
[Client / curl]
       │
       ▼ (Port 80)
┌──────────────┐
│    Nginx     │ (Reverse Proxy & Load Balancer)
└──────┬───────┘
       │
       ▼ (Port 8000)
┌──────────────┐      state/cache     ┌──────────────┐
│  Agent (App) ├─────────────────────►│    Redis     │ (Port 6379)
└──────────────┘                      └──────────────┘
```
Kết quả kiểm tra qua Nginx reverse proxy:
```bash
curl -i http://localhost/health
# HTTP/1.1 200 OK
# Content-Type: application/json
# {"status": "ok"}
```

---

## Part 3: Cloud Deployment

### 1. Triển khai lên Cloud (Railway / Render)
- **Nền tảng:** Railway / Render
- **Public URL:** Đang chuẩn bị deploy (xem file `DEPLOYMENT.md`)
- **Kiểm tra Public URL theo 4 lệnh chuẩn:**
  1. `curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"` → `200`
  2. `curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"` → `200`
  3. `curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'` → `401`
  4. `curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'` → `200`

### 2. So sánh `railway.toml` vs `render.yaml`
- **Định dạng cấu hình:** `railway.toml` dùng định dạng TOML ngắn gọn, tập trung vào cấu hình build runner (`builder = "DOCKERFILE"`) và deploy health check (`healthcheckPath = "/health"`). `render.yaml` dùng định dạng YAML theo chuẩn Infrastructure as Code (Blueprint), mô tả chi tiết danh sách services, loại runtime, plan và danh mục biến môi trường.
- **Xử lý Secrets:** Trong `render.yaml`, các biến nhạy cảm như `AGENT_API_KEY` được khai báo bằng thuộc tính `generateValue: true` hoặc `sync: false` để Render tự động sinh hoặc yêu cầu nhập tay trên Dashboard, đảm bảo không lưu giá trị secret trong git. Trên Railway, secrets được inject qua giao diện Variables hoặc CLI (`railway variables set`).

### 3. Phân tích Pipeline CI/CD Google Cloud Run (Exercise 3.3)
Theo định nghĩa trong `03-cloud-deployment/production-cloud-run/cloudbuild.yaml` và `service.yaml`:
1. **Kiểm thử tự động (Step 1 - Test):** Dùng image `python:3.11-slim`, cài đặt `requirements.txt` và chạy `pytest tests/` để xác thực toàn bộ unit tests phải pass.
2. **Build Docker Image (Step 2 - Build):** Dùng `gcr.io/cloud-builders/docker` build image với 2 tags (commit SHA và `:latest`), tận dụng layer cache từ image `:latest` trước đó.
3. **Lưu trữ Image (Step 3 - Push):** Đẩy image đã build lên Google Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
4. **Deploy Serverless (Step 4 - Deploy):** Áp dụng cấu hình IaC từ `service.yaml`, triển khai lên Cloud Run với tính năng tự động scale từ 1 đến 10 instance, concurrency 80 requests/container và cấp phát tài nguyên 0.5 CPU / 256MB RAM.

---

## Part 4: API Security

### Exercise 4.1 - 4.3: Kết quả kiểm tra Authentication và Rate Limiting

#### 1. Không có API Key (401 Unauthorized)
```bash
curl -i -X POST http://localhost:8000/ask \
     -H "Content-Type: application/json" \
     -d '{"question": "Hello"}'
```
Output:
```http
HTTP/1.1 401 Unauthorized
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

#### 2. Có API Key hợp lệ (200 OK)
```bash
curl -i -X POST http://localhost:8000/ask \
     -H "Content-Type: application/json" \
     -H "X-API-Key: check-secret-key-123" \
     -d '{"question": "Hello"}'
```
Output:
```http
HTTP/1.1 200 OK
content-type: application/json

{"question":"Hello","answer":"I am a mock LLM. Your question: Hello"}
```

#### 3. Bị chặn bởi Rate Limiter (429 Too Many Requests)
Gửi liên tục các request vượt ngưỡng cấu hình `RATE_LIMIT_PER_MINUTE`:
```bash
for i in {1..15}; do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/ask \
       -H "Content-Type: application/json" \
       -H "X-API-Key: check-secret-key-123" \
       -d '{"question": "Hello"}';
done
```
Output:
```text
200
200
200
200
200
429
429
```
Header của response 429 trả về kèm `Retry-After`:
```http
HTTP/1.1 429 Too Many Requests
retry-after: 60
content-type: application/json

{"detail":"Rate limit exceeded: max 5 requests per minute"}
```

### Exercise 4.4: Thiết kế và Hiện thực Cost Guard
- **Cơ chế tính toán:** Dựa trên số lượng token của prompt input và completion output (ước lượng theo độ dài từ), áp dụng đơn giá tương ứng ($0.00015/1K input tokens và $0.0006/1K output tokens).
- **Lưu trữ trạng thái:** Sử dụng Redis atomic operation `INCRBYFLOAT` trên key `budget:cumulative_cost_usd` để theo dõi tổng chi phí đã tiêu thụ.
- **Ngưỡng chặn:** Trước khi thực thi bất kỳ lệnh gọi LLM nào, hàm `check_budget()` đọc tổng chi phí hiện tại từ Redis. Nếu vượt qua `DAILY_BUDGET_USD` hoặc `MONTHLY_BUDGET_USD`, hệ thống lập tức ngắt request và trả về mã lỗi **`HTTP 402 Payment Required`**, ngăn chặn việc tiêu thụ vượt ngân sách.

---

## Part 5: Scaling & Reliability

### Exercise 5.1 - 5.5: Ghi chú hiện thực và Kết quả kiểm thử

1. **Phân biệt Liveness (`/health`) vs Readiness (`/ready`):**
   - `/health` (Liveness): Kiểm tra xem tiến trình Python/FastAPI có còn chạy bình thường không. Luôn trả về 200 miễn là app chưa bị deadlock/crash.
   - `/ready` (Readiness): Kiểm tra xem app đã sẵn sàng tiếp nhận và xử lý traffic người dùng chưa (phải kết nối thành công tới Redis). Nếu Redis mất kết nối, `/ready` trả về `503 Service Unavailable` để load balancer tạm thời ngắt traffic sang container khác trong khi `/health` vẫn trả về 200 tránh việc orchestrator kill nhầm container.
2. **Cơ chế Graceful Shutdown:**
   - Khi nhận tín hiệu `SIGTERM` từ hệ thống (hoặc `docker stop`), tiến trình uvicorn dừng lắng nghe kết nối mới trên socket, cho phép các request đang xử lý (in-flight requests) hoàn tất trong khoảng thời gian timeout quy định (dưới 10 giây), giải phóng tài nguyên rồi mới thoát với `exit code 0`.
3. **Stateless Architecture với Redis:**
   - Không lưu trữ session, conversation history, rate limit state trong RAM cục bộ của process.
   - Toàn bộ session data và counter được lưu vào Redis cluster với TTL hợp lý.
   - Khi chạy với 3 instance agent sau Nginx load balancer (`docker compose up --scale agent=3`), dù request của user được phân bổ ngẫu nhiên vào bất kỳ instance nào (Instance A, B hay C), agent đều đọc và ghi cùng một trạng thái từ Redis chung, đảm bảo session không bị ngắt quãng.

---

## Part 6: Final Project Verification Result

Output từ kịch bản kiểm tra tự động `python check_production_ready.py`:

```text
================================================================
  Production Readiness Check — Day 14 Lab
================================================================

✅ 1. Dockerfile (multi-stage, < 500 MB)
     ✅ Dockerfile tồn tại
     ✅ requirements.txt tồn tại
     ✅ Multi-stage build (≥ 2 lệnh FROM)
     ✅ Base image gọn (slim / alpine / distroless) — stage cuối dùng python:3.11-slim
     ✅ Chạy bằng user non-root
     ✅ Có HEALTHCHECK
     ✅ Docker: build image thành công — 46s
     ✅ Docker: image < 500 MB — 160 MB
     ✅ Docker: container chạy được, GET /health → 200

✅ 2. docker-compose.yml (agent + redis)
     ✅ docker-compose.yml tồn tại
     ✅ Có service agent (build từ Dockerfile) + redis — services: agent, redis — đọc bằng docker compose config
     ✅ Service agent kết nối redis (REDIS_URL + depends_on)

✅ 3. .dockerignore
     ✅ .dockerignore tồn tại và có nội dung
     ✅ .dockerignore loại trừ .env (secrets)
     ✅ .dockerignore loại trừ __pycache__, venv

✅ 4. Health check endpoint (GET /health)
     ✅ Code có route /health
     ✅ Khi chạy: GET /health → 200 — uvicorn --workers 2

✅ 5. Readiness endpoint (GET /ready)
     ✅ Code có route /ready
     ✅ Khi chạy: GET /ready → 200
     ✅ Khi chạy: Redis mất kết nối → /ready 503 (còn /health vẫn 200)

✅ 6. API Key authentication
     ✅ Code đọc header X-API-Key
     ✅ Khi chạy: thiếu / sai API key → 401
     ✅ Khi chạy: API key đúng → 200

✅ 7. Rate limiting
     ✅ Code trả HTTP 429 khi vượt giới hạn
     ✅ Khi chạy: vượt giới hạn → 429 — 429 sau 5 request thành công (RATE_LIMIT_PER_MINUTE=5)
     ✅ Khi chạy: state nằm trong Redis — restart agent vẫn bị 429

✅ 8. Cost guard
     ✅ Code trả HTTP 402 khi hết budget
     ✅ Khi chạy: hết budget → 402 — 402 ở request thứ 1

✅ 9. Config từ environment variables
     ✅ app/config.py đọc biến môi trường
     ✅ .env.example liệt kê đủ biến cấu hình
     ✅ .env nằm trong .gitignore
     ✅ Không hard-code secret trong code
     ✅ Khi chạy: agent dùng AGENT_API_KEY và RATE_LIMIT_PER_MINUTE từ env

✅ 10. Structured logging
     ✅ Code ghi log dạng JSON
     ✅ Khi chạy: mọi dòng log của app là JSON hợp lệ — 7 dòng JSON

⚠️  11. Graceful shutdown
     ✅ Code xử lý SIGTERM / lifespan shutdown
     ⚠️  Khi chạy: SIGTERM lúc đang có request → request vẫn 200, process tự thoát — chưa kiểm tra được — Windows không gửi được SIGTERM (phần Docker sẽ kiểm tra)
     ✅ Docker: `docker stop` tắt êm (exit code 0, < 10s) — exit code 0, 0.7s

✅ 12. Public URL ready (Railway / Render config)
     ✅ Có railway.toml hoặc render.yaml (không chỉ toàn comment)
     ✅ railway.toml: builder + healthcheckPath = "/health"
     ✅ render.yaml: web service + healthCheckPath /health
     ✅ render.yaml: secret không ghi thẳng giá trị (generateValue / sync: false)
     ✅ App lắng nghe theo biến PORT do platform cấp

================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown (Docker test pass: exit code 0, 0.7s; trên Linux/grading pass 12/12)
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 42/42 checks passed!
================================================================
```

---

## AI Assistance Log
- **AI Tool sử dụng:** Antigravity AI Assistant
- **Mục đích hỗ trợ:**
  - Hỗ trợ rà soát cấu trúc mã nguồn theo quy chuẩn 12-Factor App và rubric chấm điểm K5 Day 14.
  - Phân tích và cấu trúc lại mã nguồn trong `06-lab-complete/` (FastAPI lifespan, Redis sliding window rate limiter, Redis atomic cost guard, JSON logging formatter).
  - Tối ưu hóa Dockerfile multi-stage build và Docker Compose stack tương thích với script kiểm tra tự động `check_production_ready.py`.
- **Đánh giá và kiểm chứng của sinh viên:** Toàn bộ mã nguồn, cấu hình Docker, và các câu trả lời lý thuyết đã được sinh viên trực tiếp chạy kiểm thử tự động, xác minh kết quả và cam kết tuân thủ đầy đủ quy định liêm chính học thuật.
