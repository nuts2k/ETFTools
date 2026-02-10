# ETF 自动分类功能 - 阶段0实施计划

## 1. 背景与目标 (Context)

### 1.1 为什么需要这个功能？

根据设计文档 `docs/design/2026-02-10-etf-auto-classification-design.md`，ETF 自动分类功能旨在解决以下核心痛点：

- **信息过载**：A股市场有数百只 ETF，用户难以快速筛选和发现感兴趣的品种
- **认知成本高**：新手用户不了解 ETF 的行业、主题、风格分类
- **搜索效率低**：当前只能通过代码/名称搜索，缺乏分类浏览和筛选能力

### 1.2 阶段0的目标

**核心目标**：在不修改任何现有代码的情况下，独立验证分类规则的质量。

**为什么要独立验证？**
- 分类准确率是整个功能的基石，必须先验证规则质量
- 避免将未验证的规则集成到生产代码中
- 便于快速迭代和调整规则，无需担心影响现有功能
- 为后续阶段提供可靠的分类器基础

### 1.3 验收标准

- ✅ 验证矩阵全部 31 个用例通过
- ✅ 全量 ETF 分类准确率 ≥ 85%
- ✅ 全量分类性能 < 500ms（约500个ETF）

---

## 2. 技术方案设计

### 2.1 分类器架构

基于设计文档第4节，采用**统一标签列表模型**：

**核心数据结构**：
```python
class ETFTag:
    label: str   # 标签显示文本（如 "半导体"）
    group: str   # 分组: "type" | "industry" | "strategy" | "special"

# 示例输出
[
    {"label": "跨境", "group": "type"},
    {"label": "科技", "group": "industry"}
]
```

**分类流程**（4步骤）：
1. **Step 1**: 扫描大类关键词 → 添加 group=type 标签（宽基、跨境、商品、策略）
2. **Step 2**: 扫描细分关键词 → 添加 group=industry/strategy 标签
3. **Step 3**: 扫描特殊属性 → 添加 group=special 标签（LOF、联接、增强等）
4. **Step 4**: 去冗余 + 排序（有具体标签时移除泛化大类标签）

### 2.2 关键词库设计

根据设计文档 4.2.3 节，需要实现以下关键词库：

**宽基指数关键词**（约15个，精确匹配）：
- 完整词：沪深300、中证500、中证1000、上证50、创业板、科创50等
- 数字模式：300ETF、500ETF、1000ETF等

**跨境指数关键词**：
- 恒生、纳指、纳斯达克、标普、中概、港股、美股、A50等

**行业分类关键词**（约30个大类，每个支持多个同义词）：
- 半导体：[半导体, 芯片, 集成电路]
- 医药：[医药, 医疗, 生物医药, 创新药, CXO, 医疗器械]
- 科技：[科技, 科创, 信息技术]
- 人工智能：[人工智能, AI, AIETF, 机器人]
- 新能源：[新能源, 光伏, 风电, 储能]
- 金融：[金融, 券商, 证券, 银行, 保险, 非银]
- ... 更多行业

**策略关键词**：
- 红利、价值、成长、低波、质量、增强

**特殊属性关键词**：
- LOF、联接、QDII、ESG、杠杆、反向

**排除规则**（安全网机制）：
- "非银" → 排除 "银行"（避免"非银ETF"被误标为银行）

### 2.3 验证矩阵（31个关键边界用例）

设计文档 4.2.4 节定义了31个必须通过的边界用例，覆盖：
- 纯宽基/行业/策略
- 跨境+行业交叉
- 宽基+行业交叉
- 多策略叠加
- 英文/数字名称
- 排除词冲突
- 短名称映射
- 特殊属性识别

