#!/usr/bin/env python3
"""
ETF 分类器全量验证脚本

功能：
1. 从 fallback JSON 获取全量 ETF 列表
2. 对每个 ETF 进行分类
3. 输出分类结果到 CSV 文件
4. 统计性能指标
"""

import csv
import json
import sys
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.etf_classifier import ETFClassifier


def load_etf_list() -> list:
    """从 fallback JSON 加载 ETF 列表"""
    fallback_path = (
        Path(__file__).parent.parent / "app" / "data" / "etf_fallback.json"
    )
    with open(fallback_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    classifier = ETFClassifier()

    # 获取 ETF 列表
    print("正在加载 ETF 列表...")
    etf_list = load_etf_list()
    print(f"共 {len(etf_list)} 只 ETF")

    # 分类
    results = []
    start_time = time.perf_counter()

    for etf in etf_list:
        code = etf.get("code", "")
        name = etf.get("name", "")
        tags = classifier.classify(name, code)
        results.append({
            "code": code,
            "name": name,
            "tags": " | ".join(
                f"{t.label}({t.group})" for t in tags
            ),
        })

    duration = time.perf_counter() - start_time

    # 保存结果
    output_dir = Path(__file__).parent.parent / "data"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "classification_results.csv"

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["code", "name", "tags"])
        writer.writeheader()
        writer.writerows(results)

    # 统计
    tagged = sum(1 for r in results if r["tags"])
    untagged = len(results) - tagged

    print(f"\n分类完成！")
    print(f"结果已保存到: {output_file}")
    print(f"总计 ETF 数量: {len(etf_list)}")
    print(f"已分类: {tagged}, 未分类: {untagged}")
    print(f"分类耗时: {duration * 1000:.0f}ms")
    print(f"平均耗时: {duration / len(etf_list) * 1000:.2f}ms/个")

    if duration > 0.5:
        print(f"⚠️  警告：分类耗时超过 500ms")
    else:
        print(f"✅ 性能达标（< 500ms）")


if __name__ == "__main__":
    main()
