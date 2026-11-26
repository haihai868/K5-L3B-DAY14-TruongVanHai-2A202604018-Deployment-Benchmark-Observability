"""
Cost guard (tiêu chí 8).

Yêu cầu:
  • Cộng dồn chi phí LLM (tính theo token) vào Redis
  • Tổng chi phí vượt DAILY_BUDGET_USD (hoặc MONTHLY_BUDGET_USD) → HTTP 402
"""
from fastapi import HTTPException
from app.config import settings
from app.redis_client import get_redis

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006
REDIS_COST_KEY = "budget:cumulative_cost_usd"


def get_current_cost() -> float:
    redis_client = get_redis()
    if redis_client is None:
        return 0.0
    try:
        val = redis_client.get(REDIS_COST_KEY)
        return float(val) if val else 0.0
    except Exception:
        return 0.0


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    current_cost = get_current_cost()
    max_budget = min(settings.daily_budget_usd, settings.monthly_budget_usd)
    if current_cost >= max_budget:
        raise HTTPException(
            status_code=402,
            detail=f"Budget exceeded: current cost ${current_cost:.6f} >= limit ${max_budget:.6f}",
        )


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = (input_tokens / 1000.0) * PRICE_INPUT_PER_1K + (output_tokens / 1000.0) * PRICE_OUTPUT_PER_1K
    redis_client = get_redis()
    if redis_client is not None:
        try:
            redis_client.incrbyfloat(REDIS_COST_KEY, cost)
        except Exception:
            pass
    return cost
