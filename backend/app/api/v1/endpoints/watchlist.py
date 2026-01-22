from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Body, Request
from sqlmodel import Session, select
from datetime import datetime

from app.core.database import get_session
from app.core.cache import etf_cache
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User, Watchlist
from app.services.akshare_service import ak_service

router = APIRouter()

@router.get("/", response_model=List[Dict[str, Any]])
def get_watchlist(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get authenticated user's watchlist with realtime info"""
    # 1. Get codes from DB
    statement = select(Watchlist).where(Watchlist.user_id == current_user.id)
    watchlist_items = session.exec(statement).all()
    
    if not watchlist_items:
        return []

    # 2. Fetch realtime info for each code
    results = []
    items_to_update = []
    
    for item in watchlist_items:
        info = ak_service.get_etf_info(item.etf_code)
        if info:
            name = info.get("name") or item.name
            # If we got a name from cache but DB doesn't have it, update DB
            if info.get("name") and not item.name:
                item.name = info.get("name")
                items_to_update.append(item)
            
            results.append({
                "code": item.etf_code,
                "name": name,
                "price": info.get("price"),
                "change_pct": info.get("change_pct"),
                "added_at": item.created_at
            })
        else:
            # Fallback if info not found in cache/live, use DB name
            results.append({
                "code": item.etf_code,
                "name": item.name or "Unknown",
                "price": 0,
                "change_pct": 0,
                "added_at": item.created_at
            })
    
    # Batch update items that got new names
    if items_to_update:
        for updated_item in items_to_update:
            session.add(updated_item)
        session.commit()
            
    # Sort by added time (desc)
    results.sort(key=lambda x: x["added_at"], reverse=True)
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
            item = Watchlist(
                user_id=current_user.id, 
                etf_code=code,
                name=item_info.get("name") if item_info else None
            )
            session.add(item)
            synced_count += 1
            
    session.commit()
    return {"synced_count": synced_count}

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
    
    # Add new
    item = Watchlist(
        user_id=current_user.id, 
        etf_code=code,
        name=item_info.get("name") if item_info else None
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