**示例用例**：
| ETF 名称 | 期望标签 | 说明 |
|----------|---------|------|
| 沪深300ETF | [宽基, 沪深300] | 纯宽基 |
| 半导体ETF | [半导体] | 纯行业，"行业"大类被去冗余 |
| 恒生科技 | [跨境, 科技] | 跨境+行业共存 |
| 红利低波 | [红利, 低波动] | 多策略叠加 |
| AIETF | [人工智能] | 英文名称 |
| 非银ETF | [非银金融] | 排除词，不应匹配"银行" |

---

## 3. 实施任务清单

### 3.1 任务1：创建分类器服务

**文件**：`backend/app/services/etf_classifier.py`

**实现内容**：
1. 定义 `ETFTag` 数据类（使用 dataclass 或 TypedDict）
2. 定义 `ETFClassifier` 类，包含以下方法：
   - `classify(etf_name: str, etf_code: str = "") -> List[ETFTag]`：核心分类方法
   - `get_display_tags(tags: List[ETFTag], limit: int = 2) -> List[str]`：获取展示标签
   - `_match_broad_base(name: str) -> List[ETFTag]`：匹配宽基指数
   - `_match_cross_border(name: str) -> List[ETFTag]`：匹配跨境指数
   - `_match_commodity(name: str) -> List[ETFTag]`：匹配商品
   - `_match_strategy(name: str) -> List[ETFTag]`：匹配策略
   - `_match_industry(name: str) -> List[ETFTag]`：匹配行业
   - `_match_special(name: str) -> List[ETFTag]`：匹配特殊属性
   - `_remove_redundant_tags(tags: List[ETFTag]) -> List[ETFTag]`：去冗余
   - `_sort_tags(tags: List[ETFTag]) -> List[ETFTag]`：排序
3. 定义完整的关键词库（作为类常量或配置）
4. 实现排除规则机制
5. 添加详细的日志记录

**代码规范**：
- 遵循项目命名规范（参考 akshare_service.py）
- 使用 type hints
- 添加 docstring
- 使用 logger 记录关键步骤

### 3.2 任务2：编写单元测试

**文件**：`backend/tests/services/test_etf_classifier.py`

**测试结构**：
```python
class TestETFClassifier:
    """ETF 分类器基础功能测试"""

    def test_classify_basic(self):
        """测试基础分类功能"""
        pass

    def test_get_display_tags(self):
        """测试展示标签获取"""
        pass

class TestBroadBaseMatching:
    """宽基指数匹配测试"""

    def test_match_standard_broad_base(self):
        """测试标准宽基指数匹配"""
        pass

    def test_match_number_pattern(self):
        """测试数字模式匹配（300ETF、500ETF等）"""
        pass

class TestCrossBorderMatching:
    """跨境指数匹配测试"""
    pass

class TestIndustryMatching:
    """行业分类匹配测试"""
    pass

class TestStrategyMatching:
    """策略匹配测试"""
    pass

class TestSpecialAttributeMatching:
    """特殊属性匹配测试"""
    pass

class TestValidationMatrix:
    """验证矩阵测试（31个边界用例）"""

    @pytest.mark.parametrize("etf_name,expected_tags,description", [
        ("沪深300ETF", [{"label": "宽基", "group": "type"}, {"label": "沪深300", "group": "type"}], "纯宽基"),
        ("半导体ETF", [{"label": "半导体", "group": "industry"}], "纯行业"),
        ("恒生科技", [{"label": "跨境", "group": "type"}, {"label": "科技", "group": "industry"}], "跨境+行业"),
        # ... 全部31个用例
    ])
    def test_validation_matrix(self, etf_name, expected_tags, description):
        """参数化测试：验证矩阵全部用例"""
        classifier = ETFClassifier()
        result = classifier.classify(etf_name)
        assert result == expected_tags, f"Failed: {description}"

class TestEdgeCases:
    """边界情况测试"""

    def test_empty_name(self):
        """测试空名称"""
        pass

    def test_special_characters(self):
        """测试特殊字符"""
        pass

    def test_very_long_name(self):
        """测试超长名称"""
        pass

    def test_exclusion_rules(self):
        """测试排除规则（如"非银"不匹配"银行"）"""
        pass

class TestPerformance:
    """性能测试"""

    def test_single_classification_performance(self):
        """测试单个分类性能 < 1ms"""
        pass

    def test_batch_classification_performance(self):
        """测试批量分类性能（500个ETF < 500ms）"""
        pass
```

