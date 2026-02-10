"""
ETF 自动分类器单元测试

测试覆盖：
- 基础分类功能
- 宽基指数匹配
- 跨境指数匹配
- 行业分类匹配
- 策略匹配
- 特殊属性匹配
- 验证矩阵（31个边界用例）
- 边界情况
- 性能测试
"""

import time

import pytest

from app.services.etf_classifier import ETFClassifier, ETFTag


@pytest.fixture
def classifier() -> ETFClassifier:
    """创建分类器实例"""
    return ETFClassifier()


class TestClassifyBasic:
    """基础分类功能测试"""

    def test_empty_name_returns_empty(self, classifier: ETFClassifier):
        """空名称应返回空列表"""
        assert classifier.classify("") == []

    def test_returns_list_of_etf_tags(self, classifier: ETFClassifier):
        """返回值应为 ETFTag 列表"""
        result = classifier.classify("沪深300ETF")
        assert isinstance(result, list)
        assert all(isinstance(t, ETFTag) for t in result)

    def test_tag_has_label_and_group(self, classifier: ETFClassifier):
        """每个标签应包含 label 和 group"""
        result = classifier.classify("沪深300ETF")
        for tag in result:
            assert hasattr(tag, "label")
            assert hasattr(tag, "group")
            assert tag.group in ("type", "industry", "strategy", "special")

    def test_to_dict(self, classifier: ETFClassifier):
        """ETFTag.to_dict 应返回字典"""
        tag = ETFTag(label="宽基", group="type")
        d = tag.to_dict()
        assert d == {"label": "宽基", "group": "type"}


class TestGetDisplayTags:
    """展示标签测试"""

    def test_default_limit_2(self, classifier: ETFClassifier):
        """默认最多返回 2 个标签"""
        tags = [
            ETFTag(label="宽基", group="type"),
            ETFTag(label="沪深300", group="type"),
            ETFTag(label="LOF", group="special"),
        ]
        result = classifier.get_display_tags(tags)
        assert result == ["宽基", "沪深300"]

    def test_custom_limit(self, classifier: ETFClassifier):
        """自定义展示数量"""
        tags = [
            ETFTag(label="宽基", group="type"),
            ETFTag(label="沪深300", group="type"),
            ETFTag(label="LOF", group="special"),
        ]
        result = classifier.get_display_tags(tags, limit=3)
        assert result == ["宽基", "沪深300", "LOF"]

    def test_fewer_tags_than_limit(self, classifier: ETFClassifier):
        """标签数少于 limit 时全部返回"""
        tags = [ETFTag(label="半导体", group="industry")]
        result = classifier.get_display_tags(tags, limit=2)
        assert result == ["半导体"]


