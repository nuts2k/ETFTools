#!/usr/bin/env python3
"""
ETF 分类器全量覆盖率测试脚本

功能：
1. 通过 akshare 获取全量 ETF 列表
2. 逐一调用 ETFClassifier.classify() 进行分类
3. 输出统计报告：
   - 总覆盖率（有标签 / 总数）
   - 未分类 ETF 完整列表
   - 按分类标签分组的 ETF 数量统计
   - 只有 type 标签但无细分的 ETF 列表
"""

import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Dict, List

from app.services.etf_classifier import ETFClassifier


def fetch_all_etfs() -> List[Dict]:
    """
    获取全量 ETF 列表

    优先级：akshare 在线接口 → DiskCache 缓存 → fallback JSON
    """
    # 尝试 akshare 在线接口
    try:
        import akshare as ak
        print("正在从东方财富获取全量 ETF 列表...")
        df = ak.fund_etf_spot_em()
        records = []
        for _, row in df.iterrows():
            records.append({"code": row["代码"], "name": row["名称"]})
        print(f"[在线] 获取到 {len(records)} 只 ETF\n")
        return records
    except Exception as e:
        print(f"在线接口不可用: {e}")

    # 尝试 DiskCache
    try:
        from diskcache import Cache
        cache_dir = Path(__file__).parent.parent / ".cache"
        cache = Cache(str(cache_dir))
        cached = cache.get("etf_list_all")
        if cached and len(cached) > 20:
            records = [{"code": r["code"], "name": r["name"]} for r in cached]
            print(f"[缓存] 从 DiskCache 加载 {len(records)} 只 ETF\n")
            return records
    except Exception as e:
        print(f"DiskCache 不可用: {e}")

    # fallback JSON
    import json
    fallback_path = Path(__file__).parent.parent / "app" / "data" / "etf_fallback.json"
    with open(fallback_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    records = [{"code": r["code"], "name": r["name"]} for r in data]
    print(f"[离线] 从 fallback JSON 加载 {len(records)} 只 ETF\n")
    return records


def run_coverage_test():
    classifier = ETFClassifier()
    etf_list = fetch_all_etfs()

    # 分类所有 ETF
    classified = []      # 有标签的
    unclassified = []    # 无标签的
    type_only = []       # 只有 type 标签，无 industry/strategy 细分
    label_counter = Counter()          # 标签计数
    group_counter = Counter()          # 分组计数
    label_etfs = defaultdict(list)     # 标签 → ETF 列表

    start = time.perf_counter()

    for etf in etf_list:
        code, name = etf["code"], etf["name"]
        tags = classifier.classify(name, code)

        if not tags:
            unclassified.append(etf)
        else:
            classified.append({"code": code, "name": name, "tags": tags})
            groups = {t.group for t in tags}
            labels = [t.label for t in tags]

            for tag in tags:
                label_counter[tag.label] += 1
                group_counter[tag.group] += 1
                label_etfs[tag.label].append(f"{code} {name}")

            # 只有 type 标签，没有 industry/strategy 细分
            if groups == {"type"} or groups == {"type", "special"}:
                type_only.append({"code": code, "name": name, "labels": labels})

    duration = time.perf_counter() - start
    total = len(etf_list)

    # ========== 输出报告 ==========
    print("=" * 60)
    print("ETF 分类器全量覆盖率报告")
    print("=" * 60)

    # 1. 总览
    coverage = len(classified) / total * 100 if total else 0
    print(f"\n【总览】")
    print(f"  ETF 总数:    {total}")
    print(f"  已分类:      {len(classified)} ({coverage:.1f}%)")
    print(f"  未分类:      {len(unclassified)} ({100-coverage:.1f}%)")
    print(f"  分类耗时:    {duration*1000:.0f}ms ({duration/total*1000:.2f}ms/个)")

    # 2. 按标签分组统计
    print(f"\n【按标签统计】(共 {len(label_counter)} 个不同标签)")
    print(f"  {'标签':<12} {'数量':>6}  {'占比':>6}")
    print(f"  {'-'*30}")
    for label, count in label_counter.most_common():
        pct = count / total * 100
        print(f"  {label:<12} {count:>6}  {pct:>5.1f}%")

    # 3. 按 group 统计
    print(f"\n【按分组统计】")
    for group in ["type", "industry", "strategy", "special"]:
        count = group_counter.get(group, 0)
        print(f"  {group:<12} {count:>6} 个标签命中")

    # 4. 未分类 ETF 列表
    print(f"\n【未分类 ETF 列表】({len(unclassified)} 只)")
    print(f"  {'代码':<8} {'名称'}")
    print(f"  {'-'*40}")
    for etf in unclassified:
        print(f"  {etf['code']:<8} {etf['name']}")

    # 5. 只有 type 标签的 ETF（可能需要补充细分规则）
    print(f"\n【仅有大类标签，无细分】({len(type_only)} 只)")
    print(f"  {'代码':<8} {'名称':<20} {'标签'}")
    print(f"  {'-'*50}")
    for item in type_only:
        labels_str = ", ".join(item["labels"])
        print(f"  {item['code']:<8} {item['name']:<20} {labels_str}")

    print(f"\n{'=' * 60}")
    print("报告结束")


if __name__ == "__main__":
    run_coverage_test()
