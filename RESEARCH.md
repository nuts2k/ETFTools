# ETF 估值数据获取与计算方案研究报告

## 1. 核心结论 (Executive Summary)

*   **可行性**：通过 AKShare 免费接口获取 ETF 估值是**高度可行**的。
*   **最佳路径**：不直接获取 ETF 的 PE，而是建立 **“ETF -> 跟踪指数 -> 指数历史估值”** 的数据链路。
*   **数据源**：中证指数有限公司（CSIndex）官方数据是质量最高、最稳定的免费来源，覆盖了 A 股绝大多数主流宽基和行业指数。
*   **局限性**：跨境 ETF（如纳指、标普）和部分非中证系指数（如国证指数）的数据获取难度较大，需特殊处理。

## 2. 技术实现方案 (Technical Solution)

### 2.1 数据链路架构

1.  **映射层 (Mapping)**：通过天天基金网（`fundf10`）或雪球数据，将 ETF 代码（如 `512480`）映射到其跟踪的指数名称（如“中证全指半导体”）。
2.  **转换层 (Translation)**：将指数名称转换为指数代码（如 `H30184`）。推荐使用本地维护的字典或 AKShare 的 `index_stock_info` 接口辅助。
3.  **数据层 (Data Fetching)**：使用 `ak.stock_zh_index_hist_csindex(symbol=index_code)` 获取历史 PE-TTM 序列。
4.  **计算层 (Calculation)**：基于 Pandas 对历史序列进行分位数计算 (`rank(pct=True)`)。

### 2.2 核心接口清单

| 步骤 | 功能描述 | 推荐接口/方法 | 稳定性 | 备注 |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **获取 ETF 跟踪标的** | `requests.get('fundf10.eastmoney.com/jbgk_{code}.html')` | ⭐⭐⭐⭐⭐ | 网页解析比 API 更稳，直接提取 `跟踪标的` 字段 |
| **2** | **获取指数信息表** | `ak.index_stock_info()` | ⭐⭐⭐⭐ | 用于模糊匹配指数名称获取代码 |
| **3** | **获取中证指数历史 PE** | `ak.stock_zh_index_hist_csindex(symbol)` | ⭐⭐⭐⭐⭐ | **核心接口**，数据源自中证官网，含 PE-TTM, PB, 股息率 |
| **4** | **获取国证指数历史 PE** | `ak.stock_index_pe_lg(symbol)` | ⭐⭐⭐ | 备用方案，用于创业板指等非中证指数 |

## 3. 估值百分位计算逻辑

```python
# 伪代码示例
def calculate_percentile(history_df, window_years=5):
    # 1. 提取 PE-TTM 序列，清洗空值
    pe_series = history_df['滚动市盈率'].dropna()
    
    # 2. 截取时间窗口 (如近5年)
    cutoff_date = pd.Timestamp.now() - pd.DateOffset(years=window_years)
    window_data = pe_series[history_df['日期'] >= cutoff_date]
    
    # 3. 计算当前值在历史分布中的百分位
    current_pe = window_data.iloc[-1]
    percentile = (window_data < current_pe).mean() * 100
    
    return percentile, current_pe
```

## 4. 自动化映射系统设计 (Auto-Mapping System)

为解决手动维护映射表的痛点，建立“冷热分离的增量映射系统”：

### 4.1 数据结构
在本地 `backend/app/data/etf_index_map.json` 维护三种状态：
*   **`mapped`**: 确定的映射（如 `510300 -> 000300`）。
*   **`unmappable`**: 确认无法映射的（如主动增强型、无标的基金），直接跳过后续爬取。
*   **`pending`**: 尚未尝试爬取的代码池。

### 4.2 爬取策略
*   **触发机制**: 每日低峰期（如凌晨）执行一次。
*   **小批量**: 每次仅处理 10 个 `pending` 中的代码，防止 IP 封禁。
*   **慢爬**: 请求间隔 10-20 秒，使用随机 User-Agent。
*   **判弃逻辑**:
    *   若“跟踪标的”为空 -> 移入 `unmappable`。
    *   若连续 3 次无法匹配有效指数代码 -> 移入 `unmappable`。

## 5. 已知问题与对策 (Issues & Mitigations)

### 5.1 指数代码匹配难点
*   **问题**：基金公告中的指数名称（如“中证全指半导体产品与设备指数”）与数据源名称（如“800半导”）可能不完全一致。
*   **对策**：
    *   优先匹配中证代码（`000` 或 `H3` 开头）。
    *   建立一个 `Alias Table`（别名表）处理常见热门行业。

### 5.2 数据源覆盖不全
*   **问题**：`stock_zh_index_hist_csindex` 仅覆盖中证系指数。创业板指（399006）属于深证/国证系列，无法通过此接口获取。
*   **对策**：对创业板指等特殊指数，降级使用 `ak.stock_index_pe_lg`（乐咕接口）或仅提供价格分位数作为参考。

### 5.3 跨境 ETF
*   **问题**：美股/港股指数缺乏免费且长周期的历史 PE 数据源。
*   **对策**：对于 513100 (纳指ETF) 等，建议暂不支持 PE 百分位，或仅接入简单的实时 PE 展示。

## 6. 下一步建议 (Next Steps)

1.  **构建映射库**：编写脚本批量爬取主流 Top 50 ETF 的跟踪指数，生成本地 `etf_index_map.json`。
2.  **开发原型工具**：实现一个 CLI 工具，输入 ETF 代码，输出当前估值红绿灯。
