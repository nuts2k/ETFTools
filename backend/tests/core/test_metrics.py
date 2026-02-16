"""DataSourceMetrics 和 @track_datasource 装饰器的单元测试"""

import threading
import time

import pytest

from app.core.metrics import DataSourceMetrics, track_datasource


@pytest.fixture
def metrics():
    """每个测试用例使用独立的 DataSourceMetrics 实例"""
    return DataSourceMetrics()


class TestRecordSuccess:
    def test_increments_count(self, metrics):
        metrics.record_success("eastmoney", 100.0)
        status = metrics.get_source_status("eastmoney")
        assert status["success_count"] == 1
        assert status["failure_count"] == 0
        assert status["status"] == "ok"

    def test_records_latency(self, metrics):
        metrics.record_success("eastmoney", 150.5)
        assert metrics.get_avg_latency("eastmoney") == pytest.approx(150.5)

    def test_sets_last_success_at(self, metrics):
        metrics.record_success("eastmoney", 100.0)
        status = metrics.get_source_status("eastmoney")
        assert "last_success_at" in status

    def test_returns_false_on_first_call(self, metrics):
        assert metrics.record_success("eastmoney", 100.0) is False

    def test_returns_false_after_success(self, metrics):
        metrics.record_success("eastmoney", 100.0)
        assert metrics.record_success("eastmoney", 100.0) is False

    def test_returns_true_on_recovery(self, metrics):
        metrics.record_failure("eastmoney", "err", 100.0)
        assert metrics.record_success("eastmoney", 100.0) is True

    def test_returns_false_after_recovery(self, metrics):
        metrics.record_failure("eastmoney", "err", 100.0)
        metrics.record_success("eastmoney", 100.0)  # recovery
        assert metrics.record_success("eastmoney", 100.0) is False


class TestRecordFailure:
    def test_increments_count(self, metrics):
        metrics.record_failure("eastmoney", "Connection refused", 50.0)
        status = metrics.get_source_status("eastmoney")
        assert status["failure_count"] == 1
        assert status["success_count"] == 0
        assert status["status"] == "error"

    def test_records_error(self, metrics):
        metrics.record_failure("eastmoney", "timeout", 200.0)
        status = metrics.get_source_status("eastmoney")
        assert status["last_error"] == "timeout"

    def test_sets_last_failure_at(self, metrics):
        metrics.record_failure("eastmoney", "err", 50.0)
        status = metrics.get_source_status("eastmoney")
        assert "last_failure_at" in status


class TestSuccessRate:
    def test_all_success(self, metrics):
        for _ in range(10):
            metrics.record_success("sina", 100.0)
        assert metrics.get_success_rate("sina") == pytest.approx(1.0)

    def test_all_failure(self, metrics):
        for _ in range(10):
            metrics.record_failure("sina", "err", 100.0)
        assert metrics.get_success_rate("sina") == pytest.approx(0.0)

    def test_mixed(self, metrics):
        for _ in range(7):
            metrics.record_success("sina", 100.0)
        for _ in range(3):
            metrics.record_failure("sina", "err", 100.0)
        assert metrics.get_success_rate("sina") == pytest.approx(0.7)

    def test_unknown_source(self, metrics):
        assert metrics.get_success_rate("nonexistent") is None


class TestAvgLatency:
    def test_single(self, metrics):
        metrics.record_success("ths", 200.0)
        assert metrics.get_avg_latency("ths") == pytest.approx(200.0)

    def test_multiple(self, metrics):
        metrics.record_success("ths", 100.0)
        metrics.record_success("ths", 300.0)
        assert metrics.get_avg_latency("ths") == pytest.approx(200.0)

    def test_unknown_source(self, metrics):
        assert metrics.get_avg_latency("nonexistent") is None


class TestSlidingWindow:
    def test_window_size_limit(self, metrics):
        # 记录 150 次，窗口大小 100，旧数据应被丢弃
        for i in range(150):
            metrics.record_success("eastmoney", float(i))
        status = metrics.get_source_status("eastmoney")
        assert status["success_count"] == 150
        # 平均延迟应基于最近 100 次 (50..149)
        expected_avg = sum(range(50, 150)) / 100
        assert metrics.get_avg_latency("eastmoney") == pytest.approx(expected_avg)

    def test_success_rate_uses_window(self, metrics):
        # 先记录 100 次失败，再记录 100 次成功
        # 窗口大小 100，成功率应为 1.0（只看最近 100 次）
        for _ in range(100):
            metrics.record_failure("eastmoney", "err", 10.0)
        for _ in range(100):
            metrics.record_success("eastmoney", 10.0)
        assert metrics.get_success_rate("eastmoney") == pytest.approx(1.0)
        # 全局计数仍然保留
        status = metrics.get_source_status("eastmoney")
        assert status["success_count"] == 100
        assert status["failure_count"] == 100