### 3.3 任务3：全量验证脚本

**文件**：`backend/scripts/validate_classifier.py`

**功能**：
1. 从 akshare 获取全量 ETF 列表（或使用 fallback JSON）
2. 对每个 ETF 进行分类
3. 输出分类结果到 CSV 文件（包含：code, name, tags）
4. 统计准确率（需要人工审核后标注）
5. 统计性能指标（总耗时、平均耗时）
6. 生成分类报告

**输出示例**：
```
分类结果已保存到: backend/data/classification_results.csv
总计 ETF 数量: 500
分类耗时: 450ms
平均耗时: 0.9ms/个
```

### 3.4 任务4：人工审核与规则调整

**流程**：
1. 运行全量验证脚本，生成分类结果 CSV
2. 人工审核分类结果，标注错误案例
3. 分析错误模式，调整关键词库或规则
4. 重新运行验证，直到准确率 ≥ 85%
5. 记录最终的关键词库和规则

**审核重点**：
- 跨境+行业交叉是否正确
- 宽基+行业交叉是否正确
- 排除词是否生效
- 英文/数字名称是否识别
- 特殊属性是否识别

---

## 4. 关键文件路径

### 4.1 新增文件

| 文件路径 | 说明 |
|---------|------|
| `backend/app/services/etf_classifier.py` | 分类器服务（核心实现） |
| `backend/tests/services/test_etf_classifier.py` | 单元测试 |
| `backend/scripts/validate_classifier.py` | 全量验证脚本 |
| `backend/data/classification_results.csv` | 分类结果输出（临时文件） |

### 4.2 参考文件（只读）

| 文件路径 | 参考内容 |
|---------|---------|
| `backend/app/services/akshare_service.py` | 代码规范、错误处理模式 |
| `backend/app/services/trend_service.py` | 服务类结构参考 |
| `backend/tests/services/test_trend_service.py` | 测试结构参考 |
| `backend/app/data/etf_fallback.json` | ETF 列表数据源 |
| `docs/design/2026-02-10-etf-auto-classification-design.md` | 设计文档 |

### 4.3 不修改的文件

⚠️ **重要**：阶段0不修改任何现有代码，包括：
- `backend/app/services/akshare_service.py`
- `backend/app/core/cache.py`
- `backend/app/api/v1/endpoints/etf.py`
- 任何前端代码

---

## 5. 验证方法

### 5.1 单元测试验证

**运行命令**：
```bash
cd backend
pytest tests/services/test_etf_classifier.py -v
```

**验收标准**：
- ✅ 所有测试用例通过
- ✅ 验证矩阵 31 个用例全部通过
- ✅ 边界情况测试通过
- ✅ 性能测试通过（单个 < 1ms，批量 500 个 < 500ms）

### 5.2 全量验证

**运行命令**：
```bash
cd backend
python scripts/validate_classifier.py
```

**输出文件**：
- `backend/data/classification_results.csv`：包含所有 ETF 的分类结果

**验收标准**：
- ✅ 成功对全量 ETF 进行分类
- ✅ 总耗时 < 500ms
- ✅ 无异常或错误

### 5.3 人工审核

**审核流程**：
1. 打开 `classification_results.csv`
2. 随机抽样 50-100 个 ETF
3. 检查分类标签是否准确
4. 记录错误案例
5. 计算准确率 = (正确数 / 总数) × 100%

**验收标准**：
- ✅ 准确率 ≥ 85%

### 5.4 性能验证

