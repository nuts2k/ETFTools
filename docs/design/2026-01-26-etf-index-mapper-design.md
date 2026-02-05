# ETF 指数自动映射脚本设计

## 1. 概述

### 目标
创建一个本地 Python 脚本，用于自动爬取 ETF 的跟踪指数信息，生成/更新映射表，支持估值分位功能。

### 背景
- 现有 `etf_index_map.json` 仅包含 12 条手工维护的映射
- 研究报告 `RESEARCH.md` 提出了「冷热分离的增量映射系统」方案
- 需要扩展映射覆盖范围，同时保持可维护性

### 核心决策
| 决策点 | 选择 | 理由 |
|:--|:--|:--|
| 运行形式 | 纯本地脚本 | 轻量灵活，手动触发或 cron 执行 |
| 数据源 | 天天基金 fundf10 | HTML 页面稳定性最高 |
| 数据结构 | 单文件三分区 | 简化管理，状态清晰 |
| 运行模式 | 单次执行 + 手动审核 | 先跑通流程，人工确认结果 |

## 2. 架构设计

### 核心流程
```
ETF 代码列表 → 天天基金 HTML 爬取 → 提取「跟踪标的」 
                                         ↓
                              模糊匹配指数代码（AKShare index_stock_info）
                                         ↓
                              输出 JSON 结果 → 人工审核 → 合并到映射表
```

### 文件结构
```
backend/
├── scripts/
│   └── etf_index_mapper.py    # 主脚本
└── app/data/
    ├── etf_index_map.json     # 现有文件，保持不变
    └── etf_index_map_new.json # 脚本输出的新文件
```

### 新 JSON 数据结构
```json
{
  "mapped": {
    "510300": {
      "index_code": "000300",
      "index_name": "沪深300",
      "source_name": "沪深300指数",
      "updated_at": "2026-01-26"
    }
  },
  "unmappable": {
    "513100": {
      "reason": "跨境ETF(纳指)",
      "source_name": "纳斯达克100指数",
      "updated_at": "2026-01-26"
    }
  },
  "pending": ["159915", "588000"]
}
```

## 3. 爬取逻辑

### 数据源
- URL: `https://fundf10.eastmoney.com/jbgk_{etf_code}.html`
- 目标字段: 表格中的「跟踪标的」行

### 爬取策略
1. **请求配置**
   - 随机 User-Agent 模拟浏览器
   - 请求间隔: 5-10 秒随机延迟（防封禁）
   - 超时: 10 秒

2. **HTML 解析**
   - 使用 `BeautifulSoup` 解析页面
   - 定位 `<th>` 包含「跟踪标的」的行
   - 提取对应 `<td>` 中的指数名称

3. **指数名称匹配**
   - 调用 `ak.index_stock_info()` 获取全量指数列表（预先缓存）
   - 匹配优先级:
     1. 精确匹配 `index_name`
     2. 去除「指数」后缀后匹配
     3. 模糊匹配简称
   - 代码优先级: `000xxx`/`399xxx` > `H3xxxx` > 其他

4. **分类规则**
   - 匹配成功 → `mapped`
   - 跟踪标的为空/主动管理型 → `unmappable`（标注原因）
   - 有跟踪标的但匹配失败 → 保留在 `pending`

## 4. CLI 接口

### 命令行参数
```bash
# 基本用法：处理 pending 列表中的 ETF
python scripts/etf_index_mapper.py

# 指定 ETF 代码（逗号分隔）
python scripts/etf_index_mapper.py --codes 510300,159915,588000

# 从 AKShare 获取全量 ETF 列表，填充 pending
python scripts/etf_index_mapper.py --init

# 只输出结果，不写入文件（dry-run）
python scripts/etf_index_mapper.py --dry-run

# 限制本次处理数量
python scripts/etf_index_mapper.py --limit 20
```

### 输出示例
```
[INFO] Loading index database from AKShare...
[INFO] Loaded 5832 indices

[1/20] 510300 沪深300ETF
  → 跟踪标的: 沪深300指数
  → 匹配结果: 000300 (沪深300) ✓ MAPPED

[2/20] 159915 创业板ETF  
  → 跟踪标的: 创业板指数
  → 匹配结果: 399006 (创业板指) ✓ MAPPED

[3/20] 513100 纳指ETF
  → 跟踪标的: 纳斯达克100指数
  → 匹配结果: 无匹配 (跨境指数) → UNMAPPABLE

[4/20] 512480 半导体ETF
  → 跟踪标的: 中证全指半导体产品与设备指数
  → 匹配结果: 无精确匹配，候选: H30184 (中证全指半导体) ? PENDING

========== 执行摘要 ==========
成功匹配: 12
无法匹配: 3  
待人工确认: 5
```

## 5. 依赖与错误处理

### 依赖库
- `requests` - HTTP 请求
- `beautifulsoup4` - HTML 解析
- `akshare` - 获取指数列表
- `pandas` - 数据处理（akshare 依赖）

### 错误处理策略
| 场景 | 处理方式 |
|:--|:--|
| HTTP 请求失败 (4xx/5xx) | 记录日志，跳过该 ETF，保留在 pending |
| 页面结构变化（找不到跟踪标的） | 记录警告，标记为 pending 待人工检查 |
| 指数匹配失败 | 输出候选列表，标记为 pending |
| 网络超时 | 重试 1 次，仍失败则跳过 |
| AKShare 指数列表获取失败 | 终止脚本，提示用户检查网络 |

## 6. 后续步骤

设计完成后的实现任务：

1. 创建 `backend/scripts/` 目录
2. 实现指数数据库加载（AKShare 接口）
3. 实现天天基金 HTML 爬取与解析
4. 实现指数名称匹配逻辑
5. 实现 JSON 三分区读写
6. 实现 CLI 参数解析
7. 测试运行验证

## 7. 迁移计划（暂缓）

> 注：以下内容待脚本开发完成后再处理

- 将 `etf_index_map_new.json` 中的 `mapped` 数据迁移到生产使用
- 修改 `valuation_service.py` 以支持新数据结构
- 保持向后兼容