class TestOverallStatus:
    def test_no_sources(self, metrics):
        assert metrics.get_overall_status() == "healthy"

    def test_all_ok(self, metrics):
        metrics.record_success("eastmoney", 100.0)
        metrics.record_success("sina", 100.0)
        assert metrics.get_overall_status() == "healthy"

    def test_degraded(self, metrics):
        metrics.record_success("eastmoney", 100.0)
        metrics.record_failure("sina", "err", 100.0)
        assert metrics.get_overall_status() == "degraded"

    def test_critical(self, metrics):
        metrics.record_failure("eastmoney", "err", 100.0)
        metrics.record_failure("sina", "err", 100.0)
        metrics.record_failure("ths", "err", 100.0)
        assert metrics.get_overall_status() == "critical"

    def test_recovery(self, metrics):
        metrics.record_failure("eastmoney", "err", 100.0)
        metrics.record_failure("sina", "err", 100.0)
        assert metrics.get_overall_status() == "critical"
        # sina 恢复
        metrics.record_success("sina", 100.0)
        assert metrics.get_overall_status() == "degraded"


class TestGetSummary:
    def test_empty(self, metrics):
        assert metrics.get_summary() == {}

    def test_multiple_sources(self, metrics):
        metrics.record_success("eastmoney", 100.0)
        metrics.record_failure("sina", "err", 200.0)
        summary = metrics.get_summary()
        assert "eastmoney" in summary
        assert "sina" in summary
        assert summary["eastmoney"]["status"] == "ok"
        assert summary["sina"]["status"] == "error"


class TestThreadSafety:
    def test_concurrent_writes(self, metrics):
        errors = []

        def writer(source, count):
            try:
                for _ in range(count):
                    metrics.record_success(source, 10.0)
                    metrics.record_failure(source, "err", 5.0)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=("eastmoney", 100)),
            threading.Thread(target=writer, args=("sina", 100)),
            threading.Thread(target=writer, args=("eastmoney", 100)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        status = metrics.get_source_status("eastmoney")
        assert status["success_count"] == 200
        assert status["failure_count"] == 200


class TestTrackDatasourceDecorator:
    def test_success(self):
        # 使用独立的 metrics 实例需要 monkeypatch，
        # 但装饰器使用模块级单例，所以直接测试行为
        @track_datasource("test_source")
        def good_func():
            return "ok"

        result = good_func()
        assert result == "ok"

    def test_failure(self):
        @track_datasource("test_fail_source")
        def bad_func():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            bad_func()

    def test_preserves_return_value(self):
        @track_datasource("test_return")
        def returns_list():
            return [1, 2, 3]

        assert returns_list() == [1, 2, 3]

    def test_preserves_function_name(self):
        @track_datasource("test_name")
        def my_function():
            pass

        assert my_function.__name__ == "my_function"


class TestCircuitBreaker:
    def test_not_open_for_unknown_source(self, metrics):
        assert metrics.is_circuit_open("nonexistent") is False

    def test_not_open_with_insufficient_data(self, metrics):
        """数据不足 window 大小时不触发熔断"""
        for _ in range(5):
            metrics.record_failure("src", "err", 10.0)
        assert metrics.is_circuit_open("src", threshold=0.1, window=10) is False

    def test_opens_when_below_threshold(self, metrics):
        """成功率低于阈值时开启熔断"""
        for _ in range(10):
            metrics.record_failure("src", "err", 10.0)
        assert metrics.is_circuit_open("src", threshold=0.1, window=10) is True

    def test_stays_open_during_cooldown(self, metrics):
        """熔断冷却期内保持开启"""
        for _ in range(10):
            metrics.record_failure("src", "err", 10.0)
        metrics.is_circuit_open("src", threshold=0.1, window=10, cooldown=300)
        # 立即再次检查，仍然开启
        assert metrics.is_circuit_open("src", threshold=0.1, window=10, cooldown=300) is True

    def test_half_open_after_cooldown(self, metrics):
        """冷却期过后进入半开状态（允许探测）"""
        for _ in range(10):
            metrics.record_failure("src", "err", 10.0)
        metrics.is_circuit_open("src", threshold=0.1, window=10, cooldown=0)
        # cooldown=0 立即过期，应允许探测
        import time
        time.sleep(0.01)
        assert metrics.is_circuit_open("src", threshold=0.1, window=10, cooldown=0) is False

    def test_not_open_when_above_threshold(self, metrics):
        """成功率高于阈值时不触发"""
        for _ in range(8):
            metrics.record_success("src", 10.0)
        for _ in range(2):
            metrics.record_failure("src", "err", 10.0)
        assert metrics.is_circuit_open("src", threshold=0.1, window=10) is False