**测试方法**：
```python
import time
from app.services.etf_classifier import ETFClassifier

classifier = ETFClassifier()

# 单个分类性能
start = time.perf_counter()
result = classifier.classify("半导体ETF")
duration = time.perf_counter() - start
assert duration < 0.001  # < 1ms

# 批量分类性能
etf_list = [...]  # 500个ETF
start = time.perf_counter()
for etf in etf_list:
    classifier.classify(etf["name"])
duration = time.perf_counter() - start
assert duration < 0.5  # < 500ms
```

**验收标准**：
- ✅ 单个分类 < 1ms
- ✅ 批量分类（500个）< 500ms

---

## 6. 风险与注意事项

### 6.1 准确率风险

**风险描述**：
- 规则匹配可能出现误分类
- 边界情况处理不当（如"非银ETF"误匹配"银行"）
- 新型 ETF 命名模式未覆盖

**缓解措施**：
1. 严格遵循设计文档的验证矩阵（31个用例）
2. 实现排除规则机制
3. 长关键词优先匹配（避免子串误匹配）
4. 精确匹配宽基指数（防止"医药50"触发宽基）
5. 人工审核全量分类结果，调整规则

### 6.2 性能风险

**风险描述**：
- 关键词库过大导致匹配变慢
- 正则表达式性能问题

**缓解措施**：
1. 使用简单的字符串包含判断（`in` 操作符）
2. 避免复杂的正则表达式
3. 关键词库按长度排序（长关键词优先）
4. 添加性能测试，及时发现瓶颈

### 6.3 维护风险

**风险描述**：
- 关键词库硬编码在代码中，难以维护
- 新行业/主题出现时需要修改代码

**缓解措施**：
1. 关键词库使用类常量或配置字典
2. 添加详细注释说明每个关键词的用途
3. 为后续阶段预留配置化空间（可选：JSON 配置文件）

### 6.4 测试覆盖风险

**风险描述**：
- 测试用例不全面，遗漏边界情况
- 验证矩阵用例不够充分

**缓解措施**：
1. 严格按照设计文档的 31 个验证矩阵用例编写测试
2. 补充边界情况测试（空名称、特殊字符、超长名称）
3. 添加性能测试
4. 全量验证脚本覆盖所有 ETF

### 6.5 文档同步风险

**风险描述**：
- 代码实现与设计文档不一致
- 关键词库与设计文档定义不匹配

**缓解措施**：
1. 严格遵循设计文档 4.2.3 节的关键词库定义
2. 代码中添加注释引用设计文档章节
3. 完成后对比设计文档和实现，确保一致性

---

## 7. 实施顺序与时间估算

### 7.1 推荐实施顺序

**第1步：搭建基础框架**（预计 2-3 小时）
- 创建 `etf_classifier.py` 文件
- 定义 `ETFTag` 数据结构
- 定义 `ETFClassifier` 类骨架
- 实现基础的 `classify()` 方法框架

**第2步：实现关键词匹配逻辑**（预计 3-4 小时）
- 实现宽基指数匹配（含数字模式）
- 实现跨境指数匹配
- 实现商品匹配
- 实现行业分类匹配（30个大类）
- 实现策略匹配
- 实现特殊属性匹配
- 实现排除规则机制

**第3步：实现去冗余和排序**（预计 1-2 小时）
- 实现 `_remove_redundant_tags()` 方法
- 实现 `_sort_tags()` 方法
- 实现 `get_display_tags()` 方法

**第4步：编写单元测试**（预计 4-5 小时）
- 编写基础功能测试
- 编写各类匹配测试
- 编写验证矩阵参数化测试（31个用例）
- 编写边界情况测试
- 编写性能测试

**第5步：全量验证与调整**（预计 3-4 小时）
- 编写全量验证脚本
- 运行全量验证，生成分类结果
- 人工审核分类结果
- 根据审核结果调整关键词库和规则
- 重新验证，直到准确率 ≥ 85%

**总计预估时间**：13-18 小时（约 2-3 个工作日）

### 7.2 里程碑检查点

