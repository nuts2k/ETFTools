import pandas as pd
import pytest
from app.services.grid_service import calculate_grid_params

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
