# Deployment Information — Day 14 Lab

> **Student Name:** Trương Văn Hải  
> **Student ID:** 2A202604018  
> **Class:** K5-L3B  

## Public URL
https://your-agent.up.railway.app (hoặc https://your-agent.onrender.com)

## Platform
Railway (hoặc Render)

## Test Commands (CP6 Verification)

Đặt biến môi trường:
```bash
export BASE="https://your-agent.up.railway.app"
export AGENT_API_KEY="your-secret-key"
```

### 1. Health Check (GET /health) → 200
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
# Expected HTTP Code: 200
```

### 2. Readiness Check (GET /ready) → 200
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
# Expected HTTP Code: 200
```

### 3. API Test không có API Key (POST /ask) → 401
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hello"}'
# Expected HTTP Code: 401
```

### 4. API Test có API Key hợp lệ (POST /ask) → 200
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
# Expected HTTP Code: 200
```

## Environment Variables Đã Thiết Lập Trên Nền Tảng
- `PORT`: Do platform tự cấp (hoặc mặc định `8000`)
- `ENVIRONMENT`: `production`
- `AGENT_API_KEY`: `<secret-api-key>` (đặt trên Dashboard của platform, không ghi trong code)
- `REDIS_URL`: `<redis-connection-url>` (kết nối tới instance Redis được tạo trên cloud)
- `RATE_LIMIT_PER_MINUTE`: `10`
- `DAILY_BUDGET_USD`: `10.0`
- `MONTHLY_BUDGET_USD`: `100.0`

## Danh sách ảnh chụp minh chứng
- [Deployment Dashboard](screenshots/dashboard.png) — Ảnh trang quản trị project trên Railway / Render.
- [Service Running Logs](screenshots/running.png) — Ảnh log service khởi động thành công và kết nối Redis.
- [Test Results](screenshots/test.png) — Ảnh terminal chạy 4 lệnh curl trên với HTTP code tương ứng (200, 200, 401, 200).