| 检查点 | 验收标准 | 预计完成时间 |
|--------|---------|-------------|
| **M1: 框架完成** | 代码结构清晰，方法定义完整 | Day 1 上午 |
| **M2: 匹配逻辑完成** | 所有匹配方法实现完成 | Day 1 下午 |
| **M3: 单元测试完成** | 所有测试用例编写完成并通过 | Day 2 上午 |
| **M4: 全量验证完成** | 准确率 ≥ 85%，性能达标 | Day 2 下午 |
| **M5: 文档更新完成** | 代码注释、README 更新 | Day 3 上午 |

---

## 8. 实施细节补充

### 8.1 关键词库实现建议

**数据结构选择**：
```python
# 方案1：字典映射（推荐）
INDUSTRY_KEYWORDS = {
    "半导体": ["半导体", "芯片", "集成电路"],
    "医药": ["医药", "医疗", "生物医药", "创新药", "CXO", "医疗器械"],
    # ...
}

# 方案2：扁平列表（备选）
INDUSTRY_KEYWORDS = [
    ("半导体", ["半导体", "芯片", "集成电路"]),
    ("医药", ["医药", "医疗", "生物医药", "创新药", "CXO", "医疗器械"]),
    # ...
]
```

**推荐方案1**，理由：
- 查找效率高
- 代码可读性好
- 易于维护和扩展

### 8.2 匹配算法实现建议

**长关键词优先匹配**：
```python
def _match_industry(self, name: str) -> List[ETFTag]:
    """匹配行业分类，长关键词优先"""
    tags = []
    matched_keywords = set()  # 避免重复匹配

    # 按关键词长度降序排序
    sorted_keywords = sorted(
        self.INDUSTRY_KEYWORDS.items(),
        key=lambda x: max(len(k) for k in x[1]),
        reverse=True
    )

    for label, keywords in sorted_keywords:
        for keyword in keywords:
            if keyword in name and keyword not in matched_keywords:
                tags.append(ETFTag(label=label, group="industry"))
                matched_keywords.add(keyword)
                break  # 找到一个同义词即可

    return tags
```

**排除规则实现**：
```python
def _apply_exclusion_rules(self, name: str, tags: List[ETFTag]) -> List[ETFTag]:
    """应用排除规则"""
    EXCLUSION_RULES = {
        "非银": ["银行"],  # "非银ETF"不应匹配"银行"
    }

    for trigger, exclude_labels in EXCLUSION_RULES.items():
        if trigger in name:
            tags = [t for t in tags if t.label not in exclude_labels]

    return tags
```

### 8.3 测试数据准备