class TestBroadBaseMatching:
    """宽基指数匹配测试"""

    def test_hs300(self, classifier: ETFClassifier):
        """沪深300ETF → [宽基, 沪深300]"""
        result = classifier.classify("沪深300ETF")
        labels = [t.label for t in result]
        assert labels == ["宽基", "沪深300"]

    def test_zz500(self, classifier: ETFClassifier):
        """中证500ETF → [宽基, 中证500]"""
        labels = [t.label for t in classifier.classify("中证500ETF")]
        assert labels == ["宽基", "中证500"]

    def test_zz1000(self, classifier: ETFClassifier):
        """中证1000ETF → [宽基, 中证1000]"""
        labels = [t.label for t in classifier.classify("中证1000ETF")]
        assert labels == ["宽基", "中证1000"]

    def test_sz50(self, classifier: ETFClassifier):
        """上证50ETF → [宽基, 上证50]"""
        labels = [t.label for t in classifier.classify("上证50ETF")]
        assert labels == ["宽基", "上证50"]

    def test_cyb(self, classifier: ETFClassifier):
        """创业板ETF → [宽基, 创业板]"""
        labels = [t.label for t in classifier.classify("创业板ETF")]
        assert labels == ["宽基", "创业板"]

    def test_number_pattern_300(self, classifier: ETFClassifier):
        """300ETF → [宽基, 沪深300]（数字模式）"""
        labels = [t.label for t in classifier.classify("300ETF")]
        assert labels == ["宽基", "沪深300"]

    def test_number_pattern_1000(self, classifier: ETFClassifier):
        """1000ETF → [宽基, 中证1000]（数字模式）"""
        labels = [t.label for t in classifier.classify("1000ETF")]
        assert labels == ["宽基", "中证1000"]

    def test_number_pattern_with_suffix(self, classifier: ETFClassifier):
        """300ETF华夏 → [宽基, 沪深300]（后缀不影响）"""
        labels = [t.label for t in classifier.classify("300ETF华夏")]
        assert labels == ["宽基", "沪深300"]

    def test_cyb50(self, classifier: ETFClassifier):
        """创业板50 → [宽基, 创业板]（50不触发上证50）"""
        labels = [t.label for t in classifier.classify("创业板50")]
        assert labels == ["宽基", "创业板"]

    def test_chuang_abbreviation(self, classifier: ETFClassifier):
        """创成长 → [宽基, 成长]（创业板简称）"""
        labels = [t.label for t in classifier.classify("创成长")]
        assert labels == ["宽基", "成长"]


class TestCrossBorderMatching:
    """跨境指数匹配测试"""

    def test_hengseng(self, classifier: ETFClassifier):
        """恒生ETF → [跨境]"""
        labels = [t.label for t in classifier.classify("恒生ETF")]
        assert labels == ["跨境"]

    def test_hengseng_tech(self, classifier: ETFClassifier):
        """恒生科技 → [跨境, 科技]"""
        labels = [t.label for t in classifier.classify("恒生科技")]
        assert labels == ["跨境", "科技"]

    def test_zhonggai(self, classifier: ETFClassifier):
        """中概互联 → [跨境, 互联网]"""
        labels = [t.label for t in classifier.classify("中概互联")]
        assert labels == ["跨境", "互联网"]

    def test_a50_is_cross_border(self, classifier: ETFClassifier):
        """A50ETF → [跨境]（富时A50，非A股宽基）"""
        labels = [t.label for t in classifier.classify("A50ETF")]
        assert labels == ["跨境"]

    def test_biaopu500_is_cross_border(self, classifier: ETFClassifier):
        """标普500 → [跨境]（500不触发中证500）"""
        labels = [t.label for t in classifier.classify("标普500")]
        assert labels == ["跨境"]


class TestIndustryMatching:
    """行业分类匹配测试"""

    def test_semiconductor(self, classifier: ETFClassifier):
        """半导体ETF → [半导体]"""
        labels = [t.label for t in classifier.classify("半导体ETF")]
        assert labels == ["半导体"]

    def test_medicine(self, classifier: ETFClassifier):
        """医药50 → [医药]（50不触发宽基）"""
        labels = [t.label for t in classifier.classify("医药50")]
        assert labels == ["医药"]

    def test_bio_medicine(self, classifier: ETFClassifier):
        """生物医药 → [医药]（多同义词只产生一个标签）"""
        labels = [t.label for t in classifier.classify("生物医药")]
        assert labels == ["医药"]

    def test_ai_english(self, classifier: ETFClassifier):
        """AIETF → [人工智能]（英文名称）"""
        labels = [t.label for t in classifier.classify("AIETF")]
        assert labels == ["人工智能"]

    def test_wine_short_name(self, classifier: ETFClassifier):
        """酒ETF → [食品饮料]（短名称映射）"""
        labels = [t.label for t in classifier.classify("酒ETF")]
        assert labels == ["食品饮料"]

    def test_broker(self, classifier: ETFClassifier):
        """券商ETF → [券商]"""
        labels = [t.label for t in classifier.classify("券商ETF")]
        assert labels == ["券商"]

    def test_military(self, classifier: ETFClassifier):
        """军工龙头 → [军工]（"龙头"不成为标签）"""
        labels = [t.label for t in classifier.classify("军工龙头")]
        assert labels == ["军工"]

    def test_5g_communication(self, classifier: ETFClassifier):
        """5G通信 → [通信]（数字开头不触发宽基）"""
        labels = [t.label for t in classifier.classify("5G通信")]
        assert labels == ["通信"]

    def test_new_energy_vehicle(self, classifier: ETFClassifier):
        """新能源车 → [新能源车]（不产生"新能源"冗余标签）"""
        labels = [t.label for t in classifier.classify("新能源车")]
        assert labels == ["新能源车"]

    def test_new_energy_vehicle_abbrev(self, classifier: ETFClassifier):
        """新能车ETF → [新能源车]（缩写匹配）"""
        labels = [t.label for t in classifier.classify("新能车ETF")]
        assert labels == ["新能源车"]


