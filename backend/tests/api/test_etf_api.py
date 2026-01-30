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

    @patch("app.services.akshare_service.ak_service")
    def test_get_grid_suggestion_with_cache(self, mock_ak_service):
        """Verify grid suggestion endpoint uses cache."""
        from app.main import app
        from app.services.akshare_service import disk_cache
        
        # Mock historical data
        mock_data = pd.DataFrame({
            'date': pd.date_range(start='2023-01-01', periods=100),
            'close': [3.0 + (i % 10) * 0.01 for i in range(100)],
            'high': [3.0 + (i % 10) * 0.01 + 0.01 for i in range(100)],
            'low': [3.0 + (i % 10) * 0.01 - 0.01 for i in range(100)],
        })
        
        mock_ak_service.fetch_history_raw.return_value = mock_data
        
        # Clear cache
        disk_cache.delete("grid_params_510300")
        
        client = TestClient(app)
        
        # First request (cache miss)
        response1 = client.get("/api/v1/etf/510300/grid-suggestion")
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second request (cache hit)
        response2 = client.get("/api/v1/etf/510300/grid-suggestion")
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Data should be identical
        assert data1 == data2

    @patch("app.services.grid_service.ak_service")
    def test_get_grid_suggestion_force_refresh(self, mock_ak_service):
        """Verify force_refresh parameter works."""
        from app.main import app
        from app.services.akshare_service import disk_cache
        
        # Mock historical data
        mock_data = pd.DataFrame({
            'date': pd.date_range(start='2023-01-01', periods=100),
            'close': [3.0 + (i % 10) * 0.01 for i in range(100)],
            'high': [3.0 + (i % 10) * 0.01 + 0.01 for i in range(100)],
            'low': [3.0 + (i % 10) * 0.01 - 0.01 for i in range(100)],
        })
        
        mock_ak_service.fetch_history_raw.return_value = mock_data
        
        # Clear cache
        disk_cache.delete("grid_params_510300")
        
        client = TestClient(app)
        
        # Normal request
        response1 = client.get("/api/v1/etf/510300/grid-suggestion")
        assert response1.status_code == 200
        assert mock_ak_service.fetch_history_raw.call_count == 1
        
        # Cached request (no new fetch)
        response2 = client.get("/api/v1/etf/510300/grid-suggestion")
        assert response2.status_code == 200
        assert mock_ak_service.fetch_history_raw.call_count == 1
        
        # Force refresh (should fetch again)
        response3 = client.get("/api/v1/etf/510300/grid-suggestion?force_refresh=true")
        assert response3.status_code == 200
        assert mock_ak_service.fetch_history_raw.call_count == 2
