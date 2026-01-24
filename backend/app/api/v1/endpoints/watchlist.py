from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Body, Request
from sqlmodel import Session, select, func
from datetime import datetime
import concurrent.futures

from app.core.database import get_session
from app.core.cache import etf_cache
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User, Watchlist
from app.services.akshare_service import ak_service
from app.services.metrics_service import metrics_service

router = APIRouter()

def process_watchlist_item(item: Watchlist) -> Dict[str, Any]:
    """Helper to process a single watchlist item (Realtime info + Metrics)"""
    info = ak_service.get_etf_info(item.etf_code)
    
    price = 0.0
    change_pct = 0.0
    name = item.name or "Unknown"

    if info:
        name = info.get("name") or name
        price = float(info.get("price", 0.0))
        change_pct = float(info.get("change_pct", 0.0))
    
    # Calculate lite metrics (Non-blocking history fetch inside)
    metrics = metrics_service.get_realtime_metrics_lite(item.etf_code, price, change_pct)
    
    return {
        "code": item.etf_code,
        "name": name,
        "price": price,
        "change_pct": change_pct,
        "sort_order": item.sort_order,
        "added_at": item.created_at,
        "atr": metrics.get("atr"),
        "current_drawdown": metrics.get("current_drawdown"),
        "needs_name_update": (info.get("name") and not item.name)
    }

@router.get("/", response_model=List[Dict[str, Any]])
def get_watchlist(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get watchlist with parallel processing for metrics"""
    statement = select(Watchlist).where(Watchlist.user_id == current_user.id).order_by(Watchlist.sort_order.asc())
    watchlist_items = session.exec(statement).all()
    
    if not watchlist_items:
        return []

    # Parallel processing using ThreadPoolExecutor
    results = []
    items_to_update = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all items for processing
        future_to_item = {executor.submit(process_watchlist_item, item): item for item in watchlist_items}
        
        for future in concurrent.futures.as_completed(future_to_item):
            item = future_to_item[future]
            try:
                data = future.result()
                # Handle name update if needed
                if data.pop("needs_name_update", False):
                    item.name = data["name"]
                    items_to_update.append(item)
                results.append(data)
            except Exception as e:
                # Fallback for failed items
                results.append({
                    "code": item.etf_code,
                    "name": item.name or "Error",
                    "price": 0,
                    "change_pct": 0,
                    "sort_order": item.sort_order,
                    "added_at": item.created_at,
                    "atr": None,
                    "current_drawdown": None
                })

    # Sort results back by sort_order because as_completed returns in finish order
    results.sort(key=lambda x: x["sort_order"])

    if items_to_update:
        for updated_item in items_to_update:
            session.add(updated_item)
        session.commit()
            
    return results

@router.post("/sync")
async def sync_watchlist(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    items = await request.json()
    synced_count = 0
    for item_data in items:
        if isinstance(item_data, str):
            code = item_data
            item_info = {}
        else:
            code = item_data.get("code")
            item_info = item_data
        if not code: continue

        if item_info.get("name") and item_info.get("name") != "Unknown":
             existing_info = etf_cache.get_etf_info(code)
             if not existing_info or existing_info.get("name") == "Unknown":
                 try:
                     clean_item = item_info.copy()
                     clean_item["price"] = float(item_info.get("price", 0))
                     clean_item["change_pct"] = float(item_info.get("change_pct", 0))
                     etf_cache.update_etf_info(clean_item)
                 except: pass

        statement = select(Watchlist).where(Watchlist.user_id == current_user.id, Watchlist.etf_code == code)
        existing = session.exec(statement).first()
        if not existing:
            min_order_stmt = select(func.min(Watchlist.sort_order)).where(Watchlist.user_id == current_user.id)
            min_order = session.exec(min_order_stmt).one() or 0
            item = Watchlist(user_id=current_user.id, etf_code=code, name=item_info.get("name") if item_info else None, sort_order=min_order - 1)
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
    statement = select(Watchlist).where(Watchlist.user_id == current_user.id)
    items = session.exec(statement).all()
    item_map = {item.etf_code: item for item in items}
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
    if item_info and item_info.get("name") and item_info.get("name") != "Unknown":
        item_info["code"] = code
        try:
             item_info["price"] = float(item_info.get("price", 0))
             item_info["change_pct"] = float(item_info.get("change_pct", 0))
             etf_cache.update_etf_info(item_info)
        except: pass
    statement = select(Watchlist).where(Watchlist.user_id == current_user.id, Watchlist.etf_code == code)
    existing = session.exec(statement).first()
    if existing: return {"msg": "Already in watchlist"}
    min_order_stmt = select(func.min(Watchlist.sort_order)).where(Watchlist.user_id == current_user.id)
    min_order = session.exec(min_order_stmt).one()
    new_order = (min_order - 1) if min_order is not None else 0
    item = Watchlist(user_id=current_user.id, etf_code=code, name=item_info.get("name") if item_info else None, sort_order=new_order)
    session.add(item)
    session.commit()
    return {"msg": "Added to watchlist"}

@router.delete("/{code}")
def remove_from_watchlist(
    code: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    statement = select(Watchlist).where(Watchlist.user_id == current_user.id, Watchlist.etf_code == code)
    item = session.exec(statement).first()
    if not item: raise HTTPException(status_code=404, detail="Item not found")
    session.delete(item)
    session.commit()
    return {"msg": "Removed from watchlist"}
