"""ETF 对比端点"""

import re
import logging
from fastapi import APIRouter, HTTPException, Query, Request

from app.services.compare_service import compare_service
from app.middleware.rate_limit import limiter

router = APIRouter()
logger = logging.getLogger(__name__)

ETF_CODE_RE = re.compile(r"^\d{6}$")
VALID_PERIODS = {"1y", "3y", "5y", "all"}


@router.get("/compare")
@limiter.limit("30/minute")
async def get_etf_compare(
    request: Request,
    codes: str = Query(..., description="逗号分隔的 ETF 代码，2-3 个"),
    period: str = Query("3y", description="对比周期: 1y, 3y, 5y, all"),
):
    """ETF 对比：归一化走势 + 相关性系数"""
    # 参数校验
    if period not in VALID_PERIODS:
        raise HTTPException(status_code=400, detail=f"period 必须为 {', '.join(VALID_PERIODS)} 之一")

    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if len(code_list) < 2 or len(code_list) > 3:
        raise HTTPException(status_code=400, detail="codes 数量必须为 2-3 个")
    for c in code_list:
        if not ETF_CODE_RE.match(c):
            raise HTTPException(status_code=400, detail=f"ETF 代码格式无效: {c}")

    # 计算
    try:
        result = compare_service.compute(code_list, period)
    except ValueError as e:
        msg = str(e)
        if "无历史数据" in msg:
            raise HTTPException(status_code=404, detail=msg)
        elif "不足 30" in msg:
            raise HTTPException(status_code=422, detail=msg)
        else:
            raise HTTPException(status_code=422, detail=msg)
    except Exception:
        logger.exception("对比计算失败")
        raise HTTPException(status_code=500, detail="对比计算失败，请稍后重试")

    return result
