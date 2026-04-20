from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.config import TUSHARE_HTTP_URL, TUSHARE_TOKEN

try:
    import tushare as ts  # type: ignore
except Exception:  # pragma: no cover - optional dependency in some environments
    ts = None


def tushare_available() -> bool:
    return bool(ts is not None and TUSHARE_TOKEN)


@dataclass(slots=True)
class TushareCNClient:
    token: str = TUSHARE_TOKEN
    http_url: str = TUSHARE_HTTP_URL
    pro: Any | None = None

    def __post_init__(self) -> None:
        if ts is None:
            raise RuntimeError("tushare is not installed")
        if not self.token:
            raise RuntimeError("TUSHARE_TOKEN is not configured")
        self.pro = ts.pro_api(self.token)
        if self.http_url:
            self.pro._DataApi__http_url = self.http_url

    @staticmethod
    def to_ts_code(code: str) -> str:
        code = str(code).zfill(6)
        if code.startswith(("600", "601", "603", "605", "688")):
            suffix = "SH"
        elif code.startswith(("000", "001", "002", "003", "300", "301")):
            suffix = "SZ"
        elif code.startswith(("430", "830", "831", "832", "833", "835", "836", "837", "838", "839", "870", "871", "872", "873", "874", "875", "876", "877", "878", "879", "920")):
            suffix = "BJ"
        else:
            suffix = "SZ"
        return f"{code}.{suffix}"

    @staticmethod
    def from_ts_code(ts_code: str) -> str:
        return str(ts_code).split(".", 1)[0].zfill(6)

    def get_trade_dates(self, *, start_date: str, end_date: str) -> list[str]:
        df = self.pro.trade_cal(
            exchange="",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            is_open="1",
            fields="cal_date",
        )
        if df is None or df.empty:
            return []
        return sorted(
            f"{str(row['cal_date'])[:4]}-{str(row['cal_date'])[4:6]}-{str(row['cal_date'])[6:8]}"
            for _, row in df.iterrows()
        )

    def fetch_daily_history(
        self,
        code: str,
        *,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        ts_code = self.to_ts_code(code)
        daily_df = self.pro.daily(
            ts_code=ts_code,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
        )
        basic_df = self.pro.daily_basic(
            ts_code=ts_code,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            fields="ts_code,trade_date,turnover_rate,volume_ratio,total_mv,circ_mv",
        )

        daily_by_date = {
            str(row.get("trade_date", "")): row
            for row in (daily_df.to_dict("records") if daily_df is not None and not daily_df.empty else [])
            if row.get("trade_date")
        }
        basic_by_date = {
            str(row.get("trade_date", "")): row
            for row in (basic_df.to_dict("records") if basic_df is not None and not basic_df.empty else [])
            if row.get("trade_date")
        }

        all_dates = sorted(set(daily_by_date) | set(basic_by_date))
        rows: list[dict[str, Any]] = []
        for trade_date in all_dates:
            daily = daily_by_date.get(trade_date, {})
            basic = basic_by_date.get(trade_date, {})

            def _float(value: Any) -> float | None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None

            rows.append(
                {
                    "market": "CN",
                    "code": self.from_ts_code(ts_code),
                    "date": f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}",
                    "turnover_rate": _float(basic.get("turnover_rate")),
                    "open": _float(daily.get("open")),
                    "high": _float(daily.get("high")),
                    "low": _float(daily.get("low")),
                    "close": _float(daily.get("close")),
                    "pct_change": _float(daily.get("pct_chg")),
                    "volume": _float(daily.get("vol")),
                    "amount": _float(daily.get("amount")),
                    "circ_mv": _float(basic.get("circ_mv")),
                }
            )
        return sorted(rows, key=lambda item: item["date"])
