"""
Production AI Agent — Part 6 Final Project
"""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    """Structured JSON formatter cho tiêu chí 10."""

    def format(self, record):
        log_obj = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        return json.dumps(log_obj)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Graceful shutdown và lifecycle management (tiêu chí 11)."""
    logger.info(json.dumps({"event": "startup", "app": "production-agent", "env": settings.environment}))
    yield
    logger.info(json.dumps({"event": "shutdown", "app": "production-agent"}))


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = None


@app.get("/health")
def health():
    """Liveness probe (tiêu chí 4): luôn trả 200 khi process còn chạy."""
    return {"status": "ok", "environment": settings.environment}


@app.get("/ready")
def ready():
    """Readiness probe (tiêu chí 5): 200 khi sẵn sàng, 503 khi Redis mất kết nối."""
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis service unavailable")
    return {"status": "ready"}


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    """Xử lý câu hỏi với xác thực, rate limiting và cost guard."""
    check_rate_limit(api_key)
    check_budget()

    start_time = time.time()
    answer = llm_ask(body.question)
    latency_ms = (time.time() - start_time) * 1000

    input_tokens = max(1, len(body.question.split()))
    output_tokens = max(1, len(answer.split()))
    cost = record_cost(input_tokens, output_tokens)

    logger.info(json.dumps({
        "event": "ask_complete",
        "question_len": len(body.question),
        "answer_len": len(answer),
        "cost_usd": cost,
        "latency_ms": round(latency_ms, 2),
    }))

    return {"question": body.question, "answer": answer}