class TestStrategyMatching:
    """策略匹配测试"""

    def test_dividend(self, classifier: ETFClassifier):
        """红利ETF → [红利]"""
        labels = [t.label for t in classifier.classify("红利ETF")]
        assert labels == ["红利"]

    def test_multi_strategy(self, classifier: ETFClassifier):
        """红利低波 → [红利, 低波动]（多策略叠加）"""
        labels = [t.label for t in classifier.classify("红利低波")]
        assert labels == ["红利", "低波动"]

    def test_growth(self, classifier: ETFClassifier):
        """成长ETF → 包含成长标签"""
        tags = classifier.classify("成长ETF")
        labels = [t.label for t in tags]
        assert "成长" in labels


class TestSpecialAttributeMatching:
    """特殊属性匹配测试"""

    def test_lof(self, classifier: ETFClassifier):
        """沪深300LOF → 包含 LOF 标签"""
        tags = classifier.classify("沪深300LOF")
        labels = [t.label for t in tags]
        assert "LOF" in labels
        assert tags[-1].group == "special"

    def test_liangjie(self, classifier: ETFClassifier):
        """创业板联接 → 包含联接标签"""
        tags = classifier.classify("创业板联接")
        labels = [t.label for t in tags]
        assert "联接" in labels

    def test_enhanced(self, classifier: ETFClassifier):
        """沪深300增强 → 包含增强标签（strategy 组）"""
        tags = classifier.classify("沪深300增强")
        labels = [t.label for t in tags]
        assert "增强" in labels
        enhanced_tag = next(t for t in tags if t.label == "增强")
        assert enhanced_tag.group == "strategy"


class TestExclusionRules:
    """排除规则测试"""

    def test_feiyin_excludes_bank(self, classifier: ETFClassifier):
        """非银ETF → [非银金融]，不应包含银行标签"""
        tags = classifier.classify("非银ETF")
        labels = [t.label for t in tags]
        assert "非银金融" in labels
        assert "银行" not in labels

    def test_feiyin_no_finance_redundancy(self, classifier: ETFClassifier):
        """非银金融应移除泛化的"金融"标签"""
        tags = classifier.classify("非银ETF")
        labels = [t.label for t in tags]
        assert "金融" not in labels


