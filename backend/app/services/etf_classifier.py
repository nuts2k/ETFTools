"""
ETF 自动分类器服务

基于规则匹配的 ETF 分类器，通过扫描 ETF 名称中的关键词，
自动生成分类标签（统一标签列表模型）。

设计文档: docs/design/2026-02-10-etf-auto-classification-design.md
"""

import logging
import re
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ETFTag:
    """ETF 分类标签"""
    label: str   # 标签显示文本（如 "半导体"）
    group: str   # 分组: "type" | "industry" | "strategy" | "special"

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


# 标签 group 排序权重：type > industry > strategy > special
GROUP_ORDER = {"type": 0, "industry": 1, "strategy": 2, "special": 3}


class ETFClassifier:
    """
    ETF 自动分类器

    分类流程（4步骤）：
    1. 扫描大类关键词 → 添加 group=type 标签（宽基、跨境、商品）
    2. 扫描细分关键词 → 添加 group=industry/strategy 标签
    3. 扫描特殊属性 → 添加 group=special 标签（LOF、联接、增强等）
    4. 去冗余 + 排序
    """

    # ========== 关键词库定义 ==========

    # 基金公司名称前缀（预处理时去除）
    FUND_COMPANIES = [
        "华夏", "易方达", "南方", "嘉实", "广发", "博时", "天弘",
        "富国", "汇添富", "招商", "华安", "国泰", "工银", "建信",
        "中银", "华宝", "鹏华", "景顺长城", "银华", "平安",
    ]

    # 宽基指数关键词 → 指数名称（精确匹配，长关键词优先）
    BROAD_BASE_KEYWORDS: Dict[str, str] = {
        "沪深300": "沪深300",
        "中证500": "中证500",
        "中证1000": "中证1000",
        "中证2000": "中证2000",
        "中证A500": "中证A500",
        "A500": "中证A500",
        "中证A50": "中证A50",
        "中证A100": "中证A100",
        "A100": "中证A100",
        "中证800": "中证800",
        "国证2000": "国证2000",
        "上证50": "上证50",
        "上证180": "上证180",
        "上证380": "上证380",
        "上证580": "上证580",
        "上证指数": "上证指数",
        "创业板": "创业板",
        "科创50": "宽基",
        "科创板50": "宽基",
        "科创板": "宽基",
        "双创50": "双创50",
        "双创": "双创50",
        "深100": "深证100",
        "深证100": "深证100",
        "深证50": "深证50",
        "深证主板": "深证50",
        "深证成指": "深成指",
        "深成ETF": "深成指",
        "深300": "深证300",
        "中小100": "中小100",
        "中创400": "中创400",
        "创新100": "创新100",
        "超大盘": "宽基",
        "中盘": "宽基",
        "A股ETF": "宽基",
        "漂亮50": "宽基",
        "核心50": "宽基",
    }

    # 数字+ETF 模式 → 指数名称
    BROAD_BASE_NUMBER_PATTERNS: Dict[str, str] = {
        "300ETF": "沪深300",
        "500ETF": "中证500",
        "800ETF": "中证800",
        "1000ETF": "中证1000",
        "2000ETF": "中证2000",
        "50ETF": "上证50",
    }

    # 纯数字模式（去除基金公司前缀后的匹配）
    PURE_NUMBER_PATTERNS: Dict[str, str] = {
        "300": "沪深300",
        "500": "中证500",
        "1000": "中证1000",
        "2000": "中证2000",
    }

    # 跨境指数关键词
    CROSS_BORDER_KEYWORDS = [
        "恒生", "恒指", "纳指", "纳斯达克", "标普", "中概",
        "港股", "港股通", "美股", "日经", "东证", "德国", "法国",
        "美国", "日本", "巴西", "沙特", "亚太", "亚洲", "东南亚",
        "道琼斯", "富时", "沪港深", "香港", "MSCI",
    ]

    # 需要特殊处理的跨境关键词（避免误匹配）
    # A50 → 跨境（富时A50），但 A500/中证A50 不是跨境
    CROSS_BORDER_SPECIAL_PATTERNS = {
        "A50": {"exclude_prefixes": ["中证"], "exclude_contains": ["A500"]},
    }

    # 商品关键词
    COMMODITY_KEYWORDS = ["黄金", "白银", "原油", "豆粕", "有色金属", "大宗商品"]

    # 货币基金关键词
    CURRENCY_KEYWORDS = [
        "货币", "添益", "快钱", "快线", "日利", "天金",
        "现金添富", "财富宝", "添利",
    ]

    # 债券类关键词
    BOND_KEYWORDS = [
        "国债", "信用债", "公司债", "可转债", "政金债",
        "地方债", "地债", "短融", "城投债", "国开债", "债券",
    ]

    # REITs 代码前缀（180xxx, 508xxx）
    REITS_CODE_PREFIXES = ["180", "508"]
    # REITs 名称关键词（作为补充）
    REITS_KEYWORDS = ["REIT", "REITs"]

    # 行业分类关键词：标签名 → 同义词列表（长关键词优先匹配）
    INDUSTRY_KEYWORDS: Dict[str, List[str]] = {
        "半导体": ["半导体", "芯片", "集成电路"],
        "医药": ["医药", "医疗", "生物医药", "生物", "创新药", "CXO", "医疗器械", "药ETF"],
        "中药": ["中药"],
        "疫苗": ["疫苗"],
        "科技": ["科技", "科创", "信息技术", "TMT"],
        "人工智能": ["人工智能", "AI", "AIETF", "机器人"],
        "新能源": ["新能源", "光伏", "风电", "储能"],
        "新能源车": ["新能源车", "新能车", "整车"],
        "金融": ["金融"],
        "券商": ["券商", "证券"],
        "银行": ["银行"],
        "保险": ["保险"],
        "非银金融": ["非银"],
        "军工": ["军工", "国防"],
        "食品饮料": ["食品饮料", "食品", "白酒", "啤酒", "酒"],
        "消费": ["消费", "零售", "商贸", "国货"],
        "家电": ["家电", "家居", "消电"],
        "汽车": ["汽车"],
        "电子": ["电子"],
        "计算机": ["计算机", "软件"],
        "通信": ["通信", "5G", "电信"],
        "传媒": ["传媒", "文化", "游戏", "影视"],
        "有色金属": ["有色", "铜", "铝", "稀土"],
        "稀有金属": ["稀有金属"],
        "煤炭": ["煤炭"],
        "化工": ["化工", "石化"],
        "钢铁": ["钢铁", "建材", "水泥"],
        "房地产": ["房地产", "地产"],
        "基建": ["基建", "建筑"],
        "农业": ["农业", "种业", "养殖", "畜牧", "农牧", "粮食"],
        "电力": ["电力", "公用事业", "绿电"],
        "旅游": ["旅游"],
        "互联网": ["互联网", "中概互联"],
        "机床": ["机床"],
        # 新增行业
        "航空航天": ["航空航天", "航空", "航天", "通用航空", "卫星"],
        "碳中和": ["碳中和", "低碳"],
        "云计算": ["云计算"],
        "物联网": ["物联网"],
        "信创": ["信创"],
        "数字经济": ["数字经济", "大数据"],
        "新材料": ["新材料", "材料"],
        "电池": ["电池", "锂电"],
        "油气": ["油气", "石油", "天然气"],
        "交通运输": ["交通运输", "交运", "物流"],
        "船舶": ["船舶"],
        "电网": ["电网"],
        "信息安全": ["信息安全"],
        "环保": ["环保"],
        "养老": ["养老"],
        "智能制造": ["智能制造", "智能驾驶", "智能电车", "智能电动", "智能车", "工业母机"],
        "高端装备": ["高端装备", "高端制造", "工程机械"],
        "机械": ["机械ETF"],
        "VR": ["VR"],
        "专精特新": ["专精特新"],
        "能源": ["能源"],  # 注意：依赖 SUBSUME_RULES 被"新能源"/"新能源车"消解
        "矿业": ["矿业"],
        "教育": ["教育"],
        "资源": ["资源"],  # 注意：依赖 SUBSUME_RULES 被"矿业"等消解
        "区域主题": [
            "湾创", "大湾区", "杭州湾", "长三角", "长江保护",
            "成渝", "张江", "G60", "浙江", "湖北",
        ],
        # 商品细分（同时产生 industry 标签）
        "黄金": ["黄金", "金ETF", "上海金"],
        "白银": ["白银"],
        "原油": ["原油"],
        "豆粕": ["豆粕"],
    }

    # 策略关键词：标签名 → 同义词列表
    STRATEGY_KEYWORDS: Dict[str, List[str]] = {
        "红利": ["红利"],
        "高股息": ["高股息"],
        "现金流": ["现金流"],
        "价值": ["价值"],
        "成长": ["成长"],
        "低波动": ["低波"],
        "质量": ["质量"],
        "增强": ["增强"],
        "央企": ["央企"],
        "国企": ["国企"],
        "一带一路": ["一带一路"],
        "基本面": ["基本面"],
        "民企": ["民企"],
        "战略新兴": ["战略新兴"],
        "产业升级": ["产业升级"],
        "新经济": ["新经济"],
        "治理": ["治理", "责任"],
    }

    # 特殊属性关键词（直接作为标签）
    SPECIAL_KEYWORDS = ["LOF", "联接", "QDII", "ESG", "可持续"]

    # 排除规则：触发词 → 需排除的标签列表
    EXCLUSION_RULES: Dict[str, List[str]] = {
        "非银": ["银行"],
    }

    # 标签包含规则：具体标签 → 应移除的泛化标签
    SUBSUME_RULES: Dict[str, List[str]] = {
        "新能源车": ["新能源", "能源"],
        "新能源": ["能源"],
        "非银金融": ["金融"],
        "中药": ["医药"],
        "疫苗": ["医药"],
        "高股息": ["红利"],
        "航空航天": ["军工"],
        "稀有金属": ["有色金属"],
        "油气": ["原油"],
        "智能制造": ["机械"],
        "高端装备": ["机械"],
        "电网": ["电力"],
        "矿业": ["资源"],
    }

    def __init__(self) -> None:
        pass

    def classify(self, etf_name: str, etf_code: str = "") -> List[ETFTag]:
        """
        对 ETF 进行分类，返回标签列表

        Args:
            etf_name: ETF 名称（如 "沪深300ETF"）
            etf_code: ETF 代码（如 "510300"），可选

        Returns:
            排序后的标签列表
        """
        if not etf_name:
            return []

        # 预处理：去除常见基金公司后缀和份额标识
        name = self._preprocess_name(etf_name)
        tags: List[ETFTag] = []

        # Step 1: 扫描大类关键词
        tags.extend(self._match_broad_base(name))
        tags.extend(self._match_cross_border(name))
        tags.extend(self._match_commodity(name))
        tags.extend(self._match_currency(name))
        tags.extend(self._match_bond(name))
        tags.extend(self._match_reits(name, etf_code))

        # Step 2: 扫描细分关键词
        tags.extend(self._match_industry(name))
        tags.extend(self._match_strategy(name))

        # Step 3: 扫描特殊属性
        tags.extend(self._match_special(name))

        # Step 4: 去冗余 + 排序
        tags = self._apply_exclusion_rules(name, tags)
        tags = self._remove_redundant_tags(tags)
        tags = self._sort_tags(tags)

        logger.debug(f"分类结果: {etf_name} -> {[t.label for t in tags]}")
        return tags

    def get_display_tags(self, tags: List[ETFTag], limit: int = 2) -> List[str]:
        """
        获取展示标签（卡片最多显示 limit 个）

        Args:
            tags: 完整标签列表
            limit: 最大展示数量

        Returns:
            标签文本列表
        """
        return [t.label for t in tags[:limit]]

    # ========== 预处理 ==========

    def _preprocess_name(self, name: str) -> str:
        """预处理 ETF 名称，去除基金公司后缀和份额标识"""
        # 去除常见份额标识后缀（A/B/C）
        name = re.sub(r'[ABC]$', '', name)
        # 去除常见基金公司名称前缀
        for company in self.FUND_COMPANIES:
            if name.startswith(company):
                name = name[len(company):]
                break
        return name

    # ========== Step 1: 大类匹配 ==========

    def _match_broad_base(self, name: str) -> List[ETFTag]:
        """匹配宽基指数"""
        tags: List[ETFTag] = []
        matched_index: Optional[str] = None

        # 1. 精确匹配完整宽基关键词（长关键词优先）
        sorted_keywords = sorted(
            self.BROAD_BASE_KEYWORDS.items(),
            key=lambda x: len(x[0]),
            reverse=True,
        )
        for keyword, index_name in sorted_keywords:
            if keyword in name:
                matched_index = index_name
                break

        # 2. 数字+ETF 模式匹配（如 "300ETF"、"1000ETF"）
        # 注意：数字前面不能是字母（避免 "A50ETF" 误匹配 "50ETF"）
        if not matched_index:
            for pattern, index_name in self.BROAD_BASE_NUMBER_PATTERNS.items():
                pos = name.find(pattern)
                if pos >= 0:
                    # 检查数字前面是否有字母
                    if pos == 0 or not name[pos - 1].isalpha():
                        matched_index = index_name
                        break

        # 3. 纯数字匹配（去除基金公司前缀后可能只剩数字，如 "易方达300" → "300"）
        if not matched_index:
            for num, index_name in self.PURE_NUMBER_PATTERNS.items():
                if name == num or name.startswith(num):
                    matched_index = index_name
                    break

        # 4. 创业板特殊处理（"创成长"等简称，只标记宽基不加具体指数名）
        if not matched_index:
            if name.startswith("创") and "创新" not in name and "创业板" not in name:
                matched_index = "宽基"

        if matched_index:
            tags.append(ETFTag(label="宽基", group="type"))
            # 添加具体指数标签（如果不是泛化的"宽基"）
            if matched_index != "宽基":
                tags.append(ETFTag(label=matched_index, group="type"))

        return tags

    def _match_cross_border(self, name: str) -> List[ETFTag]:
        """匹配跨境指数"""
        for keyword in self.CROSS_BORDER_KEYWORDS:
            if keyword in name:
                return [ETFTag(label="跨境", group="type")]

        # 特殊模式匹配（如 A50 需排除 A500/中证A50）
        for keyword, rules in self.CROSS_BORDER_SPECIAL_PATTERNS.items():
            if keyword not in name:
                continue
            excluded = False
            for prefix in rules.get("exclude_prefixes", []):
                if f"{prefix}{keyword}" in name:
                    excluded = True
                    break
            if not excluded:
                for contains in rules.get("exclude_contains", []):
                    if contains in name:
                        excluded = True
                        break
            if not excluded:
                return [ETFTag(label="跨境", group="type")]

        return []

    def _match_commodity(self, name: str) -> List[ETFTag]:
        """匹配商品"""
        for keyword in self.COMMODITY_KEYWORDS:
            if keyword in name:
                return [ETFTag(label="商品", group="type")]
        return []

    def _match_currency(self, name: str) -> List[ETFTag]:
        """匹配货币基金"""
        for keyword in self.CURRENCY_KEYWORDS:
            if keyword in name:
                return [ETFTag(label="货币", group="type")]
        return []

    def _match_bond(self, name: str) -> List[ETFTag]:
        """匹配债券类"""
        for keyword in self.BOND_KEYWORDS:
            if keyword in name:
                return [ETFTag(label="债券", group="type")]
        return []

    def _match_reits(self, name: str, etf_code: str) -> List[ETFTag]:
        """匹配 REITs（基于代码前缀或名称关键词）"""
        # 代码前缀匹配
        if etf_code:
            for prefix in self.REITS_CODE_PREFIXES:
                if etf_code.startswith(prefix):
                    return [ETFTag(label="REITs", group="type")]
        # 名称关键词匹配
        for keyword in self.REITS_KEYWORDS:
            if keyword in name:
                return [ETFTag(label="REITs", group="type")]
        return []

    # ========== Step 2: 细分匹配 ==========

    def _match_industry(self, name: str) -> List[ETFTag]:
        """匹配行业分类，长关键词优先"""
        tags: List[ETFTag] = []
        matched_labels: Set[str] = set()

        # 按关键词最大长度降序排序，确保长关键词优先匹配
        sorted_industries = sorted(
            self.INDUSTRY_KEYWORDS.items(),
            key=lambda x: max(len(k) for k in x[1]),
            reverse=True,
        )

        for label, keywords in sorted_industries:
            if label in matched_labels:
                continue
            # 按关键词长度降序排序
            sorted_kws = sorted(keywords, key=len, reverse=True)
            for keyword in sorted_kws:
                if keyword in name:
                    tags.append(ETFTag(label=label, group="industry"))
                    matched_labels.add(label)
                    break

        return tags

    def _match_strategy(self, name: str) -> List[ETFTag]:
        """匹配策略关键词"""
        tags: List[ETFTag] = []
        for label, keywords in self.STRATEGY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in name:
                    tags.append(ETFTag(label=label, group="strategy"))
                    break
        return tags

    # ========== Step 3: 特殊属性匹配 ==========

    def _match_special(self, name: str) -> List[ETFTag]:
        """匹配特殊属性"""
        tags: List[ETFTag] = []
        for keyword in self.SPECIAL_KEYWORDS:
            if keyword in name:
                tags.append(ETFTag(label=keyword, group="special"))
        return tags

    # ========== Step 4: 去冗余 + 排序 ==========

    def _apply_exclusion_rules(self, name: str, tags: List[ETFTag]) -> List[ETFTag]:
        """应用排除规则"""
        for trigger, exclude_labels in self.EXCLUSION_RULES.items():
            if trigger in name:
                tags = [t for t in tags if t.label not in exclude_labels]
        return tags

    def _remove_redundant_tags(self, tags: List[ETFTag]) -> List[ETFTag]:
        """
        去冗余：有具体标签时移除泛化标签

        规则：
        - 应用 SUBSUME_RULES（如有"新能源车"则移除"新能源"）
        - 去重：同一 label 只保留一个
        """
        labels = {t.label for t in tags}

        # 应用包含规则：具体标签存在时移除泛化标签
        labels_to_remove: Set[str] = set()
        for specific, generals in self.SUBSUME_RULES.items():
            if specific in labels:
                labels_to_remove.update(generals)

        # 去重 + 移除被包含的标签
        seen: Set[str] = set()
        unique_tags: List[ETFTag] = []
        for tag in tags:
            if tag.label in labels_to_remove:
                continue
            if tag.label not in seen:
                seen.add(tag.label)
                unique_tags.append(tag)

        return unique_tags

    def _sort_tags(self, tags: List[ETFTag]) -> List[ETFTag]:
        """按 group 排序：type > industry > strategy > special"""
        return sorted(tags, key=lambda t: GROUP_ORDER.get(t.group, 99))
