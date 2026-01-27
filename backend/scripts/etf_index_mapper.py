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
import re
import sys
import time
from datetime import date
from typing import Dict, List, Optional, Tuple

import akshare as ak
import pandas as pd
import requests
from bs4 import BeautifulSoup

# 数据文件路径
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "etf_index_map_new.json")
INDEX_DB_FILE = os.path.join(DATA_DIR, "index_database.json")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

EASTMONEY_URL = "https://fundf10.eastmoney.com/jbgk_{code}.html"
REQUEST_DELAY = (5, 10)  # 请求间隔秒数范围

# 跨境指数名称映射：ETF跟踪标的名称 -> 数据源名称
# 用于处理 ETF 公示名称与数据源名称的差异
CROSS_BORDER_NAME_MAP = {
    # 日本
    "东京日经225指数": "日经225指数",
    # 美国（多种表述统一）
    "纳斯达克100": "纳斯达克100指数",
    "标普500": "标普500指数",
    "标准普尔500指数": "标普500指数",  # 全称 -> 简称
    "道琼斯工业平均": "道琼斯工业平均指数",
}


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
        f.write("\n")  # 添加尾部换行
    print(f"[INFO] 已保存到 {OUTPUT_FILE}")


def fetch_all_etf_codes() -> List[str]:
    """从主应用服务获取全量 ETF 代码列表（复用完善的 fallback 机制）"""
    print("[INFO] 正在从主应用服务获取 ETF 列表...")
    try:
        # 将 backend/ 添加到路径以支持 app 模块导入
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from app.services.akshare_service import AkShareService
        etf_list = AkShareService.fetch_all_etfs()
        codes = [etf["code"] for etf in etf_list]
        print(f"[INFO] 获取到 {len(codes)} 只 ETF")
        return codes
    except Exception as e:
        print(f"[ERROR] 获取 ETF 列表失败: {e}")
        sys.exit(1)