# 验证矩阵：31个边界用例
VALIDATION_MATRIX = [
    ("沪深300ETF", ["宽基", "沪深300"], "纯宽基"),
    ("半导体ETF", ["半导体"], "纯行业"),
    ("恒生科技", ["跨境", "科技"], "跨境+行业"),
    ("恒生生物", ["跨境", "医药"], "跨境+行业"),
    ("中概互联", ["跨境", "互联网"], "跨境+行业"),
    ("红利ETF", ["红利"], "纯策略"),
    ("红利低波", ["红利", "低波动"], "多策略"),
    ("科创50", ["宽基", "科技"], "宽基+行业"),
    ("科创50增强", ["宽基", "科技", "增强"], "宽基+行业+策略"),
    ("黄金ETF", ["商品", "黄金"], "纯商品"),
    ("AIETF", ["人工智能"], "英文名称"),
    ("1000ETF", ["宽基", "中证1000"], "数字名称"),
    ("A50ETF", ["跨境"], "字母+数字"),
    ("酒ETF", ["食品饮料"], "短名称"),
    ("医药50", ["医药"], "数字干扰"),
    ("创成长", ["宽基", "成长"], "宽基+策略"),
    ("非银ETF", ["非银金融"], "排除词"),
    ("券商ETF", ["券商"], "同义词"),
    ("新能源车", ["新能源车"], "近义词"),
    ("300ETF华夏", ["宽基", "沪深300"], "后缀干扰"),
    ("5G通信", ["通信"], "数字开头"),
    ("恒生ETF", ["跨境"], "纯跨境"),
    ("创业板50", ["宽基", "创业板"], "数字干扰"),
    ("标普500", ["跨境"], "数字干扰"),
    ("军工龙头", ["军工"], "无关词"),
    ("生物医药", ["医药"], "多同义词"),
    ("新能车ETF", ["新能源车"], "缩写"),
    ("沪深300LOF", ["宽基", "沪深300", "LOF"], "宽基+特殊属性"),
    ("沪深300增强", ["宽基", "沪深300", "增强"], "宽基+策略"),
    ("创业板联接", ["宽基", "创业板", "联接"], "宽基+特殊属性"),
    ("华夏上证50ETF联接A", ["宽基", "上证50", "联接"], "长名称+后缀"),
]


class TestValidationMatrix:
    """验证矩阵测试（31个边界用例）"""

    @pytest.mark.parametrize(
        "etf_name,expected_labels,description",
        VALIDATION_MATRIX,
        ids=[f"#{i+1}_{c[0]}" for i, c in enumerate(VALIDATION_MATRIX)],
    )
    def test_validation_case(
        self,
        classifier: ETFClassifier,
        etf_name: str,
        expected_labels: list,
        description: str,
    ):
        """参数化测试：验证矩阵用例"""
        result = classifier.classify(etf_name)
        actual_labels = [t.label for t in result]
        assert actual_labels == expected_labels, (
            f"[{description}] {etf_name}: "
            f"期望 {expected_labels}, 实际 {actual_labels}"
        )


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_string(self, classifier: ETFClassifier):
        """空字符串"""
        assert classifier.classify("") == []

    def test_pure_numbers(self, classifier: ETFClassifier):
        """纯数字名称"""
        result = classifier.classify("12345")
        assert isinstance(result, list)

    def test_special_characters(self, classifier: ETFClassifier):
        """特殊字符不应导致异常"""
        result = classifier.classify("ETF@#$%")
        assert isinstance(result, list)

    def test_very_long_name(self, classifier: ETFClassifier):
        """超长名称不应导致异常"""
        long_name = "华夏沪深300增强策略交易型开放式指数证券投资基金联接基金A"
        result = classifier.classify(long_name)
        assert isinstance(result, list)

    def test_no_duplicate_labels(self, classifier: ETFClassifier):
        """不应产生重复标签"""
        result = classifier.classify("生物医药ETF")
        labels = [t.label for t in result]
        assert len(labels) == len(set(labels))


class TestPerformance:
    """性能测试"""

    def test_single_classification_under_1ms(self, classifier: ETFClassifier):
        """单个分类性能 < 1ms"""
        start = time.perf_counter()
        classifier.classify("半导体ETF")
        duration = time.perf_counter() - start
        assert duration < 0.001, f"单个分类耗时 {duration*1000:.2f}ms，超过 1ms"

    def test_batch_500_under_500ms(self, classifier: ETFClassifier):
        """批量分类 500 个 ETF < 500ms"""
        names = [f"测试ETF{i}" for i in range(500)]
        start = time.perf_counter()
        for name in names:
            classifier.classify(name)
        duration = time.perf_counter() - start
        assert duration < 0.5, f"批量分类耗时 {duration*1000:.0f}ms，超过 500ms"