**验证矩阵测试数据**（31个用例）：
```python
VALIDATION_MATRIX = [
    ("沪深300ETF", [{"label": "宽基", "group": "type"}, {"label": "沪深300", "group": "type"}], "纯宽基"),
    ("半导体ETF", [{"label": "半导体", "group": "industry"}], "纯行业"),
    ("恒生科技", [{"label": "跨境", "group": "type"}, {"label": "科技", "group": "industry"}], "跨境+行业"),
    ("恒生生物", [{"label": "跨境", "group": "type"}, {"label": "医药", "group": "industry"}], "跨境+行业"),
    ("中概互联", [{"label": "跨境", "group": "type"}, {"label": "互联网", "group": "industry"}], "跨境+行业"),
    ("红利ETF", [{"label": "红利", "group": "strategy"}], "纯策略"),
    ("红利低波", [{"label": "红利", "group": "strategy"}, {"label": "低波动", "group": "strategy"}], "多策略"),
    ("科创50", [{"label": "宽基", "group": "type"}, {"label": "科技", "group": "industry"}], "宽基+行业"),
    ("科创50增强", [{"label": "宽基", "group": "type"}, {"label": "科技", "group": "industry"}, {"label": "增强", "group": "special"}], "宽基+行业+策略"),
    ("黄金ETF", [{"label": "商品", "group": "type"}, {"label": "黄金", "group": "industry"}], "纯商品"),
    ("AIETF", [{"label": "人工智能", "group": "industry"}], "英文名称"),
    ("1000ETF", [{"label": "宽基", "group": "type"}, {"label": "中证1000", "group": "type"}], "数字名称"),
    ("A50ETF", [{"label": "跨境", "group": "type"}], "字母+数字"),
    ("酒ETF", [{"label": "食品饮料", "group": "industry"}], "短名称"),
    ("医药50", [{"label": "医药", "group": "industry"}], "数字干扰"),
    ("创成长", [{"label": "宽基", "group": "type"}, {"label": "成长", "group": "strategy"}], "宽基+策略"),
    ("非银ETF", [{"label": "非银金融", "group": "industry"}], "排除词"),
    ("券商ETF", [{"label": "券商", "group": "industry"}], "同义词"),
    ("新能源车", [{"label": "新能源车", "group": "industry"}], "近义词"),
    ("300ETF华夏", [{"label": "宽基", "group": "type"}, {"label": "沪深300", "group": "type"}], "后缀干扰"),
    ("5G通信", [{"label": "通信", "group": "industry"}], "数字开头"),
    ("恒生ETF", [{"label": "跨境", "group": "type"}], "纯跨境"),
    ("创业板50", [{"label": "宽基", "group": "type"}, {"label": "创业板", "group": "type"}], "数字干扰"),
    ("标普500", [{"label": "跨境", "group": "type"}], "数字干扰"),
    ("军工龙头", [{"label": "军工", "group": "industry"}], "无关词"),
    ("生物医药", [{"label": "医药", "group": "industry"}], "多同义词"),
    ("新能车ETF", [{"label": "新能源车", "group": "industry"}], "缩写"),
    ("沪深300LOF", [{"label": "宽基", "group": "type"}, {"label": "沪深300", "group": "type"}, {"label": "LOF", "group": "special"}], "宽基+特殊属性"),
    ("沪深300增强", [{"label": "宽基", "group": "type"}, {"label": "沪深300", "group": "type"}, {"label": "增强", "group": "special"}], "宽基+策略"),
    ("创业板联接", [{"label": "宽基", "group": "type"}, {"label": "创业板", "group": "type"}, {"label": "联接", "group": "special"}], "宽基+特殊属性"),
    ("华夏上证50ETF联接A", [{"label": "宽基", "group": "type"}, {"label": "上证50", "group": "type"}, {"label": "联接", "group": "special"}], "长名称+后缀"),
]
```

### 8.4 全量验证脚本实现要点

**脚本结构**：
```python
#!/usr/bin/env python3
"""
ETF 分类器全量验证脚本
"""
import sys
import time
import csv
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.etf_classifier import ETFClassifier
from app.services.akshare_service import fetch_all_etfs
from app.data.etf_fallback import FALLBACK_DATA

def main():
    classifier = ETFClassifier()

    # 获取 ETF 列表
    print("正在获取 ETF 列表...")
    try:
        etf_list = fetch_all_etfs()
    except Exception as e:
        print(f"获取失败，使用 fallback 数据: {e}")
        etf_list = FALLBACK_DATA

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
            "tags": "|".join([f"{t.label}({t.group})" for t in tags])
        })

    duration = time.perf_counter() - start_time

    # 保存结果
    output_file = Path(__file__).parent.parent / "data" / "classification_results.csv"
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["code", "name", "tags"])
        writer.writeheader()
        writer.writerows(results)

    # 统计
    print(f"\n分类完成！")
    print(f"结果已保存到: {output_file}")
    print(f"总计 ETF 数量: {len(etf_list)}")
    print(f"分类耗时: {duration*1000:.0f}ms")
    print(f"平均耗时: {duration/len(etf_list)*1000:.2f}ms/个")

    # 性能检查
    if duration > 0.5:
        print(f"⚠️  警告：分类耗时超过 500ms")
    else:
        print(f"✅ 性能达标（< 500ms）")

if __name__ == "__main__":
    main()
```

