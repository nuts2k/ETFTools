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
