import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.share_history_database import create_share_history_tables

if __name__ == "__main__":
    create_share_history_tables()
    print("Table etf_share_history created in etf_share_history.db")
