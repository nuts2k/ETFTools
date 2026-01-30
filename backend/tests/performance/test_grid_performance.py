"""
性能基准测试 - 网格参数缓存优化

验证缓存带来的性能提升
"""

import time
import pytest
import pandas as pd
from unittest.mock import patch

from app.services.grid_service import calculate_grid_params_cached
from app.services.akshare_service import disk_cache


@pytest.mark.performance
def test_grid_cache_performance_improvement():
    """验证缓存带来的性能提升"""
    
    # 准备测试数据
    mock_data = pd.DataFrame({
        'date': pd.date_range(start='2023-01-01', periods=100),
        'close': [3.0 + (i % 10) * 0.05 for i in range(100)],
        'high': [3.0 + (i % 10) * 0.05 + 0.02 for i in range(100)],
        'low': [3.0 + (i % 10) * 0.05 - 0.02 for i in range(100)],
    })
    
    with patch('app.services.grid_service.ak_service.fetch_history_raw', return_value=mock_data):
        code = "510300"
        cache_key = f"grid_params_{code}"
        
        # 清除缓存
        disk_cache.delete(cache_key)
        
        # 冷启动测试（3次取平均）
        cold_times = []
        for _ in range(3):
            disk_cache.delete(cache_key)
            start = time.time()
            result = calculate_grid_params_cached(code)
            cold_times.append(time.time() - start)
        
        avg_cold_time = sum(cold_times) / len(cold_times)
        
        # 缓存命中测试（10次取平均）
        hot_times = []
        for _ in range(10):
            start = time.time()
            result = calculate_grid_params_cached(code)
            hot_times.append(time.time() - start)
        
        avg_hot_time = sum(hot_times) / len(hot_times)
        
        # 性能报告
        speedup = avg_cold_time / avg_hot_time if avg_hot_time > 0 else 0
        
        print(f"\n{'='*60}")
        print(f"网格参数缓存性能测试结果")
        print(f"{'='*60}")
        print(f"  冷启动平均耗时: {avg_cold_time*1000:.1f}ms")
        print(f"  缓存命中平均耗时: {avg_hot_time*1000:.1f}ms")
        print(f"  性能提升倍数: {speedup:.1f}x")
        print(f"  性能提升百分比: {(1 - avg_hot_time/avg_cold_time)*100:.1f}%")
        print(f"{'='*60}")
        
        # 验证性能目标
        assert avg_hot_time < 0.05, f"缓存命中应该在 50ms 以内，实际: {avg_hot_time*1000:.1f}ms"
        assert speedup > 5, f"性能提升应该超过 5 倍，实际: {speedup:.1f}x"
        
        return {
            "cold_time_ms": avg_cold_time * 1000,
            "hot_time_ms": avg_hot_time * 1000,
            "speedup": speedup,
            "improvement_pct": (1 - avg_hot_time/avg_cold_time) * 100
        }


@pytest.mark.performance
def test_concurrent_cache_access():
    """测试并发访问缓存的性能"""
    import concurrent.futures
    
    # 准备测试数据
    mock_data = pd.DataFrame({
        'date': pd.date_range(start='2023-01-01', periods=100),
        'close': [3.0 + (i % 10) * 0.05 for i in range(100)],
        'high': [3.0 + (i % 10) * 0.05 + 0.02 for i in range(100)],
        'low': [3.0 + (i % 10) * 0.05 - 0.02 for i in range(100)],
    })
    
    with patch('app.services.grid_service.ak_service.fetch_history_raw', return_value=mock_data):
        code = "510300"
        cache_key = f"grid_params_{code}"
        
        # 预热缓存
        disk_cache.delete(cache_key)
        calculate_grid_params_cached(code)
        
        # 并发测试
        def fetch_grid():
            start = time.time()
            result = calculate_grid_params_cached(code)
            return time.time() - start
        
        # 10个并发请求
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            start = time.time()
            futures = [executor.submit(fetch_grid) for _ in range(10)]
            times = [f.result() for f in concurrent.futures.as_completed(futures)]
            total_time = time.time() - start
        
        avg_time = sum(times) / len(times)
        
        print(f"\n{'='*60}")
        print(f"并发缓存访问性能测试")
        print(f"{'='*60}")
        print(f"  并发请求数: 10")
        print(f"  总耗时: {total_time*1000:.1f}ms")
        print(f"  平均单次耗时: {avg_time*1000:.1f}ms")
        print(f"  最大单次耗时: {max(times)*1000:.1f}ms")
        print(f"  最小单次耗时: {min(times)*1000:.1f}ms")
        print(f"{'='*60}")
        
        # 验证并发性能
        assert total_time < 1.0, f"10个并发请求应该在 1s 内完成，实际: {total_time:.2f}s"
        assert avg_time < 0.1, f"平均响应时间应该在 100ms 以内，实际: {avg_time*1000:.1f}ms"
