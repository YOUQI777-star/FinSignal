from __future__ import annotations

import json

from backend.scrapers.cn_akshare import AkshareCNClient
from backend.scrapers.tw_twse import TwseClient


def main() -> None:
    cn_client = AkshareCNClient()
    tw_client = TwseClient()

    result = {
        "CN": {
            "live_available": cn_client.live_source_available(),
            "mode": cn_client.last_source_mode,
            "provider": getattr(cn_client, "last_live_provider", None),
            "error": getattr(cn_client, "last_error", None),
        },
        "TW": {
            "live_available": tw_client.live_source_available(),
            "mode": tw_client.last_source_mode,
            "provider": getattr(tw_client, "last_live_provider", None),
            "error": getattr(tw_client, "last_error", None),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
