"""
同花顺历史数据源

直接调用 d.10jqka.com.cn JSONP 接口，无需认证。
URL 中 01 = 日K前复权，返回上市至今全部数据。
"""
import json
import logging
import time
from typing import Optional

import pandas as pd
import requests

from app.core.metrics import datasource_metrics

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "http://stockpage.10jqka.com.cn/",
}


def _parse_ths_response(text: str) -> Optional[pd.DataFrame]:
    """解析同花顺 JSONP 响应为 DataFrame"""
    try:
        idx = text.index("{")
        json_str = text[idx:-1]
        data = json.loads(json_str)
        raw = data.get("data", "")
        if not raw:
            return None
        rows = []
        for item in raw.split(";"):
            parts = item.split(",")
            if len(parts) >= 7:
                rows.append(parts[:7])
        if not rows:
            return None
        df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume", "amount"])
        df["date"] = pd.to_datetime(df["date"], format="%Y%m%d").dt.strftime("%Y-%m-%d")
        for col in ["open", "high", "low", "close", "volume", "amount"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
    except Exception:
        return None


class ThsHistorySource:
    """同花顺历史数据源，实现 HistoryDataSource 协议"""

    name: str = "ths_history"

    def fetch_history(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> Optional[pd.DataFrame]:
        # 01=日K前复权, 00=不复权, 02=后复权
        fq_map = {"qfq": "01", "hfq": "02", "": "00"}
        fq = fq_map.get(adjust, "01")
        url = f"http://d.10jqka.com.cn/v6/line/hs_{code}/{fq}/last36000.js"

        start = time.monotonic()
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=10)
            if resp.status_code != 200:
                latency = (time.monotonic() - start) * 1000
                datasource_metrics.record_failure(self.name, f"HTTP {resp.status_code}", latency)
                logger.warning("[ths_history] HTTP %d for %s", resp.status_code, code)
                return None

            df = _parse_ths_response(resp.text)
            if df is None or df.empty:
                latency = (time.monotonic() - start) * 1000
                datasource_metrics.record_failure(self.name, f"empty result for {code}", latency)
                return None

            # 日期范围过滤
            sd = start_date.replace("-", "")
            ed = end_date.replace("-", "")
            sd_fmt = f"{sd[:4]}-{sd[4:6]}-{sd[6:8]}" if len(sd) == 8 else start_date
            ed_fmt = f"{ed[:4]}-{ed[4:6]}-{ed[6:8]}" if len(ed) == 8 else end_date
            df = df[(df["date"] >= sd_fmt) & (df["date"] <= ed_fmt)]

            if df.empty:
                latency = (time.monotonic() - start) * 1000
                datasource_metrics.record_failure(self.name, f"no data in range for {code}", latency)
                return None

            latency = (time.monotonic() - start) * 1000
            datasource_metrics.record_success(self.name, latency)
            return df.reset_index(drop=True)
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            datasource_metrics.record_failure(self.name, str(e), latency)
            logger.warning("[ths_history] failed for %s: %s", code, e)
            return None

    def is_available(self) -> bool:
        return True
