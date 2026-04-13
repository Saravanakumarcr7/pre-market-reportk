NSE_BASE_URL = "https://www.nseindia.com"
NSE_OPTION_CHAIN_URL = "https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
NSE_INDEX_URL = "https://www.nseindia.com/api/equity-stockIndices?index={index}"
NSE_ALL_INDICES_URL = "https://www.nseindia.com/api/allIndices"
NSE_FII_DII_URL = "https://www.nseindia.com/api/fiidiiTradeReact"
GIFT_NIFTY_URL = "https://groww.in/indices/global-indices/sgx-nifty"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.nseindia.com",
}

NIFTY_STRIKE_INTERVAL = 50
SENSEX_STRIKE_INTERVAL = 100

COLOR_BULLISH = "#00ff88"
COLOR_BEARISH = "#ff4444"
COLOR_NEUTRAL = "#00d4ff"
COLOR_WARNING = "#ffaa00"
COLOR_CARD_BG = "rgba(255, 255, 255, 0.05)"
COLOR_CARD_BORDER = "rgba(255, 255, 255, 0.1)"
