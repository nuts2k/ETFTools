import pandas as pd
import pytest
import time
from app.services.grid_service import calculate_grid_params
from app.services.akshare_service import disk_cache

def test_calculate_grid_params_basic():
    # Mock dataframe with oscillation
    data = {
        'date': pd.date_range(start='2023-01-01', periods=100),
        'close': [1.0 + (i % 10) * 0.01 for i in range(100)],  # Oscillating 1.00 - 1.10
        'high': [1.0 + (i % 10) * 0.01 + 0.005 for i in range(100)],
        'low': [1.0 + (i % 10) * 0.01 - 0.005 for i in range(100)],
    }
    df = pd.DataFrame(data)
    
    result = calculate_grid_params(df)
    
    assert result['upper'] > 1.05
    assert result['lower'] < 1.05
    assert result['grid_count'] >= 5
    assert not result['is_out_of_range']


def test_atr_spacing_logic():
    """高波动数据应该产生更大的网格间距"""
    # 高波动数据
    high_vol_data = {
        'date': pd.date_range(start='2023-01-01', periods=100),
        'close': [3.0 + (i % 20) * 0.05 for i in range(100)],  # 大幅震荡 3.0 - 4.0
        'high': [3.0 + (i % 20) * 0.05 + 0.1 for i in range(100)],
        'low': [3.0 + (i % 20) * 0.05 - 0.1 for i in range(100)],
    }
    high_vol_df = pd.DataFrame(high_vol_data)
    
    # 低波动数据
    low_vol_data = {
        'date': pd.date_range(start='2023-01-01', periods=100),
        'close': [3.0 + (i % 10) * 0.01 for i in range(100)],  # 小幅震荡 3.0 - 3.1
        'high': [3.0 + (i % 10) * 0.01 + 0.01 for i in range(100)],
        'low': [3.0 + (i % 10) * 0.01 - 0.01 for i in range(100)],
    }
    low_vol_df = pd.DataFrame(low_vol_data)
    
    high_vol_result = calculate_grid_params(high_vol_df)
    low_vol_result = calculate_grid_params(low_vol_df)
    
    # 高波动应该有更大的间距百分比
    assert high_vol_result['spacing_pct'] > low_vol_result['spacing_pct']
    # 两者都应该有合理的网格数量
    assert 5 <= high_vol_result['grid_count'] <= 20
    assert 5 <= low_vol_result['grid_count'] <= 20


def test_calculate_grid_params_cached_basic():
    """测试缓存函数基本功能"""
    from app.services.grid_service import calculate_grid_params_cached
    
    # 准备测试数据
    data = {
        'date': pd.date_range(start='2023-01-01', periods=100),
        'close': [3.0 + (i % 10) * 0.05 for i in range(100)],
        'high': [3.0 + (i % 10) * 0.05 + 0.02 for i in range(100)],
        'low': [3.0 + (i % 10) * 0.05 - 0.02 for i in range(100)],
    }
    df = pd.DataFrame(data)
    
    # Mock ak_service.fetch_history_raw
    from unittest.mock import patch
    with patch('app.services.grid_service.ak_service.fetch_history_raw', return_value=df):
        # 清除可能存在的缓存
        cache_key = "grid_params_510300"
        disk_cache.delete(cache_key)
        
        # 第一次调用（缓存未命中）
        result1 = calculate_grid_params_cached("510300")
        
        # 验证返回结果
        assert result1 is not None
        assert 'upper' in result1
        assert 'lower' in result1
        assert 'grid_count' in result1
        
        # 第二次调用（缓存命中）
        result2 = calculate_grid_params_cached("510300")
        
        # 验证结果一致
        assert result1 == result2


def test_calculate_grid_params_cached_performance():
    """测试缓存性能提升"""
    from app.services.grid_service import calculate_grid_params_cached
    
    # 准备测试数据
    data = {
        'date': pd.date_range(start='2023-01-01', periods=100),
        'close': [3.0 + (i % 10) * 0.05 for i in range(100)],
        'high': [3.0 + (i % 10) * 0.05 + 0.02 for i in range(100)],
        'low': [3.0 + (i % 10) * 0.05 - 0.02 for i in range(100)],
    }
    df = pd.DataFrame(data)
    
    from unittest.mock import patch
    with patch('app.services.grid_service.ak_service.fetch_history_raw', return_value=df):
        code = "510300"
        cache_key = f"grid_params_{code}"
        disk_cache.delete(cache_key)
        
        # 测试冷启动
        start = time.time()
        result1 = calculate_grid_params_cached(code)
        cold_time = time.time() - start
        
        # 测试缓存命中
        start = time.time()
        result2 = calculate_grid_params_cached(code)
        hot_time = time.time() - start
        
        # 验证缓存命中速度至少快 5 倍
        assert hot_time < cold_time * 0.2
        # 缓存命中应该在 50ms 以内
        assert hot_time < 0.05


def test_calculate_grid_params_cached_force_refresh():
    """测试强制刷新功能"""
    from app.services.grid_service import calculate_grid_params_cached
    
    data = {
        'date': pd.date_range(start='2023-01-01', periods=100),
        'close': [3.0 + (i % 10) * 0.05 for i in range(100)],
        'high': [3.0 + (i % 10) * 0.05 + 0.02 for i in range(100)],
        'low': [3.0 + (i % 10) * 0.05 - 0.02 for i in range(100)],
    }
    df = pd.DataFrame(data)
    
    from unittest.mock import patch, MagicMock
    mock_fetch = MagicMock(return_value=df)
    
    with patch('app.services.grid_service.ak_service.fetch_history_raw', mock_fetch):
        code = "510300"
        disk_cache.delete(f"grid_params_{code}")
        
        # 第一次调用
        result1 = calculate_grid_params_cached(code)
        assert mock_fetch.call_count == 1
        
        # 第二次调用（使用缓存）
        result2 = calculate_grid_params_cached(code)
        assert mock_fetch.call_count == 1  # 没有新的调用
        
        # 强制刷新
        result3 = calculate_grid_params_cached(code, force_refresh=True)
        assert mock_fetch.call_count == 2  # 应该有新的调用
