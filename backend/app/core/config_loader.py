import json
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class MetricConfigLoader:
    _instance = None
    _config: Dict[str, Any] = {}
    _last_mtime = 0
    _file_path = ""

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MetricConfigLoader, cls).__new__(cls)
            # path: backend/app/core/config_loader.py -> backend/app/data/metrics_config.json
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cls._file_path = os.path.join(base_dir, "data", "metrics_config.json")
            # Initialize defaults
            cls._config = {"drawdown_days": 120, "atr_period": 14}
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        try:
            if not os.path.exists(self._file_path):
                logger.warning(f"Config file not found at {self._file_path}, using defaults.")
                return

            mtime = os.path.getmtime(self._file_path)
            if mtime > self._last_mtime:
                with open(self._file_path, 'r', encoding='utf-8') as f:
                    new_config = json.load(f)
                    # Validate keys if necessary, or just merge
                    self._config.update(new_config)
                self._last_mtime = mtime
                logger.info(f"Loaded metrics config: {self._config}")
        except Exception as e:
            logger.error(f"Error loading metrics config: {e}")
            # Don't overwrite existing config on transient error

    @property
    def config(self) -> Dict[str, Any]:
        self._load_config() # Check for updates on access
        return self._config

    @property
    def drawdown_days(self) -> int:
        return self.config.get("drawdown_days", 120)

    @property
    def atr_period(self) -> int:
        return self.config.get("atr_period", 14)

metric_config = MetricConfigLoader()
