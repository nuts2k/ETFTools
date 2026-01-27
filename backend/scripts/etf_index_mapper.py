#!/usr/bin/env python3
"""
ETF 指数自动映射脚本

用法:
    python scripts/etf_index_mapper.py --codes 510300,159915
    python scripts/etf_index_mapper.py --init --limit 20
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import date
from typing import Dict, List, Optional

import akshare as ak
import pandas as pd
import requests
from bs4 import BeautifulSoup

# 数据文件路径
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "etf_index_map_new.json")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

EASTMONEY_URL = "https://fundf10.eastmoney.com/jbgk_{code}.html"
REQUEST_DELAY = (5, 10)  # 请求间隔秒数范围


def load_mapping() -> Dict:
    """加载现有映射文件，如不存在则返回初始结构"""
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"mapped": {}, "unmappable": {}, "pending": []}


def save_mapping(data: Dict) -> None:
    """保存映射文件"""
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[INFO] 已保存到 {OUTPUT_FILE}")


def fetch_all_etf_codes() -> List[str]:
    """从 AKShare 获取全量 ETF 代码列表"""
    print("[INFO] 正在从 AKShare 获取 ETF 列表...")
    try:
        df = ak.fund_etf_spot_em()
        codes = df["代码"].tolist()
        print(f"[INFO] 获取到 {len(codes)} 只 ETF")
        return codes
    except Exception as e:
        print(f"[ERROR] 获取 ETF 列表失败: {e}")
        sys.exit(1)


def load_index_database() -> pd.DataFrame:
    """加载全量指数列表用于匹配"""
    print("[INFO] 正在从 AKShare 加载指数数据库...")
    try:
        df = ak.index_stock_info()
        print(f"[INFO] 加载 {len(df)} 条指数数据")
        return df
    except Exception as e:
        print(f"[ERROR] 加载指数数据库失败: {e}")
        sys.exit(1)


def fetch_tracking_index(etf_code: str, max_retries: int = 1) -> Optional[str]:
    """
    从天天基金爬取 ETF 的跟踪标的名称
    
    Returns:
        跟踪标的名称，如未找到返回 None
    """
    url = EASTMONEY_URL.format(code=etf_code)
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # 查找包含「跟踪标的」的行
            for th in soup.find_all("th"):
                if "跟踪标的" in th.get_text():
                    td = th.find_next_sibling("td")
                    if td:
                        # 提取文本，清理空白
                        text = td.get_text(strip=True)
                        # 有时候是链接，只取文本
                        if text and text != "--":
                            return text
            
            return None
            
        except requests.RequestException as e:
            if attempt < max_retries:
                print(f"  [WARN] 请求失败，重试中... ({e})")
                time.sleep(2)
            else:
                print(f"  [WARN] 请求失败: {e}")
                return None
        except Exception as e:
            print(f"  [WARN] 解析失败: {e}")
            return None
    
    return None


def match_index(source_name: str, index_db: pd.DataFrame) -> Optional[Dict]:
    """
    匹配指数名称到指数代码
    
    优先级:
    1. 精确匹配 display_name
    2. 去除「指数」后缀后匹配
    3. 模糊匹配简称
    
    代码优先级: 000xxx/399xxx > H3xxxx > 其他
    """
    if not source_name or pd.isna(source_name):
        return None
    
    source_clean = source_name.replace("指数", "").strip()
    
    # 精确匹配
    exact = index_db[index_db["display_name"] == source_name]
    if not exact.empty:
        return _select_best_match(exact)
    
    # 去除「指数」后匹配
    clean_match = index_db[index_db["display_name"] == source_clean]
    if not clean_match.empty:
        return _select_best_match(clean_match)
    
    # 包含匹配
    contains = index_db[index_db["display_name"].str.contains(source_clean, na=False)]
    if not contains.empty:
        return _select_best_match(contains)
    
    return None


def _select_best_match(df: pd.DataFrame) -> Dict:
    """从多个候选中选择最佳匹配（按代码优先级）"""
    def priority(code: str) -> int:
        if code.startswith(("000", "399")):
            return 0
        if code.startswith("H3"):
            return 1
        return 2
    
    df = df.copy()
    df["priority"] = df["index_code"].apply(priority)
    best = df.sort_values("priority").iloc[0]
    return {
        "index_code": best["index_code"],
        "index_name": best["display_name"]
    }


def process_etf(
    etf_code: str, 
    index_db: pd.DataFrame,
    data: Dict
) -> str:
    """
    处理单个 ETF，返回处理结果类型: MAPPED / UNMAPPABLE / PENDING
    """
    today = date.today().isoformat()
    
    # 爬取跟踪标的
    source_name = fetch_tracking_index(etf_code)
    
    if not source_name:
        # 无跟踪标的 -> 可能是主动管理型基金
        data["unmappable"][etf_code] = {
            "reason": "无跟踪标的（主动管理型/LOF）",
            "source_name": None,
            "updated_at": today
        }
        return "UNMAPPABLE"
    
    print(f"  → 跟踪标的: {source_name}")
    
    # 检测跨境 ETF
    cross_border_keywords = ["纳斯达克", "标普", "恒生", "道琼斯", "日经", "法兰克福", "纳指", "美股"]
    if any(kw in source_name for kw in cross_border_keywords):
        data["unmappable"][etf_code] = {
            "reason": "跨境ETF",
            "source_name": source_name,
            "updated_at": today
        }
        return "UNMAPPABLE"
    
    # 匹配指数
    match = match_index(source_name, index_db)
    
    if match:
        data["mapped"][etf_code] = {
            "index_code": match["index_code"],
            "index_name": match["index_name"],
            "source_name": source_name,
            "updated_at": today
        }
        print(f"  → 匹配结果: {match['index_code']} ({match['index_name']}) ✓")
        return "MAPPED"
    else:
        # 匹配失败，保留在 pending
        if etf_code not in data["pending"]:
            data["pending"].append(etf_code)
        print(f"  → 匹配结果: 无精确匹配 → PENDING")
        return "PENDING"


def main():
    parser = argparse.ArgumentParser(description="ETF 指数自动映射脚本")
    parser.add_argument("--codes", type=str, help="指定 ETF 代码（逗号分隔）")
    parser.add_argument("--init", action="store_true", help="从 AKShare 获取全量 ETF 列表")
    parser.add_argument("--dry-run", action="store_true", help="只输出结果，不写入文件")
    parser.add_argument("--limit", type=int, default=20, help="限制本次处理数量")
    
    args = parser.parse_args()
    
    # 加载现有数据
    data = load_mapping()
    print(f"[INFO] 已加载映射文件: mapped={len(data['mapped'])}, pending={len(data['pending'])}")
    
    # 确定要处理的 ETF 列表
    if args.init:
        all_codes = fetch_all_etf_codes()
        # 排除已处理的
        existing = set(data["mapped"].keys()) | set(data["unmappable"].keys())
        new_codes = [c for c in all_codes if c not in existing]
        data["pending"] = list(set(data["pending"]) | set(new_codes))
        print(f"[INFO] 新增 {len(new_codes)} 个待处理 ETF 到 pending")
        if not args.dry_run:
            save_mapping(data)
        return
    
    if args.codes:
        codes_to_process = [c.strip() for c in args.codes.split(",")]
    else:
        codes_to_process = data["pending"][:args.limit]
    
    if not codes_to_process:
        print("[INFO] 无待处理 ETF")
        return
    
    print(f"[INFO] 本次将处理 {len(codes_to_process)} 个 ETF")

    # 加载指数数据库
    index_db = load_index_database()
    
    # 统计
    stats = {"MAPPED": 0, "UNMAPPABLE": 0, "PENDING": 0}
    
    # 处理循环
    for i, code in enumerate(codes_to_process, 1):
        print(f"\n[{i}/{len(codes_to_process)}] {code}")
        
        result = process_etf(code, index_db, data)
        stats[result] += 1
        
        # 从 pending 中移除已处理的
        if code in data["pending"] and result != "PENDING":
            data["pending"].remove(code)
        
        # 请求间隔
        if i < len(codes_to_process):
            delay = random.uniform(*REQUEST_DELAY)
            print(f"  [等待 {delay:.1f}s]")
            time.sleep(delay)
    
    # 输出摘要
    print("\n" + "=" * 40)
    print("执行摘要")
    print("=" * 40)
    print(f"成功匹配: {stats['MAPPED']}")
    print(f"无法匹配: {stats['UNMAPPABLE']}")
    print(f"待人工确认: {stats['PENDING']}")
    
    # 保存
    if not args.dry_run:
        save_mapping(data)


if __name__ == "__main__":
    main()
