import os
from diskcache import Cache
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache setup matches akshare_service.py
CACHE_DIR = os.path.join(os.getcwd(), ".cache")
disk_cache = Cache(CACHE_DIR)
ETF_LIST_CACHE_KEY = "etf_list_all"

# Mock Data for Common A-Share ETFs
MOCK_DATA = [
    {"code": "510300", "name": "沪深300ETF", "price": 3.521, "change_pct": 0.52, "volume": 12345678},
    {"code": "510500", "name": "中证500ETF", "price": 5.123, "change_pct": -0.31, "volume": 9876543},
    {"code": "588000", "name": "科创50ETF", "price": 0.892, "change_pct": 1.25, "volume": 45678901},
    {"code": "512480", "name": "半导体ETF", "price": 0.765, "change_pct": 2.10, "volume": 33445566},
    {"code": "159915", "name": "创业板ETF", "price": 1.888, "change_pct": -0.15, "volume": 22334455},
    {"code": "513050", "name": "中概互联ETF", "price": 0.995, "change_pct": -1.50, "volume": 55667788},
    {"code": "512660", "name": "军工ETF", "price": 0.921, "change_pct": 0.88, "volume": 11223344},
    {"code": "512010", "name": "医药ETF", "price": 0.453, "change_pct": -0.45, "volume": 66778899},
    {"code": "512880", "name": "证券ETF", "price": 0.845, "change_pct": 1.05, "volume": 88990011},
    {"code": "512690", "name": "酒ETF", "price": 0.789, "change_pct": 0.22, "volume": 44556677},
]

def seed_cache():
    logger.info(f"Seeding cache at {CACHE_DIR}...")
    
    # Check if cache exists
    existing = disk_cache.get(ETF_LIST_CACHE_KEY)
    if existing:
        logger.info(f"Found existing cache with {len(existing)} items. Overwriting with mock data...")
    
    # Write mock data
    disk_cache.set(ETF_LIST_CACHE_KEY, MOCK_DATA, expire=86400 * 30) # 30 days
    logger.info("Successfully seeded mock ETF data.")
    
    # Verify
    cached = disk_cache.get(ETF_LIST_CACHE_KEY)
    logger.info(f"Verification: Cache now contains {len(cached)} items.")
    for item in cached[:3]:
        logger.info(f" - {item['name']} ({item['code']}): {item['price']}")

if __name__ == "__main__":
    seed_cache()
