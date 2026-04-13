import requests
import time
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup
from config import NSE_FII_DII_URL, GIFT_NIFTY_URL

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False


def _nse_session():
    """Create a requests session with proper NSE headers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Referer": "https://www.nseindia.com/option-chain",
        "X-Requested-With": "XMLHttpRequest",
    })
    try:
        session.get("https://www.nseindia.com", timeout=10)
    except Exception:
        pass
    time.sleep(0.3)
    return session


class NSEFetcher:
    """Fetches market data using Yahoo Finance (primary) + NSE (fallback)."""

    def __init__(self):
        self.nse_session = _nse_session()

    def _nse_get(self, url, retries=2):
        """GET request to NSE with retry."""
        for attempt in range(retries + 1):
            try:
                r = self.nse_session.get(url, timeout=15)
                if r.status_code in (401, 403):
                    self.nse_session = _nse_session()
                    continue
                r.raise_for_status()
                return r.json()
            except Exception:
                if attempt < retries:
                    self.nse_session = _nse_session()
                    time.sleep(1)
                    continue
                return None
        return None

    # ── INDEX DATA (Yahoo Finance — works reliably) ──────────────────────

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
                "pChange": round(((info.last_price - info.previous_close) / info.previous_close) * 100, 2),
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

    # ── OPTION CHAIN (NSE API — may fail on cloud) ───────────────────────

    def get_option_chain(self, symbol="NIFTY"):
        """Fetch option chain from NSE. Works locally, may fail on cloud."""
        # Try nsepython first
        try:
            from nsepython import nse_optionchain_scrapper
            data = nse_optionchain_scrapper(symbol)
            if isinstance(data, str):
                data = json.loads(data)
            if data and data.get("records", {}).get("data"):
                return data
        except Exception:
            pass

        # Fallback: direct NSE API
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        data = self._nse_get(url)
        if data and data.get("records", {}).get("data"):
            return data

        return None

    # ── FII/DII DATA (NSE API — works reliably even on cloud) ────────────

    def get_fii_dii_data(self):
        """Fetch FII/DII trading activity."""
        data = self._nse_get(NSE_FII_DII_URL)
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

    # ── GIFT NIFTY (Web Scraping) ────────────────────────────────────────

    def get_gift_nifty(self):
        """Scrape GIFT Nifty value from Google Finance."""
        try:
            # Try Google Finance
            url = "https://www.google.com/finance/quote/NIFTY_50:INDEXNSE"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            r = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, "lxml")

            # Google Finance shows price in a specific div
            price_el = soup.select_one('[data-last-price]')
            if price_el:
                val = float(price_el['data-last-price'])
                if 15000 < val < 35000:
                    return {"price": val, "source": "google"}
        except Exception:
            pass

        # Fallback: Groww
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            r = requests.get(GIFT_NIFTY_URL, headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, "lxml")
            for script in soup.find_all("script"):
                text = script.string or ""
                if "ltp" in text:
                    matches = re.findall(r'"ltp"\s*:\s*"?([\d,.]+)"?', text)
                    for m in matches:
                        val = float(m.replace(",", ""))
                        if 15000 < val < 35000:
                            return {"price": val, "source": "groww"}
        except Exception:
            pass

        return None

    def get_nifty_futures(self):
        """Fetch Nifty futures data."""
        url = "https://www.nseindia.com/api/liveEquity-derivatives?index=nse50_fut"
        data = self._nse_get(url)
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
