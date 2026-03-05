"""
SSE ETF 份额历史补录脚本

用于一次性补录上交所 ETF 份额历史数据，按日期范围批量拉取。
已存在的 (code, date) 记录自动跳过，重复运行幂等。

使用方式：
    # 补录指定日期范围
    python backend/scripts/backfill_sse_share_history.py --start 2020-01-01 --end 2026-03-04

    # 仅补录某一天（测试用）
    python backend/scripts/backfill_sse_share_history.py --start 2025-06-30 --end 2025-06-30

    # dry-run：只打印会请求哪些日期，不实际写库
    python backend/scripts/backfill_sse_share_history.py --start 2025-01-01 --end 2025-01-31 --dry-run
"""

import sys
import os

# 从 backend/scripts/ 往上一级指向 backend/，使 from app.xxx import yyy 可用
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import time
import logging
from datetime import date, timedelta

import requests
import pandas as pd
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError

from app.core.share_history_database import share_history_engine
from app.models.etf_share_history import ETFShareHistory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

SSE_API_URL = "https://query.sse.com.cn/commonQuery.do"
SSE_HEADERS = {
    "Referer": "https://www.sse.com.cn/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def build_etf_whitelist() -> set:
    """从 Sina 列表接口构建 ETF 白名单（过滤债券 ETF）"""
    import akshare as ak

    logger.info("Building ETF whitelist from Sina list...")
    df = ak.fund_etf_category_sina(symbol="ETF基金")
    if df is None or df.empty:
        raise RuntimeError("Sina ETF list is empty, cannot build whitelist")

    df["代码"] = df["代码"].astype(str).str.replace(r"^(sh|sz)", "", regex=True)

    mask_bond = (
        df["代码"].str.match(r"^(51|52|53|56|58)")
        & df["名称"].str.contains("债", na=False)
    )
    df_filtered = df[~mask_bond]

    whitelist = set(df_filtered["代码"].astype(str))
    logger.info(f"ETF whitelist built: {len(whitelist)} codes (filtered {mask_bond.sum()} bond ETFs)")
    return whitelist


def get_existing_dates(start_str: str, end_str: str) -> set:
    """查询数据库中已有 SSE 数据的日期集合，用于跳过已完整采集的日期"""
    with Session(share_history_engine) as session:
        existing = session.exec(
            select(ETFShareHistory.date)
            .where(ETFShareHistory.date >= start_str)
            .where(ETFShareHistory.date <= end_str)
            .where(ETFShareHistory.exchange == "SSE")
            .distinct()
        ).all()
    return set(existing)


def fetch_sse_shares_for_date(date_str: str, whitelist: set) -> pd.DataFrame:
    """
    精确拉取指定日期的 SSE ETF 份额数据（最多重试 3 次）

    Returns:
        标准化 DataFrame（columns: code, shares, date, etf_type），
        非交易日或无数据返回空 DataFrame
    """
    for attempt in range(3):
        try:
            resp = requests.get(
                SSE_API_URL,
                params={
                    "sqlId": "COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L",
                    "STAT_DATE": date_str,
                },
                headers=SSE_HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            records = data.get("result", [])
            if not records:
                return pd.DataFrame()  # 非交易日，返回空

            # 校验响应结构
            if "SEC_CODE" not in records[0] or "TOT_VOL" not in records[0]:
                raise ValueError(f"SSE API response structure changed: keys={list(records[0].keys())}")

            df = pd.DataFrame(records)

            # 白名单过滤
            df = df[df["SEC_CODE"].astype(str).isin(whitelist)]
            if df.empty:
                return pd.DataFrame()

            # 标准化：TOT_VOL 单位为万份，÷1e4 转换为亿份
            result = pd.DataFrame({
                "code": df["SEC_CODE"].astype(str).values,
                "shares": pd.to_numeric(df["TOT_VOL"], errors="coerce") / 1e4,
                "date": df["STAT_DATE"].astype(str).values,
                "etf_type": df["ETF_TYPE"].astype(str).values if "ETF_TYPE" in df.columns else None,
            })
            return result

        except Exception as e:
            logger.warning(f"SSE fetch attempt {attempt + 1}/3 for {date_str} failed: {e}")
            if attempt < 2:
                time.sleep(3)

    raise RuntimeError(f"Failed to fetch SSE shares for {date_str} after 3 attempts")


def save_to_database(df: pd.DataFrame) -> tuple[int, int]:
    """
    保存数据到数据库，重复 (code, date) 记录自动跳过

    Returns:
        (新增条数, 跳过条数)
    """
    if df is None or df.empty:
        return 0, 0

    inserted = 0
    skipped = 0

    with Session(share_history_engine) as session:
        for _, row in df.iterrows():
            try:
                shares_val = float(row["shares"])
                if pd.isna(shares_val) or shares_val <= 0:
                    continue

                code = str(row["code"])
                exchange = "SZSE" if code.startswith(("15", "16", "12")) else "SSE"

                record = ETFShareHistory(
                    code=code,
                    date=str(row["date"]),
                    shares=shares_val,
                    exchange=exchange,
                    etf_type=str(row.get("etf_type", "")) if pd.notna(row.get("etf_type")) else None,
                )
                nested = session.begin_nested()
                session.add(record)
                nested.commit()
                inserted += 1
            except IntegrityError:
                nested.rollback()
                skipped += 1
            except Exception as e:
                logger.error(f"Failed to insert record {row.get('code')}: {e}")
                nested.rollback()

        session.commit()

    return inserted, skipped


def generate_weekdays(start: date, end: date) -> list[date]:
    """生成 start 到 end 之间所有工作日（跳过周六、周日）"""
    days = []
    d = start
    while d <= end:
        if d.weekday() < 5:  # 0=Mon, 4=Fri
            days.append(d)
        d += timedelta(days=1)
    return days


def main():
    parser = argparse.ArgumentParser(description="SSE ETF 份额历史补录脚本")
    parser.add_argument("--start", required=True, help="起始日期 YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="结束日期 YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="只打印目标日期，不实际写库")
    parser.add_argument("--delay", type=float, default=1.0, help="每次请求后的等待秒数（默认 1.0）")
    args = parser.parse_args()

    try:
        start_date = date.fromisoformat(args.start)
        end_date = date.fromisoformat(args.end)
    except ValueError as e:
        print(f"日期格式错误：{e}，请使用 YYYY-MM-DD 格式")
        sys.exit(1)

    if start_date > end_date:
        print(f"起始日期 {start_date} 不能晚于结束日期 {end_date}")
        sys.exit(1)

    # 生成工作日序列
    weekdays = generate_weekdays(start_date, end_date)
    logger.info(f"日期范围：{start_date} ~ {end_date}，工作日共 {len(weekdays)} 天")

    if args.dry_run:
        print(f"\n[dry-run] 将请求以下 {len(weekdays)} 个工作日：")
        for d in weekdays:
            print(f"  {d}")
        return

    # 构建 ETF 白名单
    whitelist = build_etf_whitelist()

    # 查询已有日期（跳过优化）
    existing_dates = get_existing_dates(args.start, args.end)
    logger.info(f"数据库中已有 {len(existing_dates)} 个日期的 SSE 数据，将跳过")

    # 统计
    total_days = len(weekdays)
    skipped_days = 0
    trading_days = 0
    total_inserted = 0
    total_skipped = 0
    failed_dates = []

    for i, d in enumerate(weekdays, 1):
        date_str = d.isoformat()

        if date_str in existing_dates:
            logger.info(f"[{i}/{total_days}] {date_str} — 已有数据，跳过")
            skipped_days += 1
            continue

        try:
            df = fetch_sse_shares_for_date(date_str, whitelist)

            if df.empty:
                logger.info(f"[{i}/{total_days}] {date_str} — 非交易日或无数据，跳过")
                skipped_days += 1
            else:
                inserted, skipped = save_to_database(df)
                trading_days += 1
                total_inserted += inserted
                total_skipped += skipped
                logger.info(
                    f"[{i}/{total_days}] {date_str} — "
                    f"新增 {inserted} 条，跳过 {skipped} 条（共 {len(df)} 条原始数据）"
                )

            if i < total_days:
                time.sleep(args.delay)

        except RuntimeError as e:
            logger.error(f"[{i}/{total_days}] {date_str} — 请求失败：{e}")
            failed_dates.append(date_str)

    # 最终汇总
    print("\n" + "=" * 60)
    print("补录完成汇总")
    print("=" * 60)
    print(f"  总工作日数：    {total_days}")
    print(f"  有效交易日数：  {trading_days}")
    print(f"  跳过日数：      {skipped_days}")
    print(f"  失败日数：      {len(failed_dates)}")
    print(f"  新增记录总数：  {total_inserted}")
    print(f"  重复跳过总数：  {total_skipped}")
    if failed_dates:
        print(f"\n  失败日期：")
        for d in failed_dates:
            print(f"    {d}")
    print("=" * 60)


if __name__ == "__main__":
    main()
