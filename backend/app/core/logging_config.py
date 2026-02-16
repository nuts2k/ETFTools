"""
集中日志配置模块

提供统一的日志格式和配置，替代各模块散落的 logging.basicConfig()。
输出到 stdout，适配 Docker 环境（通过 docker logs 查看）。
"""

import logging
import logging.config
import sys


def setup_logging(level: str = "INFO") -> None:
    """
    集中配置所有 logger。

    格式: [2026-02-16 15:30:01] [INFO] [module_name] message
    输出: stdout（Docker 友好）

    应在 main.py 启动时调用一次，在任何 logger 使用之前。
    """
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "standard",
            },
        },
        "root": {
            "level": level,
            "handlers": ["stdout"],
        },
        "loggers": {
            # 第三方库降噪
            "akshare": {"level": "WARNING"},
            "urllib3": {"level": "WARNING"},
            "httpx": {"level": "WARNING"},
            "httpcore": {"level": "WARNING"},
            "apscheduler": {"level": "WARNING"},
            "telegram": {"level": "WARNING"},
            "uvicorn.access": {"level": "WARNING"},
        },
    }
    logging.config.dictConfig(config)
