# ETF 指数映射脚本实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现一个 CLI 脚本，自动爬取 ETF 跟踪指数信息并生成映射表。

**Architecture:** 分层设计 —— 数据获取层（天天基金 HTML 爬取）、匹配层（指数名称模糊匹配）、存储层（JSON 三分区读写）。CLI 接口提供灵活的运行模式。

**Tech Stack:** Python, requests, BeautifulSoup4, AkShare, argparse

---

## Task 1: 创建骨架脚本和 JSON 读写模块

**Files:**
- Create: `backend/scripts/etf_index_mapper.py`

**Step 1: 创建脚本骨架**

```python
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
import sys
from datetime import date
from typing import Dict, List, Optional

# 数据文件路径
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "etf_index_map_new.json")


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
    
    # TODO: 实现处理逻辑
    print("[INFO] 脚本骨架运行成功")


if __name__ == "__main__":
    main()
```

**Step 2: 验证脚本可运行**

Run: `cd backend && python3 scripts/etf_index_mapper.py --help`
Expected: 显示帮助信息，无报错

**Step 3: Commit**

```bash
git add backend/scripts/etf_index_mapper.py
git commit -m "feat: add etf_index_mapper.py skeleton with JSON read/write"
```

---

## Task 2: 实现 --init 命令（获取全量 ETF 列表）

**Files:**
- Modify: `backend/scripts/etf_index_mapper.py`

**Step 1: 添加 ETF 列表获取函数**

在文件顶部导入区添加:
```python
import akshare as ak
import pandas as pd
```

在 `save_mapping` 函数后添加:
```python
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
```

**Step 2: 实现 --init 逻辑**

修改 `main()` 函数，在 `# TODO: 实现处理逻辑` 处添加:
```python
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
```

**Step 3: 验证 --init 功能**

Run: `cd backend && python3 scripts/etf_index_mapper.py --init --dry-run`
Expected: 显示获取到的 ETF 数量，不写入文件

**Step 4: Commit**

```bash
git add backend/scripts/etf_index_mapper.py
git commit -m "feat: implement --init command to fetch ETF list from AkShare"
```

---

## Task 3: 实现指数数据库加载和匹配逻辑

**Files:**
- Modify: `backend/scripts/etf_index_mapper.py`

**Step 1: 添加指数数据库加载函数**

在 `fetch_all_etf_codes` 函数后添加:
```python
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
```

**Step 2: 添加指数名称匹配函数**

```python
def match_index(source_name: str, index_db: pd.DataFrame) -> Optional[Dict]:
    """
    匹配指数名称到指数代码
    
    优先级:
    1. 精确匹配 index_name
    2. 去除「指数」后缀后匹配
    3. 模糊匹配简称
    
    代码优先级: 000xxx/399xxx > H3xxxx > 其他
    """
    if not source_name or pd.isna(source_name):
        return None
    
    source_clean = source_name.replace("指数", "").strip()
    
    # 精确匹配
    exact = index_db[index_db["index_name"] == source_name]
    if not exact.empty:
        return _select_best_match(exact)
    
    # 去除「指数」后匹配
    clean_match = index_db[index_db["index_name"] == source_clean]
    if not clean_match.empty:
        return _select_best_match(clean_match)
    
    # 包含匹配
    contains = index_db[index_db["index_name"].str.contains(source_clean, na=False)]
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
        "index_name": best["index_name"]
    }
```

**Step 3: 验证指数数据库加载**

Run: `cd backend && python3 -c "import akshare as ak; df = ak.index_stock_info(); print(df.columns.tolist()); print(len(df))"`
Expected: 显示列名和指数数量

**Step 4: Commit**

```bash
git add backend/scripts/etf_index_mapper.py
git commit -m "feat: add index database loading and fuzzy matching logic"
```

---

## Task 4: 实现天天基金 HTML 爬取

**Files:**
- Modify: `backend/scripts/etf_index_mapper.py`

**Step 1: 添加爬取相关导入和常量**

在文件顶部导入区添加:
```python
import random
import time
import requests
from bs4 import BeautifulSoup
```

在常量区添加:
```python
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

EASTMONEY_URL = "https://fundf10.eastmoney.com/jbgk_{code}.html"
REQUEST_DELAY = (5, 10)  # 请求间隔秒数范围
```

**Step 2: 实现爬取函数**

```python
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
```

**Step 3: 验证爬取函数（手动测试）**

Run: `cd backend && python3 -c "
import requests
from bs4 import BeautifulSoup
url = 'https://fundf10.eastmoney.com/jbgk_510300.html'
resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
print('Status:', resp.status_code)
soup = BeautifulSoup(resp.text, 'html.parser')
for th in soup.find_all('th'):
    if '跟踪标的' in th.get_text():
        td = th.find_next_sibling('td')
        print('跟踪标的:', td.get_text(strip=True) if td else 'None')
        break
"`
Expected: 显示 510300 的跟踪标的（沪深300指数）

**Step 4: Commit**

```bash
git add backend/scripts/etf_index_mapper.py
git commit -m "feat: implement eastmoney HTML scraping for tracking index"
```

---

## Task 5: 实现核心处理循环和分类逻辑

**Files:**
- Modify: `backend/scripts/etf_index_mapper.py`

**Step 1: 添加处理单个 ETF 的函数**

```python
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
```

**Step 2: 更新 main() 中的处理循环**

在 `print(f"[INFO] 本次将处理 {len(codes_to_process)} 个 ETF")` 后添加:
```python
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
```

**Step 3: 测试完整流程**

Run: `cd backend && python3 scripts/etf_index_mapper.py --codes 510300,159915 --dry-run`
Expected: 显示两个 ETF 的处理过程和匹配结果

**Step 4: Commit**

```bash
git add backend/scripts/etf_index_mapper.py
git commit -m "feat: implement main processing loop with classification logic"
```

---

## Task 6: 端到端验证

**Files:**
- None (验证任务)

**Step 1: 运行 --init 初始化**

Run: `cd backend && python3 scripts/etf_index_mapper.py --init`
Expected: 创建 `etf_index_map_new.json`，pending 列表填充完毕

**Step 2: 运行小批量处理**

Run: `cd backend && python3 scripts/etf_index_mapper.py --limit 5`
Expected: 处理 5 个 ETF，部分匹配成功

**Step 3: 检查输出文件格式**

Run: `cat backend/app/data/etf_index_map_new.json | head -50`
Expected: 符合设计的三分区 JSON 结构

**Step 4: Commit**

```bash
git add backend/app/data/etf_index_map_new.json
git commit -m "chore: add initial etf_index_map_new.json from mapper script"
```

---

## 验收标准

| 验收项 | 预期结果 |
|:--|:--|
| `--help` | 显示正确帮助信息 |
| `--init` | 获取 ETF 列表填充 pending |
| `--codes 510300,159915` | 正确匹配沪深300和创业板 |
| `--dry-run` | 不写入文件 |
| 输出 JSON | 符合三分区结构 |
| 跨境 ETF | 分类到 unmappable |
