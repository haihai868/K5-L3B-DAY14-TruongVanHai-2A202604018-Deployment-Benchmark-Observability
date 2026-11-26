# Deployment Information — Day 14 Lab

> **Student Name:** Trương Văn Hải  
> **Student ID:** 2A202604018  
> **Class:** K5-L3B  

## Public URL
https://k5-l3b-day14-truongvanhai-2a202604018.onrender.com

## Platform
Render (Docker Runtime + Managed Redis)

## Test Commands (CP6 Verification)

Đặt biến môi trường:
```bash
export BASE="https://k5-l3b-day14-truongvanhai-2a202604018.onrender.com"
export AGENT_API_KEY="your-secret-key"
```

### 1. Health Check (GET /health) → 200
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
# Actual HTTP Code: 200
```

### 2. Readiness Check (GET /ready) → 200
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
# Actual HTTP Code: 200
```

### 3. API Test không có API Key (POST /ask) → 401
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hello"}'
# Actual HTTP Code: 401
```

### 4. API Test có API Key hợp lệ (POST /ask) → 200
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
# Actual HTTP Code: 200
```

## Environment Variables Đã Thiết Lập Trên Render
- `PORT`: 8000 (Render tự inject port nội bộ)
- `ENVIRONMENT`: `production`
- `AGENT_API_KEY`: Đã cấu hình trên Render Environment Variables
- `REDIS_URL`: Đã kết nối với Internal Redis service trên Render
- `RATE_LIMIT_PER_MINUTE`: `10`
- `DAILY_BUDGET_USD`: `10.0`
- `MONTHLY_BUDGET_USD`: `100.0`

## Danh sách ảnh chụp minh chứng
- [Deployment Dashboard](screenshots/dashboard.png) — Giao diện quản trị Web Service và Redis trên Render.
- [Service Running Logs](screenshots/running.png) — Log container khởi động thành công và sẵn sàng nhận request.
- [Test Results](screenshots/test.png) — Màn hình terminal chạy kiểm tra các endpoint trả về đúng mã HTTP.
