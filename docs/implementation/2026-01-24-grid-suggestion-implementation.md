# Grid Trading Suggestion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a backend service to calculate conservative grid trading parameters based on historical volatility and visualize them on the frontend chart.

**Architecture:** A new `GridService` in Python analyzes historical ETF data (QFQ) to identify oscillating ranges and calculate grid parameters (ADX/ATR based). A new API endpoint exposes this. The frontend `ETFChart` renders the range and a new card displays the suggestions.

**Tech Stack:** Python, FastAPI, Pandas, TypeScript, Next.js, Recharts.

---

### Task 1: Backend Grid Service Core Logic

**Files:**
- Create: `backend/app/services/grid_service.py`
- Test: `backend/tests/services/test_grid_service.py`

**Step 1: Write the failing test for grid calculation**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/services/test_grid_service.py`
Expected: FAIL (ModuleNotFoundError or ImportError)

**Step 3: Write minimal implementation of GridService**

```python
import pandas as pd
import numpy as np
from typing import Dict, Any

def calculate_grid_params(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty or len(df) < 30:
        return {}
        
    # Use last 60 days
    recent_df = df.tail(60).copy()
    
    # Simple quantiles for now (placeholder for ADX/ATR logic)
    upper = recent_df['close'].quantile(0.95)
    lower = recent_df['close'].quantile(0.05)
    current_price = recent_df['close'].iloc[-1]
    
    # Spacing logic (simplified for pass)
    spacing_pct = 0.015
    
    # Calculate count
    price_range = upper - lower
    avg_price = (upper + lower) / 2
    step = avg_price * spacing_pct
    
    if step == 0:
        count = 0
    else:
        count = int(price_range / step)
    
    # Clamp count
    count = max(5, min(count, 20))
    
    return {
        "upper": round(upper, 3),
        "lower": round(lower, 3),
        "spacing_pct": spacing_pct * 100,
        "grid_count": count,
        "range_start": recent_df['date'].iloc[0].strftime("%Y-%m-%d") if 'date' in recent_df.columns else "",
        "range_end": recent_df['date'].iloc[-1].strftime("%Y-%m-%d") if 'date' in recent_df.columns else "",
        "is_out_of_range": current_price > upper * 1.05 or current_price < lower * 0.95
    }
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/services/test_grid_service.py`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/grid_service.py backend/tests/services/test_grid_service.py
git commit -m "feat(backend): init grid service with basic calculation"
```

---

### Task 2: Advanced Grid Logic (ADX/ATR)

**Files:**
- Modify: `backend/app/services/grid_service.py`
- Test: `backend/tests/services/test_grid_service.py`

**Step 1: Add test for ATR logic**

```python
def test_atr_spacing_logic():
    # Volatile data should yield larger spacing
    # ...
    pass
```

**Step 2: Implement ADX/ATR logic**
(I will assume `talib` is not available and write pure pandas implementations for portability)

**Step 3: Run tests**

**Step 4: Commit**

```bash
git commit -am "feat(backend): enhance grid service with ATR/ADX logic"
```

---

### Task 3: API Endpoint

**Files:**
- Modify: `backend/app/api/v1/endpoints/etf.py`
- Test: `backend/tests/api/test_etf_api.py`

**Step 1: Add API test**

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_grid_suggestion():
    # Mock service
    response = client.get("/api/v1/etf/510300/grid-suggestion")
    assert response.status_code == 200
    assert "upper" in response.json()
```

**Step 2: Implement Endpoint**

```python
@router.get("/{code}/grid-suggestion")
def get_grid_suggestion(code: str):
    df = AkShareService.fetch_history_raw(code, period="daily", adjust="qfq")
    return calculate_grid_params(df)
```

**Step 3: Run tests**

**Step 4: Commit**

```bash
git commit -am "feat(api): add grid suggestion endpoint"
```

---

### Task 4: Frontend API & Types

**Files:**
- Modify: `frontend/lib/api.ts`

**Step 1: Add Types**

```typescript
export interface GridSuggestion {
  upper: number;
  lower: number;
  spacing_pct: number;
  grid_count: number;
  range_start: string;
  range_end: string;
  is_out_of_range: boolean;
  reason?: string;
}
```

**Step 2: Commit**

```bash
git commit -am "feat(frontend): add grid suggestion types"
```

---

### Task 5: Grid Suggestion Card

**Files:**
- Create: `frontend/components/GridSuggestionCard.tsx`

**Step 1: Create Component**

- Use Shadcn Card
- Display parameters
- Handle loading state

**Step 2: Commit**

```bash
git add frontend/components/GridSuggestionCard.tsx
git commit -m "feat(ui): add GridSuggestionCard component"
```

---

### Task 6: Chart Visualization Integration

**Files:**
- Modify: `frontend/components/ETFChart.tsx`
- Modify: `frontend/app/etf/[code]/page.tsx`

**Step 1: Update Chart Props**

- Add `gridSuggestion` prop.

**Step 2: Render ReferenceArea/Line**

- Implement conditional rendering based on a toggle state in the parent page.

**Step 3: Integrate in Page**

- Fetch data.
- Add "Show Grid Suggestion" switch.

**Step 4: Commit**

```bash
git commit -am "feat(ui): integrate grid suggestion into chart and page"
```