def load_index_database() -> pd.DataFrame:
    """从本地 JSON 加载指数数据库"""
    if not os.path.exists(INDEX_DB_FILE):
        print(f"[ERROR] 指数数据库不存在: {INDEX_DB_FILE}")
        print("[INFO] 请先运行: python scripts/etf_index_mapper.py --update-index-db")
        sys.exit(1)
    
    print(f"[INFO] 正在从本地加载指数数据库...")
    with open(INDEX_DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    df = pd.DataFrame(data)
    print(f"[INFO] 已加载 {len(df)} 条指数")
    return df


def fetch_chinabond_indices() -> List[Dict]:
    """从中债网站获取全量中债指数列表"""
    url = "https://yield.chinabond.com.cn/cbweb-mn/indices/queryTree"
    params = {"locale": "zh_CN"}
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        # 只保留叶子节点（实际指数，非分类）
        indices = []
        for item in data:
            if item.get("isParent") == "false":
                indices.append({
                    "index_code": item["id"],  # UUID 格式
                    "display_name": item["name"]
                })
        return indices
    except Exception as e:
        print(f"  - 中债指数获取失败: {e}")
        return []


def update_index_database() -> None:
    """从 AkShare 和中债网站获取全量指数并保存到本地 JSON"""
    print("[INFO] 正在更新指数数据库...")
    frames = []
    
    # 1. 上证/深证基础指数
    try:
        df1 = ak.index_stock_info()[['index_code', 'display_name']]
        frames.append(df1)
        print(f"  - index_stock_info: {len(df1)} 条")
    except Exception as e:
        print(f"  - index_stock_info 失败: {e}")
    
    # 2. 中证全量指数（使用全称匹配）
    try:
        df2 = ak.index_csindex_all()[['指数代码', '指数全称']]
        df2.columns = ['index_code', 'display_name']
        frames.append(df2)
        print(f"  - index_csindex_all: {len(df2)} 条")
    except Exception as e:
        print(f"  - index_csindex_all 失败: {e}")
    
    # 3. 国证指数
    try:
        df3 = ak.index_all_cni()[['指数代码', '指数简称']]
        df3.columns = ['index_code', 'display_name']
        frames.append(df3)
        print(f"  - index_all_cni: {len(df3)} 条")
    except Exception as e:
        print(f"  - index_all_cni 失败: {e}")
    
    # 4. 中债指数（从中债网站获取）
    try:
        chinabond_indices = fetch_chinabond_indices()
        if chinabond_indices:
            df4 = pd.DataFrame(chinabond_indices)
            frames.append(df4)
            print(f"  - chinabond (中债): {len(df4)} 条")
    except Exception as e:
        print(f"  - chinabond 失败: {e}")
    
    # 5. 新浪港股指数（恒生系列）
    try:
        df5 = ak.stock_hk_index_spot_sina()[['代码', '名称']]
        df5.columns = ['index_code', 'display_name']
        frames.append(df5)
        print(f"  - stock_hk_index_spot_sina (港股): {len(df5)} 条")
    except Exception as e:
        print(f"  - stock_hk_index_spot_sina 失败: {e}")
    
    # 6. 新浪全球指数（日经225等）
    try:
        df6 = ak.index_global_name_table()[['代码', '指数名称']]
        df6.columns = ['index_code', 'display_name']
        frames.append(df6)
        print(f"  - index_global_name_table (全球): {len(df6)} 条")
    except Exception as e:
        print(f"  - index_global_name_table 失败: {e}")
    
    # 7. 新浪美股主要指数（手动定义，AkShare 无直接接口）
    us_indices = [
        {"index_code": ".NDX", "display_name": "纳斯达克100指数"},
        {"index_code": ".IXIC", "display_name": "纳斯达克综合指数"},
        {"index_code": ".DJI", "display_name": "道琼斯工业平均指数"},
        {"index_code": ".INX", "display_name": "标普500指数"},
    ]
    df7 = pd.DataFrame(us_indices)
    frames.append(df7)
    print(f"  - 美股指数 (手动): {len(df7)} 条")
    
    if not frames:
        print("[ERROR] 所有指数数据源均失败")
        sys.exit(1)
    
    merged = pd.concat(frames, ignore_index=True)
    merged = merged.drop_duplicates(subset='index_code', keep='first')
    print(f"[INFO] 合并去重后共 {len(merged)} 条指数")
    
    # 保存到 JSON
    records = merged.to_dict(orient="records")
    with open(INDEX_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[INFO] 已保存到 {INDEX_DB_FILE}")


def fetch_tracking_index(etf_code: str, max_retries: int = 1) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    从天天基金爬取 ETF 的跟踪标的名称、简称和业绩比较基准指数名称
    
    Returns:
        (跟踪标的名称, 简称, 业绩比较基准指数名称)
    """
    url = EASTMONEY_URL.format(code=etf_code)
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            tracking_name = None
            short_name = None
            benchmark_index = None
            
            # 遍历所有 th 提取信息
            for th in soup.find_all("th"):
                th_text = th.get_text()
                td = th.find_next_sibling("td")
                if not td:
                    continue
                td_text = td.get_text(strip=True)
                
                # 提取跟踪标的
                if "跟踪标的" in th_text:
                    if td_text and td_text != "--" and "无跟踪标的" not in td_text:
                        tracking_name = td_text
                
                # 从业绩比较基准提取信息
                if "业绩比较基准" in th_text:
                    # 提取简称
                    match = re.search(r'简称[:：]([^)）]+)[)）]', td_text)
                    if match:
                        short_name = match.group(1)
                    # 提取指数名称（去掉「收益率」后缀）
                    if "收益率" in td_text:
                        benchmark_index = td_text.split("收益率")[0].strip()
            
            return (tracking_name, short_name, benchmark_index)
            
        except requests.RequestException as e:
            if attempt < max_retries:
                print(f"  [WARN] 请求失败，重试中... ({e})")
                time.sleep(2)
            else:
                print(f"  [WARN] 请求失败: {e}")
                return (None, None, None)
        except Exception as e:
            print(f"  [WARN] 解析失败: {e}")
            return (None, None, None)
    
    return (None, None, None)


def match_index(source_name: str, index_db: pd.DataFrame) -> Optional[Dict]:
    """
    匹配指数名称到指数代码
    
    优先级:
    0. 跨境名称映射（ETF名称 -> 数据源名称）
    1. 精确匹配 display_name
    2. 去除「指数」后缀后匹配
    3. 中债指数特殊处理（去除财富/全价/净价等后缀）
    4. 包含匹配
    5. 去除通用词后模糊匹配
    
    代码优先级: 000xxx/399xxx > H3xxxx > 其他
    """
    if not source_name or pd.isna(source_name):
        return None
    
    # 0. 跨境名称映射
    mapped_name = CROSS_BORDER_NAME_MAP.get(source_name)
    if mapped_name:
        source_name = mapped_name
    
    # 清理源名称：去除括号及其内容、去除「指数」后缀
    source_clean = re.sub(r'\([^)]*\)', '', source_name)  # 去除 (价格) 等
    source_clean = source_clean.replace("指数", "").strip()
    
    # 中债指数特殊处理：去除「财富/全价/净价(总值)指数」等后缀
    # 例如: 中债-30年期国债财富(总值)指数 -> 中债-30年期国债指数
    chinabond_clean = re.sub(r'(财富|全价|净价)?\(?总值\)?指数$', '指数', source_name)
    
    # 空字符串检查，避免 str.contains("") 匹配所有行
    if not source_clean:
        return None
    
    # 1. 精确匹配
    exact = index_db[index_db["display_name"] == source_name]
    if not exact.empty:
        return _select_best_match(exact)
    
    # 2. 去除「指数」后匹配
    clean_match = index_db[index_db["display_name"] == source_clean]
    if not clean_match.empty:
        return _select_best_match(clean_match)
    
    # 3. 中债指数特殊匹配（去除财富/全价/净价等后缀后精确匹配）
    if chinabond_clean != source_name:
        chinabond_match = index_db[index_db["display_name"] == chinabond_clean]
        if not chinabond_match.empty:
            return _select_best_match(chinabond_match)
    
    # 4. 包含匹配（使用 regex=False 避免警告）
    contains = index_db[index_db["display_name"].str.contains(source_clean, na=False, regex=False)]
    if not contains.empty:
        return _select_best_match(contains)
    
    # 5. 去除通用词后模糊匹配
    common_words = ["中证", "中国", "国证", "上证", "深证", "板"]
    source_fuzzy = source_clean
    for word in common_words:
        source_fuzzy = source_fuzzy.replace(word, "")
    source_fuzzy = source_fuzzy.strip()
    
    if source_fuzzy and len(source_fuzzy) >= 2:
        # 在数据库名称中搜索包含关键词的记录
        fuzzy_match = index_db[index_db["display_name"].str.contains(source_fuzzy, na=False, regex=False)]
        if not fuzzy_match.empty:
            return _select_best_match(fuzzy_match)
    
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
    
    # 爬取跟踪标的、简称和业绩比较基准指数名称
    source_name, short_name, benchmark_index = fetch_tracking_index(etf_code)
    
    if not source_name:
        # 无跟踪标的 -> 可能是主动管理型基金/REITs
        print(f"  → 无跟踪标的")
        print(f"  → 匹配结果: 主动管理型/LOF/REITs → UNMAPPABLE")
        data["unmappable"][etf_code] = {
            "reason": "无跟踪标的（主动管理型/LOF/REITs）",
            "source_name": None,
            "updated_at": today
        }
        return "UNMAPPABLE"
    
    print(f"  → 跟踪标的: {source_name}" + (f" (简称: {short_name})" if short_name else ""))
    
    # 检测无法匹配的跨境指数（仅 MSCI 系列，其他跨境指数已有数据源）
    # 注意: 纳斯达克、标普、恒生、道琼斯、日经等已整合数据源，不再标记为 UNMAPPABLE
    unmappable_keywords = ["MSCI", "法兰克福"]
    if any(kw in source_name for kw in unmappable_keywords):
        print(f"  → 匹配结果: {source_name} (无公开数据源) → UNMAPPABLE")
        data["unmappable"][etf_code] = {
            "reason": "无公开数据源",
            "source_name": source_name,
            "updated_at": today
        }
        return "UNMAPPABLE"
    
    # 匹配指数：先用全称，失败后用简称，再失败用业绩比较基准
    match = match_index(source_name, index_db)
    if not match and short_name:
        match = match_index(short_name, index_db)
    if not match and benchmark_index:
        match = match_index(benchmark_index, index_db)
    
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
    parser.add_argument("--update-index-db", action="store_true", help="更新本地指数数据库")
    parser.add_argument("--dry-run", action="store_true", help="只输出结果，不写入文件")
    parser.add_argument("--limit", type=int, default=20, help="限制本次处理数量")
    
    args = parser.parse_args()
    
    # 更新指数数据库
    if args.update_index_db:
        update_index_database()
        return
    
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
