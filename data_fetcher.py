"""
Data fetcher using multiple sources:
  - yfinance   → Index data (NIFTY, SENSEX, VIX, Bank NIFTY)
  - Groww      → Option chain + FII/DII activity (web scraping)
"""
import requests
import re
import json

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False


GROWW_OPTION_CHAIN_URL = "https://groww.in/v1/api/option_chain_service/v1/option_chain/{symbol}"
GROWW_FII_DII_URL = "https://groww.in/fii-dii-data"
GROWW_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json",
}


class NSEFetcher:
    """Fetches market data from yfinance + Groww (no NSE dependency)."""

    def __init__(self):
        self._groww_session = requests.Session()
        self._groww_session.headers.update(GROWW_HEADERS)

    # ── INDEX DATA (yfinance) ───────────────────────────────────────────

    def get_index_data(self, index_name="NIFTY 50"):
        """Fetch index OHLC data via Yahoo Finance."""
        if not HAS_YFINANCE:
            return None
        try:
            symbol_map = {
                "NIFTY 50": "^NSEI",
                "SENSEX": "^BSESN",
                "NIFTY BANK": "^NSEBANK",
            }
            ticker_sym = symbol_map.get(index_name, "^NSEI")
            ticker = yf.Ticker(ticker_sym)
            info = ticker.fast_info
            return {
                "index": index_name,
                "last": round(info.last_price, 2),
                "previousClose": round(info.previous_close, 2),
                "open": round(info.open, 2),
                "high": round(info.day_high, 2),
                "low": round(info.day_low, 2),
                "change": round(info.last_price - info.previous_close, 2),
                "pChange": round(
                    ((info.last_price - info.previous_close) / info.previous_close) * 100, 2
                ),
            }
        except Exception:
            return None

    def get_india_vix(self):
        """Fetch India VIX via Yahoo Finance."""
        if not HAS_YFINANCE:
            return None
        try:
            vix = yf.Ticker("^INDIAVIX")
            info = vix.fast_info
            current = round(info.last_price, 2)
            prev = round(info.previous_close, 2)
            change_pct = round(((current - prev) / prev) * 100, 2) if prev else 0
            return {
                "current": current,
                "previous_close": prev,
                "change": change_pct,
                "open": round(info.open, 2),
                "high": round(info.day_high, 2),
                "low": round(info.day_low, 2),
            }
        except Exception:
            return None

    # ── OPTION CHAIN (Groww web scraping) ───────────────────────────────

    def get_option_chain(self, symbol="NIFTY"):
        """
        Scrape option chain from Groww internal API.
        Converts Groww format → NSE-compatible format for calculations.py.
        """
        groww_symbol = symbol.lower()  # groww uses lowercase: nifty, banknifty
        if groww_symbol == "banknifty" or groww_symbol == "nifty bank":
            groww_symbol = "banknifty"

        url = GROWW_OPTION_CHAIN_URL.format(symbol=groww_symbol)
        try:
            r = self._groww_session.get(url, timeout=15)
            if r.status_code != 200:
                return None

            groww_data = r.json()
            chains = groww_data.get("optionChain", {}).get("optionChains", [])
            if not chains:
                return None

            # Get spot price from yfinance (more reliable)
            spot_price = 0
            if HAS_YFINANCE:
                try:
                    sym = "^NSEI" if "nifty" in groww_symbol else "^NSEBANK"
                    spot_price = round(yf.Ticker(sym).fast_info.last_price, 2)
                except Exception:
                    pass

            # Convert Groww format → NSE-compatible format
            nse_records = []
            for chain in chains:
                strike_raw = chain.get("strikePrice", 0)
                strike = strike_raw / 100  # Groww stores x100

                call = chain.get("callOption", {})
                put = chain.get("putOption", {})

                record = {"strikePrice": strike}

                if call:
                    call_oi = call.get("openInterest", 0)
                    call_prev_oi = call.get("prevOpenInterest", 0)
                    record["CE"] = {
                        "strikePrice": strike,
                        "openInterest": call_oi,
                        "changeinOpenInterest": call_oi - call_prev_oi,
                        "lastPrice": call.get("ltp", 0),
                        "totalTradedVolume": call.get("volume", 0),
                        "change": call.get("dayChange", 0),
                        "pChange": call.get("dayChangePerc", 0),
                        "impliedVolatility": 0,
                    }

                if put:
                    put_oi = put.get("openInterest", 0)
                    put_prev_oi = put.get("prevOpenInterest", 0)
                    record["PE"] = {
                        "strikePrice": strike,
                        "openInterest": put_oi,
                        "changeinOpenInterest": put_oi - put_prev_oi,
                        "lastPrice": put.get("ltp", 0),
                        "totalTradedVolume": put.get("volume", 0),
                        "change": put.get("dayChange", 0),
                        "pChange": put.get("dayChangePerc", 0),
                        "impliedVolatility": 0,
                    }

                nse_records.append(record)

            # Build NSE-compatible wrapper
            return {
                "records": {
                    "data": nse_records,
                    "underlyingValue": spot_price,
                },
                "source": "groww",
            }

        except Exception:
            return None

    # ── FII/DII DATA (Groww web scraping) ─────────────────────────────

    def get_fii_dii_data(self):
        """Scrape FII/DII trading activity from Groww."""
        try:
            r = self._groww_session.get(
                GROWW_FII_DII_URL,
                headers={"Accept": "text/html"},
                timeout=15,
            )
            if r.status_code != 200:
                return None

            # Extract __NEXT_DATA__ JSON embedded in the page
            match = re.search(
                r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                r.text,
                re.DOTALL,
            )
            if not match:
                return None

            page_data = json.loads(match.group(1))
            records = page_data.get("props", {}).get("pageProps", {}).get("initialData", [])
            if not records:
                return None

            # Most recent record is first
            latest = records[0]
            fii = latest.get("fii", {})
            dii = latest.get("dii", {})
            date_str = latest.get("date", "")

            result = {"fii": {}, "dii": {}}
            if fii:
                result["fii"] = {
                    "buy_value": fii.get("grossBuy", 0),
                    "sell_value": fii.get("grossSell", 0),
                    "net_value": fii.get("netBuySell", 0),
                    "date": date_str,
                }
            if dii:
                result["dii"] = {
                    "buy_value": dii.get("grossBuy", 0),
                    "sell_value": dii.get("grossSell", 0),
                    "net_value": dii.get("netBuySell", 0),
                    "date": date_str,
                }
            if result["fii"] or result["dii"]:
                return result
        except Exception:
            pass
        return None

    # ── GIFT NIFTY (not available via free APIs) ────────────────────────

    def get_gift_nifty(self):
        """GIFT Nifty not reliably available via free APIs."""
        return None

    # ── NIFTY FUTURES (derived from synthetic futures) ──────────────────

    def get_nifty_futures(self):
        """Futures data not available via free scraping. Uses synthetic instead."""
        return None
