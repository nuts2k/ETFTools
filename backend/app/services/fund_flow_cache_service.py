"""
资金流向缓存服务

包装 fund_flow_service，提供缓存功能
"""

import logging
from typing import Optional, Dict, Any

from app.services.akshare_service import disk_cache
from app.services.fund_flow_service import fund_flow_service

logger = logging.getLogger(__name__)


class FundFlowCacheService:
    """资金流向缓存服务"""

    CACHE_PREFIX = "fund_flow"
    CACHE_EXPIRE = 4 * 3600  # 4小时（秒）

    def _get_cache_key(self, code: str) -> str:
        """生成缓存 key"""
        return f"{self.CACHE_PREFIX}:{code}"

    def get_fund_flow(
        self, code: str, force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        获取资金流向数据（带缓存）

        Args:
            code: ETF 代码
            force_refresh: 强制刷新，跳过缓存

        Returns:
            资金流向数据字典，无数据时返回 None
        """
        cache_key = self._get_cache_key(code)

        # 强制刷新时跳过缓存读取
        if not force_refresh:
            cached = disk_cache.get(cache_key)
            if cached is not None:
                logger.debug(f"[{code}] Fund flow cache hit")
                return cached

        # 缓存未命中或强制刷新：重新计算
        logger.debug(f"[{code}] Computing fund flow (cache miss or force refresh)")
        result = fund_flow_service.get_fund_flow_data(code)

        if result:
            disk_cache.set(cache_key, result, expire=self.CACHE_EXPIRE)
            logger.debug(f"[{code}] Fund flow cached for {self.CACHE_EXPIRE}s")

        return result


# 全局单例
fund_flow_cache_service = FundFlowCacheService()
