"""
API integration tests for ETF endpoints.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
import pandas as pd


class TestGridSuggestionEndpoint:
    """Tests for /etf/{code}/grid-suggestion endpoint."""

    @patch("app.services.akshare_service.ak_service")
    def test_get_grid_suggestion_success(self, mock_ak_service):
        """Verify grid suggestion endpoint returns valid data."""
        from app.main import app
        
        # Mock historical data
        mock_data = pd.DataFrame({
            'date': pd.date_range(start='2023-01-01', periods=100),
            'close': [3.0 + (i % 10) * 0.01 for i in range(100)],
            'high': [3.0 + (i % 10) * 0.01 + 0.01 for i in range(100)],
            'low': [3.0 + (i % 10) * 0.01 - 0.01 for i in range(100)],
        })
        
        mock_ak_service.fetch_history_raw.return_value = mock_data
        
        client = TestClient(app)
        response = client.get("/api/v1/etf/510300/grid-suggestion")
        
        # Should succeed
        assert response.status_code == 200
        
        # Response should contain required fields
        data = response.json()
        assert "upper" in data
        assert "lower" in data
        assert "grid_count" in data
        assert "spacing_pct" in data
        assert "is_out_of_range" in data
