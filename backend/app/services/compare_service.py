"""ETF 对比计算服务：日期对齐、归一化、降采样、相关性、对齐指标"""

import logging
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
from typing import Any, Dict, List, Literal, Tuple

import pandas as pd

from app.core.cache import etf_cache
from app.services.akshare_service import ak_service
from app.services.metrics_service import calculate_period_metrics
from app.services.temperature_cache_service import temperature_cache_service

logger = logging.getLogger(__name__)

MAX_POINTS = 500  # 降采样阈值，320px 屏幕已超像素分辨率


class CompareService:

    def compute(
        self,
        codes: List[str],
        period: Literal["1y", "3y", "5y", "all"],
    ) -> Dict:
        # 1. 获取 ETF 名称
        etf_names = {}
        for code in codes:
            info = etf_cache.get_etf_info(code)
            etf_names[code] = info["name"] if info and info.get("name") else code

        # 2. 并行获取历史数据（含实时拼接，⚠️ 强制规范）
        def _fetch_one(code: str) -> Tuple[str, List]:
            records = ak_service.get_etf_history(code, period="daily", adjust="qfq")
            return code, records

        with ThreadPoolExecutor(max_workers=len(codes)) as pool:
            fetch_results = list(pool.map(lambda c: _fetch_one(c), codes))

        raw_df_map: Dict[str, pd.DataFrame] = {}
        df_map: Dict[str, pd.DataFrame] = {}
        for code, records in fetch_results:
            if not records:
                raise ValueError(f"ETF {code} 无历史数据")
            raw_df_map[code] = pd.DataFrame(records)
            df = raw_df_map[code][["date", "close"]].copy().rename(columns={"close": code})
            df["date"] = pd.to_datetime(df["date"])
            df_map[code] = df

        # 3. 日期对齐（inner merge）
        merged = df_map[codes[0]]
        for code in codes[1:]:
            merged = merged.merge(df_map[code], on="date", how="inner")
        merged = merged.sort_values("date").reset_index(drop=True)

        # 4. period 筛选
        if period != "all" and len(merged) > 0:
            end_date = merged["date"].iloc[-1]
            offset_map = {"1y": pd.DateOffset(years=1), "3y": pd.DateOffset(years=3), "5y": pd.DateOffset(years=5)}
            start_date = end_date - offset_map[period]
            merged = merged[merged["date"] >= start_date].reset_index(drop=True)

        # 5. 重叠期检查
        overlap_days = len(merged)
        if overlap_days < 30:
            raise ValueError(f"重叠交易日仅 {overlap_days} 天，不足 30 天，无法计算有意义的对比")

        warnings: List[str] = []
        if overlap_days < 120:
            warnings.append(f"重叠交易日仅 {overlap_days} 天，对比结果可能不够稳定")

        # 6. period_label
        date_strs = merged["date"].dt.strftime("%Y-%m-%d")
        period_label = f"{date_strs.iloc[0]} ~ {date_strs.iloc[-1]}"

        # 7. 归一化（基准 100）
        normalized_series: Dict[str, List[float]] = {}
        for code in codes:
            base = merged[code].iloc[0]
            if base == 0:
                raise ValueError(f"ETF {code} 基准价格为 0，数据异常")
            normed = (merged[code] / base * 100).round(2).tolist()
            normalized_series[code] = normed

        # 8. 相关性计算（基于日收益率）
        returns = merged[codes].pct_change().dropna()
        correlation: Dict[str, float] = {}
        for a, b in combinations(codes, 2):
            corr = returns[a].corr(returns[b])
            correlation[f"{a}_{b}"] = round(float(corr), 4) if not pd.isna(corr) else 0.0

        # 9. 降采样
        dates_list = date_strs.tolist()
        if len(dates_list) > MAX_POINTS:
            step = len(dates_list) / MAX_POINTS
            indices = [int(i * step) for i in range(MAX_POINTS)]
            indices[0] = 0
            indices[-1] = len(dates_list) - 1
            dates_list = [dates_list[i] for i in indices]
            for code in codes:
                normalized_series[code] = [normalized_series[code][i] for i in indices]

        # 10. 基于对齐数据计算各 ETF 核心指标
        metrics: Dict[str, Dict] = {}
        for code in codes:
            series = merged.set_index("date")[code]
            metrics[code] = calculate_period_metrics(series)

        # 11. Temperature（基于各 ETF 完整历史数据，非对齐窗口）
        temperatures: Dict[str, Any] = {}
        for code in codes:
            try:
                temp = temperature_cache_service.calculate_temperature(code, raw_df_map[code])
                temperatures[code] = temp
            except Exception:
                logger.warning(f"Temperature calculation failed for {code}", exc_info=True)
                temperatures[code] = None

        return {
            "etf_names": etf_names,
            "period_label": period_label,
            "warnings": warnings,
            "normalized": {
                "dates": dates_list,
                "series": normalized_series,
            },
            "correlation": correlation,
            "metrics": metrics,
            "temperatures": temperatures,
        }


compare_service = CompareService()
