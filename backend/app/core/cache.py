import time
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ETFCacheManager:
    def __init__(self):
        # 存储全量 ETF 列表 [{"code": "510300", "name": "沪深300ETF", ...}]
        self.etf_list: List[Dict] = []
        
        # 简单的哈希映射用于快速查找信息
        self.etf_map: Dict[str, Dict] = {}
        
        self.last_updated: float = 0
        # 缓存有效期 (秒) - 搜索列表和基础行情
        self.ttl = 60 

    def set_etf_list(self, data: List[Dict]):
        """更新 ETF 列表缓存"""
        self.etf_list = data
        # 建立 code -> info 映射，方便 O(1) 查找
        # 注意：etf_map 的 value 与 etf_list 的 item 是同一对象引用，
        # update_etf_info 的 merge 语义依赖此 identity 保证 list/map 同步更新。
        self.etf_map = {item["code"]: item for item in data}
        self.last_updated = time.time()
        logger.info(f"Cache updated with {len(data)} ETFs at {self.last_updated}")

    def get_etf_list(self) -> List[Dict]:
        return self.etf_list

    def get_etf_info(self, code: str) -> Optional[Dict]:
        """获取单个 ETF 的最新缓存信息"""
        return self.etf_map.get(code)

    def update_etf_info(self, info: Dict):
        """Manually update/insert an ETF info (e.g. from client sync)"""
        code = info.get("code")
        if not code:
            return
        
        # Update map (merge 语义，保留已有字段如 tags)
        existing = self.etf_map.get(code)
        if existing:
            existing.update(info)
        else:
            self.etf_map[code] = info

        # Update list (同样 merge 语义)
        found = False
        for i, item in enumerate(self.etf_list):
            if item["code"] == code:
                item.update(info)
                found = True
                break
        if not found:
            self.etf_list.append(info)

    def filter_by_tag(self, tag_label: str, limit: int = 50) -> List[Dict]:
        """按标签筛选 ETF"""
        results = []
        for item in self.etf_list:
            for t in item.get("tags", []):
                if t.get("label") == tag_label:
                    results.append(item)
                    break
            if len(results) >= limit:
                break
        return results

    def search(self, query: str, limit: int = 20) -> List[Dict]:
        """内存搜索：匹配代码或名称"""
        if not query:
            return []
        
        query = query.lower()
        results = []
        # 优先匹配代码
        for item in self.etf_list:
            if item["code"].startswith(query):
                results.append(item)
                if len(results) >= limit:
                    return results
        
        # 其次匹配名称
        if len(results) < limit:
            for item in self.etf_list:
                if item not in results and query in item["name"].lower():
                    results.append(item)
                    if len(results) >= limit:
                        break
        return results

    @property
    def is_initialized(self) -> bool:
        return len(self.etf_list) > 0

    @property
    def is_stale(self) -> bool:
        """检查缓存是否过期"""
        return (time.time() - self.last_updated) > self.ttl

# 单例实例
etf_cache = ETFCacheManager()
