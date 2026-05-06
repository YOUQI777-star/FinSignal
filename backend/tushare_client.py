"""Tushare Pro API 统一初始化入口。

所有需要调用 Tushare 的模块都应从这里导入 `get_pro`，而不是自己重复初始化。
这样 token 和 HTTP endpoint 只需在 .env / config.py 里维护一处。

用法::

    from backend.tushare_client import get_pro

    pro = get_pro()
    df = pro.daily(ts_code="000001.SZ", start_date="20240101", end_date="20240201")

HTTP endpoint 说明：
  使用私有代理 http://8.136.22.187:8011/ 替代官方地址。
  必须在 ts.pro_api() 之后立即设置 pro._DataApi__http_url，否则仍然走官方地址。
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import tushare as ts  # noqa: F401

# 从环境变量读取（.env 由 python-dotenv 或启动脚本加载）
_TOKEN = os.getenv(
    "TUSHARE_TOKEN",
    "pyifxxrzHGYSypEwmOMeYpJwgJLSWGCvtDgYcoPSXrJZWwGaTyJdYMdczAaOwKHg",
)
_HTTP_URL = os.getenv("TUSHARE_HTTP_URL", "http://8.136.22.187:8011/")


@lru_cache(maxsize=1)
def get_pro():
    """返回已初始化的 Tushare Pro API 实例（单例，进程内复用）。

    Raises:
        RuntimeError: tushare 未安装或 token 未配置时抛出。
    """
    try:
        import tushare as ts  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "tushare 未安装。请运行 `pip install tushare` 后重试。"
        ) from exc

    if not _TOKEN:
        raise RuntimeError(
            "TUSHARE_TOKEN 未配置。请在 .env 文件中设置 TUSHARE_TOKEN=<your_token>。"
        )

    pro = ts.pro_api(_TOKEN)
    # 必须覆盖 HTTP endpoint，否则走官方地址（已过期 token 会报 401）
    pro._DataApi__http_url = _HTTP_URL
    return pro
