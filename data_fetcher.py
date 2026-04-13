import requests
import time
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup
from config import NSE_FII_DII_URL, GIFT_NIFTY_URL


def _nse_session():
    """Create a requests session with proper NSE headers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    })
    # Get cookies
    try:
        session.get("https://www.nseindia.com", timeout=10)
    except Exception:
        pass
    time.sleep(0.3)
    # Switch to API mode
    session.headers.update({
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://www.nseindia.com/option-chain",
        "X-Requested-With": "XMLHttpRequest",
    })
    return session


class NSEFetcher:
    """Handles all data fetching from NSE India and related sources."""

    def __init__(self):
        self.session = _nse_session()
        self._use_nsepython = False
        try:
            from nsepython import nse_optionchain_scrapper
            self._use_nsepython = True
        except ImportError:
            pass

    def _get(self, url, retries=2):
        """GET request with retry + session refresh."""
        for attempt in range(retries + 1):
            try:
                r = self.session.get(url, timeout=15)
                if r.status_code in (401, 403):
                    self.session = _nse_session()
                    continue
                r.raise_for_status()
                return r.json()
            except (requests.exceptions.JSONDecodeError, ValueError):
                if attempt < retries:
                    self.session = _nse_session()
                    time.sleep(1)
                    continue
                return None
            except Exception:
                if attempt < retries:
                    self.session = _nse_session()
                    time.sleep(1)
                    continue
                return None
        return None

    def get_option_chain(self, symbol="NIFTY"):
        """Fetch full option chain. Tries nsepython first, then direct API."""
        # Try nsepython (handles WAF better)
        if self._use_nsepython:
            try:
                from nsepython import nse_optionchain_scrapper
                data = nse_optionchain_scrapper(symbol)
                if isinstance(data, str):
                    data = json.loads(data)
                if data and data.get("records", {}).get("data"):
                    return data
            except Exception:
                pass

        # Fallback: direct API
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        data = self._get(url)
        if data and data.get("records", {}).get("data"):
            return data

        return None

    def get_index_data(self, index_name="NIFTY 50"):
        """Fetch current index data (OHLC, last price, etc.)."""
        # Try nsepython
        if self._use_nsepython:
            try:
                from nsepython import nse_eq
                # nse_eq doesn't work for indices, try allIndices
                pass
            except Exception:
                pass

        # Try allIndices endpoint
        data = self._get("https://www.nseindia.com/api/allIndices")
        if data and "data" in data:
            for item in data["data"]:
                if item.get("index") == index_name:
                    return item

        # Try equity-stockIndices endpoint
        encoded = index_name.replace(" ", "%20")
        url = f"https://www.nseindia.com/api/equity-stockIndices?index={encoded}"
        data = self._get(url)
        if data and "data" in data:
            for item in data["data"]:
                if item.get("index") == index_name:
                    return item
            if data["data"]:
                return data["data"][0]

        return None

    def get_india_vix(self):
        """Extract India VIX from all indices data."""
        data = self._get("https://www.nseindia.com/api/allIndices")
        if data and "data" in data:
            for item in data["data"]:
                idx = item.get("index", "").upper()
                if "VIX" in idx:
                    return {
                        "current": item.get("last", 0),
                        "previous_close": item.get("previousClose", 0),
                        "change": item.get("percentChange", 0),
                        "open": item.get("open", 0),
                        "high": item.get("high", 0),
                        "low": item.get("low", 0),
                    }
        return None

    def get_fii_dii_data(self):
        """Fetch FII/DII trading activity (works even on weekends — returns last data)."""
        data = self._get(NSE_FII_DII_URL)
        if data:
            result = {"fii": {}, "dii": {}}
            items = data if isinstance(data, list) else [data]
            for item in items:
                category = item.get("category", "").upper()
                if "FII" in category or "FPI" in category:
                    result["fii"] = {
                        "buy_value": item.get("buyValue", 0),
                        "sell_value": item.get("sellValue", 0),
                        "net_value": item.get("netValue", 0),
                        "date": item.get("date", ""),
                    }
                elif "DII" in category:
                    result["dii"] = {
                        "buy_value": item.get("buyValue", 0),
                        "sell_value": item.get("sellValue", 0),
                        "net_value": item.get("netValue", 0),
                        "date": item.get("date", ""),
                    }
            if result["fii"] or result["dii"]:
                return result
        return None

    def get_gift_nifty(self):
        """Scrape GIFT Nifty value from public sources."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            r = requests.get(GIFT_NIFTY_URL, headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, "lxml")

            # Look in script tags for embedded JSON data
            for script in soup.find_all("script"):
                text = script.string or ""
                if "ltp" in text or "nifty" in text.lower():
                    matches = re.findall(r'"ltp"\s*:\s*"?([\d,.]+)"?', text)
                    for m in matches:
                        val = float(m.replace(",", ""))
                        if 15000 < val < 35000:
                            return {"price": val, "source": "groww"}

            # Fallback: look for price in visible elements
            for el in soup.select('[class*="price"], [class*="ltp"], [class*="value"]'):
                text = el.get_text(strip=True).replace(",", "")
                try:
                    val = float(text)
                    if 15000 < val < 35000:
                        return {"price": val, "source": "groww"}
                except ValueError:
                    continue
        except Exception:
            pass
        return None

    def get_nifty_futures(self):
        """Fetch Nifty futures data."""
        url = "https://www.nseindia.com/api/liveEquity-derivatives?index=nse50_fut"
        data = self._get(url)
        if data and "data" in data:
            for item in data["data"]:
                if "NIFTY" in item.get("symbol", "").upper():
                    return {
                        "ltp": item.get("lastPrice", 0),
                        "open": item.get("openPrice", 0),
                        "high": item.get("highPrice", 0),
                        "low": item.get("lowPrice", 0),
                        "prev_close": item.get("prevClose", 0),
                        "oi": item.get("openInterest", 0),
                        "change_oi": item.get("changeinOpenInterest", 0),
                    }
        return None
