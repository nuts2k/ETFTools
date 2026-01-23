from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Body, Request
from sqlmodel import Session, select, func
from datetime import datetime

from app.core.database import get_session
from app.core.cache import etf_cache
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User, Watchlist
from app.services.akshare_service import ak_service
from app.services.metrics_service import metrics_service

router = APIRouter()

@router.get("/", response_model=List[Dict[str, Any]])
def get_watchlist(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get authenticated user's watchlist with realtime info and lite metrics"""
    # 1. Get codes from DB, sorted by sort_order
    statement = select(Watchlist).where(Watchlist.user_id == current_user.id).order_by(Watchlist.sort_order.asc())
    watchlist_items = session.exec(statement).all()
    
    if not watchlist_items:
        return []

    # 2. Fetch realtime info and lite metrics for each code
    results = []
    items_to_update = []
    
    for item in watchlist_items:
        info = ak_service.get_etf_info(item.etf_code)
        
        # Prepare basic info
        price = 0.0
        change_pct = 0.0
        name = item.name or "Unknown"

        if info:
            name = info.get("name") or name
            price = float(info.get("price", 0.0))
            change_pct = float(info.get("change_pct", 0.0))
            
            # If we got a name from cache but DB doesn't have it, update DB
            if info.get("name") and not item.name:
                item.name = info.get("name")
                items_to_update.append(item)
        
        # Calculate lite metrics (ATR, Current Drawdown)
        # This is fast because it uses cached history base data
        metrics = metrics_service.get_realtime_metrics_lite(item.etf_code, price, change_pct)
        
        results.append({
            "code": item.etf_code,
            "name": name,
            "price": price,
            "change_pct": change_pct,
            "sort_order": item.sort_order,
            "added_at": item.created_at,
            "atr": metrics.get("atr"),
            "current_drawdown": metrics.get("current_drawdown")
        })
    
    # Batch update items that got new names
    if items_to_update:
        for updated_item in items_to_update:
            session.add(updated_item)
        session.commit()
            
    # Already sorted by sort_order from DB query
    return results


# IMPORTANT: /sync must be defined BEFORE /{code} to avoid route conflict
@router.post("/sync")
async def sync_watchlist(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Sync local watchlist with cloud.
    Strategy: Union (Merge local into cloud).
    Accepts full items (Dict) or just codes (str).
    """
    items = await request.json()
    synced_count = 0
    for item_data in items:
        # Normalize input
        if isinstance(item_data, str):
            code = item_data
            item_info = {}
        else:
            code = item_data.get("code")
            item_info = item_data
            
        if not code:
            continue

        # 1. Update server cache if we learn something new (Client-side knowledge transfer)
        if item_info.get("name") and item_info.get("name") != "Unknown":
             existing_info = etf_cache.get_etf_info(code)
             # If server doesn't know it, or server has "Unknown", learn from client
             if not existing_info or existing_info.get("name") == "Unknown":
                 # Ensure numeric types
                 try:
                     clean_item = item_info.copy()
                     clean_item["price"] = float(item_info.get("price", 0))
                     clean_item["change_pct"] = float(item_info.get("change_pct", 0))
                     etf_cache.update_etf_info(clean_item)
                 except:
                     pass

        # 2. Add to DB
        # Check if exists
        statement = select(Watchlist).where(
            Watchlist.user_id == current_user.id,
            Watchlist.etf_code == code
        )
        existing = session.exec(statement).first()
        
        if not existing:
            # Determine order: put at bottom for sync or top? 
            # For sync, maybe just append. Let's append to bottom.
            min_order_stmt = select(func.min(Watchlist.sort_order)).where(Watchlist.user_id == current_user.id)
            min_order = session.exec(min_order_stmt).one() or 0
            
            item = Watchlist(
                user_id=current_user.id, 
                etf_code=code,
                name=item_info.get("name") if item_info else None,
                sort_order=min_order - 1 # Place at top like adding
            )
            session.add(item)
            synced_count += 1
            
    session.commit()
    return {"synced_count": synced_count}

@router.put("/reorder")
def reorder_watchlist(
    codes: List[str] = Body(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Reorder watchlist items.
    Receives a list of codes in the desired order.
    """
    # Fetch all items for user
    statement = select(Watchlist).where(Watchlist.user_id == current_user.id)
    items = session.exec(statement).all()
    item_map = {item.etf_code: item for item in items}
    
    # Update sort_order
    for index, code in enumerate(codes):
        if code in item_map:
            item = item_map[code]
            item.sort_order = index
            session.add(item)
            
    session.commit()
    return {"msg": "Order updated"}

@router.post("/{code}")
def add_to_watchlist(
    code: str,
    item_info: Optional[Dict[str, Any]] = Body(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Add ETF to watchlist"""
    
    # Learn from client if info provided
    if item_info and item_info.get("name") and item_info.get("name") != "Unknown":
        # Ensure code matches
        item_info["code"] = code
        try:
             item_info["price"] = float(item_info.get("price", 0))
             item_info["change_pct"] = float(item_info.get("change_pct", 0))
             etf_cache.update_etf_info(item_info)
        except:
             pass

    # Check if already exists
    statement = select(Watchlist).where(
        Watchlist.user_id == current_user.id,
        Watchlist.etf_code == code
    )
    existing = session.exec(statement).first()
    if existing:
        return {"msg": "Already in watchlist"}
    
    # Add new - Place at TOP (min_order - 1)
    min_order_stmt = select(func.min(Watchlist.sort_order)).where(Watchlist.user_id == current_user.id)
    min_order = session.exec(min_order_stmt).one()
    
    # If no items, min_order is None, set to 0
    new_order = (min_order - 1) if min_order is not None else 0

    item = Watchlist(
        user_id=current_user.id, 
        etf_code=code,
        name=item_info.get("name") if item_info else None,
        sort_order=new_order
    )
    session.add(item)
    session.commit()
    return {"msg": "Added to watchlist"}

@router.delete("/{code}")
def remove_from_watchlist(
    code: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Remove ETF from watchlist"""
    statement = select(Watchlist).where(
        Watchlist.user_id == current_user.id,
        Watchlist.etf_code == code
    )
    result = session.exec(statement)
    item = result.first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
        
    session.delete(item)
    session.commit()
    return {"msg": "Removed from watchlist"}