---

## 9. 文档更新要求

根据 `AGENTS.md` 第 4.7 节的强制规定，代码变更必须同步更新相关文档。

### 9.1 必须更新的文档

| 文档 | 更新内容 | 说明 |
|------|---------|------|
| `AGENTS.md` 第 5 节 | 添加 `etf_classifier.py` 到核心代码导航表 | 新增核心服务文件 |
| `docs/design/2026-02-10-etf-auto-classification-design.md` | 更新第 10.3 节更新日志 | 记录阶段0完成情况 |
| `docs/implementation/` | 创建阶段0实施报告（可选） | 记录实施过程和结果 |

### 9.2 文档更新示例

**AGENTS.md 第 5 节更新**：
```markdown
| **分类器服务** | `backend/app/services/etf_classifier.py` | ETF 自动分类标签生成 |
```

**设计文档更新日志**：
```markdown
| 2026-02-XX | v1.4 | 阶段0完成：分类器独立验证通过，准确率 XX%，性能达标 |
```

### 9.3 文档更新时机

⚠️ **重要**：文档更新必须与代码变更在同一个 commit 中提交。

**推荐 commit 流程**：
```bash
# 1. 完成代码实现和测试
git add backend/app/services/etf_classifier.py
git add backend/tests/services/test_etf_classifier.py
git add backend/scripts/validate_classifier.py

# 2. 更新文档
git add AGENTS.md
git add docs/design/2026-02-10-etf-auto-classification-design.md

# 3. 一次性提交
git commit -m "feat(classifier): 实现 ETF 自动分类器（阶段0）

- 实现基于规则匹配的分类器服务
- 支持宽基、跨境、行业、策略、特殊属性识别
- 验证矩阵 31 个用例全部通过
- 全量 ETF 分类准确率 XX%
- 性能达标（< 500ms）
- 更新 AGENTS.md 和设计文档

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## 10. 总结

### 10.1 阶段0的价值

✅ **独立验证**：在不影响现有代码的情况下验证分类规则质量
✅ **快速迭代**：可以快速调整规则，无需担心影响生产环境
✅ **质量保证**：通过 31 个验证矩阵用例和全量验证确保准确率
✅ **性能验证**：提前发现性能瓶颈，确保后续集成顺利
✅ **为后续阶段奠定基础**：提供可靠的分类器实现

### 10.2 关键成功因素

1. **严格遵循设计文档**：特别是验证矩阵和关键词库定义
2. **完善的测试覆盖**：单元测试 + 全量验证 + 人工审核
3. **性能优化**：确保分类计算轻量级（< 1ms）
4. **文档同步**：代码变更与文档更新同步提交

### 10.3 后续阶段预览

阶段0完成后，将进入阶段1（核心分类功能集成）：
- 集成分类器到 `akshare_service.py`
- 修改 API 响应，添加 `tags` 字段
- 前端展示标签

但这些都是后续工作，阶段0专注于分类器本身的验证。

---

## 11. 参考资料

### 11.1 设计文档

- [ETF 自动分类标签功能 - 设计文档](../../docs/design/2026-02-10-etf-auto-classification-design.md)
- [产品需求文档 (PRD)](../../docs/planning/PRD.md)

### 11.2 项目规范

- [AGENTS.md](../../AGENTS.md) - 项目开发规范
- [CLAUDE.md](../../CLAUDE.md) - Claude Code 工作指引

### 11.3 代码参考

- `backend/app/services/akshare_service.py` - 服务层代码规范
- `backend/app/services/trend_service.py` - 服务类结构参考
- `backend/tests/services/test_trend_service.py` - 测试结构参考

---

**文档创建时间**: 2026-02-10
**预计完成时间**: 2-3 个工作日
**文档状态**: 正式实施文档

