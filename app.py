import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, time as dtime
from data_fetcher import NSEFetcher
from calculations import (
    calculate_straddle, calculate_pcr, calculate_synthetic_futures,
    calculate_pivot_levels, analyze_open_interest, interpret_vix,
    generate_market_bias, calculate_basis, calculate_max_pain,
)
from config import COLOR_BULLISH, COLOR_BEARISH, COLOR_NEUTRAL, COLOR_WARNING


def get_market_status():
    """Check if Indian market is open, pre-market, or closed."""
    now = datetime.now()
    weekday = now.weekday()  # 0=Mon, 6=Sun
    current_time = now.time()

    if weekday >= 5:  # Saturday/Sunday
        return "CLOSED", "Weekend — Market closed"

    pre_open = dtime(9, 0)
    market_open = dtime(9, 15)
    market_close = dtime(15, 30)

    if current_time < pre_open:
        return "PRE-MARKET", "Pre-market session — Data shows last trading day"
    elif current_time < market_open:
        return "PRE-OPEN", "Pre-open session (9:00-9:15)"
    elif current_time <= market_close:
        return "LIVE", "Market is LIVE"
    else:
        return "CLOSED", "Market closed for the day"

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Pre-Market Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS (Glassmorphism) ───────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&display=swap');

    * { font-family: 'JetBrains Mono', monospace !important; }

    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 1400px;
    }

    .stApp { background: linear-gradient(135deg, #0a0a1a 0%, #0d1117 50%, #0a0a1a 100%); }

    .glass-card {
        background: rgba(255, 255, 255, 0.04);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    }
    .glass-card:hover {
        border-color: rgba(0, 212, 255, 0.3);
        box-shadow: 0 0 20px rgba(0, 212, 255, 0.05);
    }

    .section-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #00d4ff;
        text-transform: uppercase;
        letter-spacing: 2px;
        margin-bottom: 0.8rem;
        border-bottom: 1px solid rgba(0, 212, 255, 0.2);
        padding-bottom: 0.4rem;
    }

    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        line-height: 1.2;
    }
    .metric-label {
        font-size: 0.7rem;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .metric-delta-up { color: #00ff88; font-size: 0.85rem; }
    .metric-delta-down { color: #ff4444; font-size: 0.85rem; }

    .bias-badge {
        display: inline-block;
        padding: 0.3rem 1rem;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.9rem;
        letter-spacing: 1px;
    }
    .bias-bullish { background: rgba(0,255,136,0.15); color: #00ff88; border: 1px solid #00ff88; }
    .bias-bearish { background: rgba(255,68,68,0.15); color: #ff4444; border: 1px solid #ff4444; }
    .bias-neutral { background: rgba(0,212,255,0.15); color: #00d4ff; border: 1px solid #00d4ff; }

    .data-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.8rem;
    }
    .data-table th {
        text-align: left;
        color: #00d4ff;
        padding: 0.4rem 0.6rem;
        border-bottom: 1px solid rgba(255,255,255,0.1);
        font-weight: 500;
    }
    .data-table td {
        padding: 0.4rem 0.6rem;
        border-bottom: 1px solid rgba(255,255,255,0.04);
        color: #ccc;
    }

    .highlight-green { color: #00ff88 !important; font-weight: 600; }
    .highlight-red { color: #ff4444 !important; font-weight: 600; }
    .highlight-cyan { color: #00d4ff !important; font-weight: 600; }
    .highlight-yellow { color: #ffaa00 !important; font-weight: 600; }

    .reason-item {
        font-size: 0.8rem;
        color: #bbb;
        padding: 0.2rem 0;
        padding-left: 1rem;
        border-left: 2px solid rgba(0,212,255,0.3);
        margin-bottom: 0.3rem;
    }

    div[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace !important; }
    div[data-testid="stMetricDelta"] { font-family: 'JetBrains Mono', monospace !important; }

    .stTabs [data-baseweb="tab-list"] { gap: 0; }
    .stTabs [data-baseweb="tab"] {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        color: #888;
        padding: 0.5rem 1.2rem;
        font-size: 0.75rem;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(0,212,255,0.1);
        color: #00d4ff;
        border-color: #00d4ff;
    }

    .disclaimer {
        font-size: 0.65rem;
        color: #555;
        text-align: center;
        padding: 1rem;
        border-top: 1px solid rgba(255,255,255,0.05);
        margin-top: 2rem;
    }

    /* OI Dashboard header bar */
    .oi-header {
        display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap;
        padding: 0.6rem 1rem;
        background: rgba(0,0,0,0.6);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 8px;
        margin-bottom: 0.8rem;
    }
    .oi-header .oi-title { font-size: 0.8rem; font-weight: 700; color: #00d4ff; }
    .oi-header .oi-spot { font-size: 1.2rem; font-weight: 700; color: #00ff88; }
    .oi-header .oi-metric { font-size: 0.75rem; color: #aaa; }
    .oi-header .oi-metric span { color: #fff; font-weight: 600; }

    /* Strike selector buttons */
    .strike-btn {
        display: inline-block; padding: 0.2rem 0.6rem; margin: 0.15rem;
        border-radius: 4px; font-size: 0.7rem; font-weight: 600; cursor: pointer;
        border: 1px solid rgba(255,255,255,0.15); color: #888;
        background: rgba(255,255,255,0.03);
    }
    .strike-btn.active-ce { background: rgba(255,68,68,0.25); color: #ff4444; border-color: #ff4444; }
    .strike-btn.active-pe { background: rgba(0,255,136,0.25); color: #00ff88; border-color: #00ff88; }
    .strike-btn.active-atm { background: rgba(0,212,255,0.25); color: #00d4ff; border-color: #00d4ff; }

    /* OI table mirror layout */
    .oi-full-table { width: 100%; border-collapse: collapse; font-size: 0.75rem; }
    .oi-full-table th {
        padding: 0.4rem 0.5rem; text-align: right; color: #00d4ff;
        border-bottom: 1px solid rgba(255,255,255,0.15); font-weight: 500;
    }
    .oi-full-table th.strike-col { text-align: center; }
    .oi-full-table td {
        padding: 0.35rem 0.5rem; text-align: right;
        border-bottom: 1px solid rgba(255,255,255,0.04); color: #ccc;
    }
    .oi-full-table td.strike-col {
        text-align: center; font-weight: 700; color: #fff;
        border-left: 1px solid rgba(255,255,255,0.1);
        border-right: 1px solid rgba(255,255,255,0.1);
        background: rgba(0,212,255,0.03);
    }
    .oi-full-table tr.atm-row { background: rgba(0,212,255,0.08); }
    .oi-full-table tr.atm-row td.strike-col { color: #00d4ff; }
    .oi-full-table tr.max-ce td { border-left: 2px solid #ff4444; }
    .oi-full-table tr.max-pe td:last-child { border-right: 2px solid #00ff88; }

    /* Insight panel */
    .insight-panel {
        display: flex; gap: 1.5rem; flex-wrap: wrap;
        padding: 0.8rem 1rem;
        background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.06);
        border-radius: 8px; margin-top: 0.8rem;
    }
    .insight-panel .insight-item .insight-label { font-size: 0.65rem; color: #888; text-transform: uppercase; letter-spacing: 1px; }
    .insight-panel .insight-item .insight-value { font-size: 1rem; font-weight: 700; margin-top: 0.15rem; }

    /* Hide Streamlit branding */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Helper Functions ─────────────────────────────────────────────────────────
def glass_card(content):
    return f'<div class="glass-card">{content}</div>'

def section_title(title):
    return f'<div class="section-title">{title}</div>'

def bias_badge(bias):
    cls = "bias-bullish" if bias == "BULLISH" else "bias-bearish" if bias == "BEARISH" else "bias-neutral"
    return f'<span class="bias-badge {cls}">{bias}</span>'

def delta_html(value, suffix=""):
    if value > 0:
        return f'<span class="metric-delta-up">+{value:.2f}{suffix}</span>'
    elif value < 0:
        return f'<span class="metric-delta-down">{value:.2f}{suffix}</span>'
    return f'<span style="color:#888">{value:.2f}{suffix}</span>'

def color_value(value, positive_good=True):
    if value > 0:
        cls = "highlight-green" if positive_good else "highlight-red"
    elif value < 0:
        cls = "highlight-red" if positive_good else "highlight-green"
    else:
        cls = ""
    return f'<span class="{cls}">{value:,.2f}</span>'

def format_cr(value):
    """Format value in crores."""
    try:
        v = float(str(value).replace(",", ""))
        if v >= 0:
            return f'<span class="highlight-green">+{v:,.2f} Cr</span>'
        else:
            return f'<span class="highlight-red">{v:,.2f} Cr</span>'
    except (ValueError, TypeError):
        return f'<span style="color:#888">{value}</span>'


# ── Data Loading ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_all_data():
    """Fetch all data with 5-min cache."""
    fetcher = NSEFetcher()

    nifty_chain = fetcher.get_option_chain("NIFTY")
    nifty_index = fetcher.get_index_data("NIFTY 50")
    sensex_index = fetcher.get_index_data("SENSEX")
    vix_data = fetcher.get_india_vix()
    fii_dii = fetcher.get_fii_dii_data()
    gift_nifty = fetcher.get_gift_nifty()
    nifty_futures = fetcher.get_nifty_futures()

    return {
        "nifty_chain": nifty_chain,
        "nifty_index": nifty_index,
        "sensex_index": sensex_index,
        "vix": vix_data,
        "fii_dii": fii_dii,
        "gift_nifty": gift_nifty,
        "nifty_futures": nifty_futures,
        "timestamp": datetime.now().strftime("%d %b %Y, %I:%M %p"),
    }


# ── Main App ─────────────────────────────────────────────────────────────────
def main():
    # Market status
    mkt_status, mkt_msg = get_market_status()
    status_colors = {
        "LIVE": "#00ff88",
        "PRE-MARKET": "#ffaa00",
        "PRE-OPEN": "#00d4ff",
        "CLOSED": "#ff4444",
    }
    status_color = status_colors.get(mkt_status, "#888")

    # Header
    hex_c = status_color.lstrip('#')
    r_val = int(hex_c[0:2], 16)
    g_val = int(hex_c[2:4], 16)
    b_val = int(hex_c[4:6], 16)
    rgba_bg = f"rgba({r_val},{g_val},{b_val},0.15)"
    now_str = datetime.now().strftime("%d %b %Y, %I:%M %p")

    hdr = '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">'
    hdr += '<div>'
    hdr += '<div style="font-size:1.4rem;font-weight:700;color:#00d4ff;">PRE-MARKET DERIVATIVES DASHBOARD</div>'
    hdr += '<div style="font-size:0.75rem;color:#666;margin-top:0.2rem;">NIFTY &middot; SENSEX &middot; India Derivatives</div>'
    hdr += '</div>'
    hdr += '<div style="text-align:right;">'
    hdr += '<div style="display:inline-block;padding:0.2rem 0.8rem;border-radius:12px;background:' + rgba_bg + ';border:1px solid ' + status_color + ';margin-bottom:0.3rem;">'
    hdr += '<span style="font-size:0.7rem;color:' + status_color + ';font-weight:600;">' + mkt_status + '</span>'
    hdr += '</div>'
    hdr += '<div style="font-size:0.7rem;color:#666;">' + mkt_msg + '</div>'
    hdr += '<div style="font-size:0.75rem;color:#aaa;margin-top:0.2rem;">' + now_str + '</div>'
    hdr += '</div></div>'

    st.markdown(glass_card(hdr), unsafe_allow_html=True)

    # Load data
    with st.spinner("Fetching live market data..."):
        data = load_all_data()

    nifty_chain = data["nifty_chain"]
    nifty_index = data["nifty_index"]
    vix_data = data["vix"]
    fii_dii = data["fii_dii"]
    gift_data = data["gift_nifty"]
    futures_data = data["nifty_futures"]

    # Extract spot price
    spot_price = 0
    prev_close = 0
    day_high = 0
    day_low = 0
    day_open = 0
    if nifty_index:
        spot_price = nifty_index.get("last", nifty_index.get("lastPrice", 0))
        prev_close = nifty_index.get("previousClose", 0)
        day_high = nifty_index.get("high", 0)
        day_low = nifty_index.get("low", 0)
        day_open = nifty_index.get("open", 0)
    elif nifty_chain:
        spot_price = nifty_chain.get("records", {}).get("underlyingValue", 0)

    # Fallback spot from option chain
    if not spot_price and nifty_chain:
        spot_price = nifty_chain.get("records", {}).get("underlyingValue", 0)

    # Run calculations
    straddle = calculate_straddle(nifty_chain, spot_price) if nifty_chain and spot_price else None
    pcr = calculate_pcr(nifty_chain) if nifty_chain else None
    synthetic = calculate_synthetic_futures(nifty_chain, spot_price) if nifty_chain and spot_price else None
    oi_analysis = analyze_open_interest(nifty_chain) if nifty_chain else None
    pivots = calculate_pivot_levels(day_high, day_low, prev_close) if day_high and day_low and prev_close else None
    vix_interp = interpret_vix(vix_data["current"], vix_data["previous_close"]) if vix_data else None
    market_bias = generate_market_bias(pcr, vix_data, oi_analysis, fii_dii)

    futures_price = futures_data.get("ltp", 0) if futures_data else 0
    if not futures_price and synthetic:
        futures_price = synthetic["synthetic_price"]
    basis = calculate_basis(futures_price, spot_price) if futures_price and spot_price else None
    max_pain = calculate_max_pain(nifty_chain) if nifty_chain else None

    # ── SECTION 1: MARKET SUMMARY ────────────────────────────────────────
    conf_color = "#00ff88" if market_bias["confidence"] == "High" else "#ffaa00" if market_bias["confidence"] == "Medium" else "#ff4444"
    gift_part = ""
    if gift_data:
        gift_part = '<div><div class="metric-label">GIFT Nifty</div><div style="font-size:1rem; color:#00d4ff;">' + f'{gift_data["price"]:,.2f}' + '</div></div>'

    reasons_parts = []
    for r in market_bias["reasons"]:
        reasons_parts.append('<div class="reason-item">' + str(r) + '</div>')
    reasons_joined = "".join(reasons_parts)

    s1 = '<div class="section-title">1. MARKET SUMMARY</div>'
    s1 += '<div style="display:flex;gap:2rem;align-items:center;flex-wrap:wrap;">'
    s1 += '<div><div class="metric-label">Overall Bias</div><div style="margin-top:0.3rem;">' + bias_badge(market_bias['bias']) + '</div></div>'
    s1 += '<div><div class="metric-label">Confidence</div><div class="metric-value" style="font-size:1.2rem;color:' + conf_color + ';">' + market_bias['confidence'] + '</div></div>'
    s1 += '<div><div class="metric-label">NIFTY Spot</div><div class="metric-value" style="color:#fff;">' + f'{spot_price:,.2f}' + '</div></div>'
    s1 += '<div><div class="metric-label">Prev Close</div><div style="font-size:1rem;color:#aaa;">' + f'{prev_close:,.2f}' + '</div></div>'
    s1 += gift_part
    s1 += '</div>'
    s1 += '<div style="margin-top:0.8rem;">' + reasons_joined + '</div>'

    st.markdown(glass_card(s1), unsafe_allow_html=True)

    # ── SECTION 2 & 3: FII/DII + VIX (side by side) ─────────────────────
    col_fii, col_vix = st.columns(2)

    with col_fii:
        fii_html = section_title("2. FII & DII DATA")
        if fii_dii:
            fii = fii_dii.get("fii", {})
            dii = fii_dii.get("dii", {})
            fii_html += f"""
            <table class="data-table">
                <tr><th>Participant</th><th>Buy (Cr)</th><th>Sell (Cr)</th><th>Net (Cr)</th></tr>
                <tr>
                    <td class="highlight-cyan">FII/FPI</td>
                    <td>{fii.get('buy_value', 'N/A')}</td>
                    <td>{fii.get('sell_value', 'N/A')}</td>
                    <td>{format_cr(fii.get('net_value', 0))}</td>
                </tr>
                <tr>
                    <td class="highlight-cyan">DII</td>
                    <td>{dii.get('buy_value', 'N/A')}</td>
                    <td>{dii.get('sell_value', 'N/A')}</td>
                    <td>{format_cr(dii.get('net_value', 0))}</td>
                </tr>
            </table>
            <div style="margin-top:0.6rem; font-size:0.75rem; color:#888;">
                Date: {fii.get('date', 'N/A')}
            </div>
            """
        else:
            fii_html += '<div style="color:#666; font-size:0.8rem;">FII/DII data unavailable — NSE may not have published yet</div>'
        st.markdown(glass_card(fii_html), unsafe_allow_html=True)

    with col_vix:
        vix_html = section_title("3. INDIA VIX")
        if vix_data and vix_interp:
            vix_val = vix_data["current"]
            vix_prev = vix_data["previous_close"]
            vix_chg = vix_interp["change_pct"]
            vix_color = "#ff4444" if vix_val > 20 else "#ffaa00" if vix_val > 15 else "#00ff88"
            vix_html += f"""
            <div style="display:flex; gap:2rem; align-items:flex-end;">
                <div>
                    <div class="metric-label">Current VIX</div>
                    <div class="metric-value" style="color:{vix_color};">{vix_val:.2f}</div>
                </div>
                <div>
                    <div class="metric-label">Previous</div>
                    <div style="font-size:1rem; color:#aaa;">{vix_prev:.2f}</div>
                </div>
                <div>
                    <div class="metric-label">Change</div>
                    <div>{delta_html(vix_chg, '%')}</div>
                </div>
            </div>
            <div style="margin-top:0.6rem;">
                <div style="font-size:0.75rem; color:#888;">Level: <span class="highlight-cyan">{vix_interp['level']}</span></div>
                <div style="font-size:0.75rem; color:#888; margin-top:0.2rem;">{vix_interp['trend']}</div>
                <div style="font-size:0.75rem; color:#ffaa00; margin-top:0.2rem;">{vix_interp['market_implication']}</div>
            </div>
            """
        else:
            vix_html += '<div style="color:#666; font-size:0.8rem;">VIX data unavailable</div>'
        st.markdown(glass_card(vix_html), unsafe_allow_html=True)

    # ── SECTION 4: OPEN INTEREST ANALYSIS ────────────────────────────────
    oi_html = section_title("4. OPEN INTEREST ANALYSIS — NIFTY")
    if oi_analysis:
        oi_html += '<div style="display:flex; gap:1.5rem; flex-wrap:wrap;">'

        # Highest Call OI (Resistance)
        oi_html += '<div style="flex:1; min-width:280px;">'
        oi_html += '<div class="metric-label" style="color:#ff4444;">HIGHEST CALL OI (Resistance)</div>'
        oi_html += '<table class="data-table"><tr><th>Strike</th><th>OI</th><th>OI Chg</th></tr>'
        for c in oi_analysis["highest_call_oi"][:5]:
            chg_cls = "highlight-red" if c["oi_change"] > 0 else "highlight-green"
            oi_html += f'<tr><td class="highlight-red">{c["strike"]:,.0f}</td><td>{c["oi"]:,}</td><td class="{chg_cls}">{c["oi_change"]:+,}</td></tr>'
        oi_html += '</table></div>'

        # Highest Put OI (Support)
        oi_html += '<div style="flex:1; min-width:280px;">'
        oi_html += '<div class="metric-label" style="color:#00ff88;">HIGHEST PUT OI (Support)</div>'
        oi_html += '<table class="data-table"><tr><th>Strike</th><th>OI</th><th>OI Chg</th></tr>'
        for p in oi_analysis["highest_put_oi"][:5]:
            chg_cls = "highlight-green" if p["oi_change"] > 0 else "highlight-red"
            oi_html += f'<tr><td class="highlight-green">{p["strike"]:,.0f}</td><td>{p["oi"]:,}</td><td class="{chg_cls}">{p["oi_change"]:+,}</td></tr>'
        oi_html += '</table></div>'

        oi_html += '</div>'

        # Support/Resistance zones
        oi_html += f"""
        <div style="margin-top:0.8rem; display:flex; gap:2rem;">
            <div>
                <span class="metric-label">Support Zone: </span>
                <span class="highlight-green">{' / '.join(f'{s:,.0f}' for s in oi_analysis['support_zone'])}</span>
            </div>
            <div>
                <span class="metric-label">Resistance Zone: </span>
                <span class="highlight-red">{' / '.join(f'{r:,.0f}' for r in oi_analysis['resistance_zone'])}</span>
            </div>
        </div>
        """
    else:
        oi_html += '<div style="color:#666; font-size:0.8rem;">Option chain data unavailable</div>'
    st.markdown(glass_card(oi_html), unsafe_allow_html=True)

    # ── LIVE OI BAR CHARTS ───────────────────────────────────────────────
    if nifty_chain and nifty_chain.get("records", {}).get("data"):
        records = nifty_chain["records"]["data"]
        oi_strikes = []
        call_oi_list = []
        put_oi_list = []
        call_oi_chg_list = []
        put_oi_chg_list = []

        for r in records:
            strike = r["strikePrice"]
            ce = r.get("CE")
            pe = r.get("PE")
            c_oi = ce.get("openInterest", 0) if ce else 0
            p_oi = pe.get("openInterest", 0) if pe else 0
            c_chg = ce.get("changeinOpenInterest", 0) if ce else 0
            p_chg = pe.get("changeinOpenInterest", 0) if pe else 0

            if c_oi > 0 or p_oi > 0:
                oi_strikes.append(strike)
                call_oi_list.append(c_oi)
                put_oi_list.append(p_oi)
                call_oi_chg_list.append(c_chg)
                put_oi_chg_list.append(p_chg)

        if oi_strikes:
            # Filter to +/- 15 strikes around ATM for clarity
            atm = min(oi_strikes, key=lambda x: abs(x - spot_price)) if spot_price else oi_strikes[len(oi_strikes) // 2]
            margin = 15
            atm_idx = oi_strikes.index(atm)
            lo = max(0, atm_idx - margin)
            hi = min(len(oi_strikes), atm_idx + margin + 1)

            f_strikes = oi_strikes[lo:hi]
            f_call_oi = call_oi_list[lo:hi]
            f_put_oi = put_oi_list[lo:hi]
            f_call_chg = call_oi_chg_list[lo:hi]
            f_put_chg = put_oi_chg_list[lo:hi]

            strike_labels = [str(int(s)) for s in f_strikes]

            # ── Chart 1: Total OI ────────────────────────────────────────
            st.markdown(glass_card(section_title("LIVE OI — TOTAL OPEN INTEREST")), unsafe_allow_html=True)

            fig_oi = go.Figure()
            fig_oi.add_trace(go.Bar(
                x=strike_labels, y=f_call_oi,
                name="Call OI", marker_color="#ff4444",
                opacity=0.85, text=[f"{v:,.0f}" for v in f_call_oi],
                textposition="outside", textfont=dict(size=8, color="#ff6666"),
            ))
            fig_oi.add_trace(go.Bar(
                x=strike_labels, y=f_put_oi,
                name="Put OI", marker_color="#00ff88",
                opacity=0.85, text=[f"{v:,.0f}" for v in f_put_oi],
                textposition="outside", textfont=dict(size=8, color="#66ffaa"),
            ))
            # ATM line
            if str(int(atm)) in strike_labels:
                atm_pos = strike_labels.index(str(int(atm)))
                fig_oi.add_vline(
                    x=atm_pos, line_dash="dash", line_color="#00d4ff", line_width=2,
                    annotation_text=f"ATM {int(atm)}", annotation_font_color="#00d4ff",
                    annotation_font_size=10,
                )

            fig_oi.update_layout(
                barmode="group",
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="JetBrains Mono, monospace", size=10, color="#aaa"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                            font=dict(size=10)),
                margin=dict(l=40, r=20, t=30, b=40),
                height=380,
                xaxis=dict(title="Strike Price", gridcolor="rgba(255,255,255,0.05)", tickangle=-45),
                yaxis=dict(title="Open Interest", gridcolor="rgba(255,255,255,0.05)"),
            )
            st.plotly_chart(fig_oi, use_container_width=True)

            # ── Chart 2: OI Change ───────────────────────────────────────
            st.markdown(glass_card(section_title("LIVE OI — CHANGE IN OPEN INTEREST")), unsafe_allow_html=True)

            fig_chg = go.Figure()

            # Color bars based on positive/negative change
            call_chg_colors = ["#ff4444" if v > 0 else "rgba(255,68,68,0.4)" for v in f_call_chg]
            put_chg_colors = ["#00ff88" if v > 0 else "rgba(0,255,136,0.4)" for v in f_put_chg]

            fig_chg.add_trace(go.Bar(
                x=strike_labels, y=f_call_chg,
                name="Call OI Change", marker_color=call_chg_colors,
                opacity=0.9,
            ))
            fig_chg.add_trace(go.Bar(
                x=strike_labels, y=f_put_chg,
                name="Put OI Change", marker_color=put_chg_colors,
                opacity=0.9,
            ))

            if str(int(atm)) in strike_labels:
                atm_pos = strike_labels.index(str(int(atm)))
                fig_chg.add_vline(
                    x=atm_pos, line_dash="dash", line_color="#00d4ff", line_width=2,
                    annotation_text=f"ATM {int(atm)}", annotation_font_color="#00d4ff",
                    annotation_font_size=10,
                )

            # Zero line
            fig_chg.add_hline(y=0, line_color="rgba(255,255,255,0.2)", line_width=1)

            fig_chg.update_layout(
                barmode="group",
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="JetBrains Mono, monospace", size=10, color="#aaa"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                            font=dict(size=10)),
                margin=dict(l=40, r=20, t=30, b=40),
                height=380,
                xaxis=dict(title="Strike Price", gridcolor="rgba(255,255,255,0.05)", tickangle=-45),
                yaxis=dict(title="OI Change", gridcolor="rgba(255,255,255,0.05)"),
            )
            st.plotly_chart(fig_chg, use_container_width=True)

    # ── SECTION 5 & 6: TECHNICAL LEVELS + PCR (side by side) ─────────────
    col_tech, col_pcr = st.columns(2)

    with col_tech:
        tech_html = section_title("5. TECHNICAL LEVELS — NIFTY")
        if pivots:
            tech_html += f"""
            <table class="data-table">
                <tr><th>Level</th><th>Value</th><th>Type</th></tr>
                <tr><td>R2</td><td class="highlight-red">{pivots['r2']:,.2f}</td><td style="color:#666">Strong Resistance</td></tr>
                <tr><td>R1</td><td class="highlight-red">{pivots['r1']:,.2f}</td><td style="color:#666">Resistance</td></tr>
                <tr><td>Pivot</td><td class="highlight-cyan">{pivots['pivot']:,.2f}</td><td style="color:#666">Pivot Point</td></tr>
                <tr><td>S1</td><td class="highlight-green">{pivots['s1']:,.2f}</td><td style="color:#666">Support</td></tr>
                <tr><td>S2</td><td class="highlight-green">{pivots['s2']:,.2f}</td><td style="color:#666">Strong Support</td></tr>
            </table>
            <div style="margin-top:0.6rem; font-size:0.75rem; color:#888;">
                Prev Day: H {day_high:,.2f} &middot; L {day_low:,.2f} &middot; C {prev_close:,.2f}
            </div>
            """
        else:
            tech_html += '<div style="color:#666; font-size:0.8rem;">Index OHLC data unavailable</div>'
        st.markdown(glass_card(tech_html), unsafe_allow_html=True)

    with col_pcr:
        pcr_html = section_title("6. PCR DATA")
        if pcr:
            pcr_val = pcr["pcr"]
            pcr_color = "#00ff88" if pcr_val > 1.1 else "#ff4444" if pcr_val < 0.8 else "#ffaa00"
            pcr_html += f"""
            <div style="display:flex; gap:2rem; align-items:flex-end;">
                <div>
                    <div class="metric-label">Current PCR (OI)</div>
                    <div class="metric-value" style="color:{pcr_color};">{pcr_val:.4f}</div>
                </div>
            </div>
            <div style="margin-top:0.6rem;">
                <div style="font-size:0.75rem; color:#888;">Total Call OI: <span style="color:#ccc">{pcr['total_call_oi']:,}</span></div>
                <div style="font-size:0.75rem; color:#888;">Total Put OI: <span style="color:#ccc">{pcr['total_put_oi']:,}</span></div>
                <div style="font-size:0.75rem; color:#ffaa00; margin-top:0.4rem;">{pcr['sentiment']}</div>
            </div>
            <div style="margin-top:0.5rem; font-size:0.7rem; color:#555;">
                Range: 0.80 (Oversold) — 1.30 (Overbought)
            </div>
            """
        else:
            pcr_html += '<div style="color:#666; font-size:0.8rem;">PCR data unavailable</div>'
        st.markdown(glass_card(pcr_html), unsafe_allow_html=True)

    # ── SECTION 7 & 8: STRADDLE + SYNTHETIC FUTURES (side by side) ───────
    col_str, col_syn = st.columns(2)

    with col_str:
        str_html = section_title("7. STRADDLE PRICING — NIFTY")
        if straddle:
            str_html += f"""
            <div style="display:flex; gap:1.5rem; flex-wrap:wrap;">
                <div>
                    <div class="metric-label">ATM Strike</div>
                    <div class="metric-value" style="color:#fff; font-size:1.4rem;">{straddle['atm_strike']:,.0f}</div>
                </div>
                <div>
                    <div class="metric-label">Straddle Price</div>
                    <div class="metric-value" style="color:#00d4ff; font-size:1.4rem;">{straddle['straddle_price']:,.2f}</div>
                </div>
            </div>
            <table class="data-table" style="margin-top:0.6rem;">
                <tr><th>Component</th><th>Premium</th></tr>
                <tr><td>CE @ {straddle['atm_strike']:,.0f}</td><td class="highlight-cyan">{straddle['ce_premium']:,.2f}</td></tr>
                <tr><td>PE @ {straddle['atm_strike']:,.0f}</td><td class="highlight-cyan">{straddle['pe_premium']:,.2f}</td></tr>
            </table>
            <div style="margin-top:0.6rem;">
                <div class="metric-label">Implied Move (x0.85)</div>
                <div style="font-size:1rem; color:#ffaa00;">&plusmn; {straddle['implied_move']:,.2f} pts</div>
            </div>
            <div style="margin-top:0.4rem; display:flex; gap:1.5rem;">
                <div>
                    <span class="metric-label">Upper: </span>
                    <span class="highlight-green">{straddle['upper_range']:,.2f}</span>
                </div>
                <div>
                    <span class="metric-label">Lower: </span>
                    <span class="highlight-red">{straddle['lower_range']:,.2f}</span>
                </div>
            </div>
            """
        else:
            str_html += '<div style="color:#666; font-size:0.8rem;">Straddle data unavailable — option chain may not be loaded</div>'
        st.markdown(glass_card(str_html), unsafe_allow_html=True)

    with col_syn:
        syn_html = section_title("8. SYNTHETIC FUTURES & BASIS")
        if synthetic:
            pd_color = "#00ff88" if synthetic["premium_discount"] > 0 else "#ff4444"
            pd_label = "Premium" if synthetic["premium_discount"] > 0 else "Discount"
            syn_html += f"""
            <table class="data-table">
                <tr><th>Parameter</th><th>Value</th></tr>
                <tr><td>Spot Price</td><td style="color:#fff">{synthetic['spot_price']:,.2f}</td></tr>
                <tr><td>Synthetic Futures</td><td class="highlight-cyan">{synthetic['synthetic_price']:,.2f}</td></tr>
                <tr><td>CE Premium (ATM)</td><td>{synthetic['ce_premium']:,.2f}</td></tr>
                <tr><td>PE Premium (ATM)</td><td>{synthetic['pe_premium']:,.2f}</td></tr>
                <tr><td>Prem/Disc</td><td style="color:{pd_color}">{synthetic['premium_discount']:+,.2f} ({pd_label})</td></tr>
            </table>
            """
        else:
            syn_html += '<div style="color:#666; font-size:0.8rem;">Synthetic futures data unavailable</div>'

        # Basis
        if basis:
            basis_color = "#00ff88" if basis["basis"] > 0 else "#ff4444"
            syn_html += f"""
            <div style="margin-top:1rem;">
                {section_title("9. FUTURES vs SPOT BASIS")}
                <div style="display:flex; gap:1.5rem;">
                    <div>
                        <div class="metric-label">Basis</div>
                        <div style="font-size:1.2rem; color:{basis_color};">{basis['basis']:+,.2f} pts</div>
                    </div>
                    <div>
                        <div class="metric-label">Basis %</div>
                        <div style="font-size:1rem; color:{basis_color};">{basis['basis_pct']:+.4f}%</div>
                    </div>
                </div>
                <div style="font-size:0.75rem; color:#888; margin-top:0.3rem;">{basis['interpretation']}</div>
            </div>
            """
        st.markdown(glass_card(syn_html), unsafe_allow_html=True)

    # ── SECTION 10: DAY RANGE PROJECTION ─────────────────────────────────
    range_html = section_title("10. DAY RANGE PROJECTION")
    if straddle:
        range_html += f"""
        <div style="display:flex; gap:3rem; flex-wrap:wrap;">
            <div>
                <div class="metric-label">NIFTY Expected Range</div>
                <div style="display:flex; gap:1rem; margin-top:0.3rem;">
                    <div>
                        <span style="font-size:0.7rem; color:#666;">LOW</span><br>
                        <span class="highlight-red" style="font-size:1.1rem;">{straddle['lower_range']:,.2f}</span>
                    </div>
                    <div style="color:#333; font-size:1.5rem; align-self:center;">—</div>
                    <div>
                        <span style="font-size:0.7rem; color:#666;">HIGH</span><br>
                        <span class="highlight-green" style="font-size:1.1rem;">{straddle['upper_range']:,.2f}</span>
                    </div>
                </div>
                <div style="font-size:0.7rem; color:#555; margin-top:0.3rem;">Based on ATM straddle implied move (&plusmn;{straddle['implied_move']:,.0f} pts)</div>
            </div>
        </div>
        """
    else:
        range_html += '<div style="color:#666; font-size:0.8rem;">Range projection unavailable</div>'
    st.markdown(glass_card(range_html), unsafe_allow_html=True)

    # ── SECTION 11: FINAL TRADING VIEW ───────────────────────────────────
    final_html = section_title("11. FINAL TRADING VIEW")
    bias_cls = "bias-bullish" if market_bias["bias"] == "BULLISH" else "bias-bearish" if market_bias["bias"] == "BEARISH" else "bias-neutral"

    strategy = ""
    if market_bias["bias"] == "BULLISH":
        strategy = "Bull Put Spread / Sell OTM Puts near support zone"
    elif market_bias["bias"] == "BEARISH":
        strategy = "Bear Call Spread / Sell OTM Calls near resistance zone"
    else:
        strategy = "Iron Condor / Short Strangle within support-resistance range"

    key_support = ""
    key_resistance = ""
    if oi_analysis:
        if oi_analysis["support_zone"]:
            key_support = f"{oi_analysis['support_zone'][0]:,.0f}"
        if oi_analysis["resistance_zone"]:
            key_resistance = f"{oi_analysis['resistance_zone'][0]:,.0f}"
    elif pivots:
        key_support = f"{pivots['s1']:,.2f}"
        key_resistance = f"{pivots['r1']:,.2f}"

    final_html += f"""
    <div style="display:flex; gap:2rem; flex-wrap:wrap;">
        <div style="flex:1; min-width:250px;">
            <div class="metric-label">Market Bias</div>
            <div style="margin-top:0.3rem;">{bias_badge(market_bias['bias'])}</div>
            <div style="margin-top:0.5rem;">
                <div class="metric-label">Confidence: <span style="color:#ffaa00;">{market_bias['confidence']}</span></div>
            </div>
        </div>
        <div style="flex:1; min-width:250px;">
            <div class="metric-label">Ideal Strategy</div>
            <div style="font-size:0.85rem; color:#00d4ff; margin-top:0.3rem;">{strategy}</div>
        </div>
        <div style="flex:1; min-width:250px;">
            <div class="metric-label">Key Levels</div>
            <div style="margin-top:0.3rem;">
                <span style="color:#00ff88;">Support: {key_support}</span>
                <span style="color:#444;"> | </span>
                <span style="color:#ff4444;">Resistance: {key_resistance}</span>
            </div>
        </div>
    </div>
    """

    if key_support and key_resistance:
        if market_bias["bias"] == "BULLISH":
            inv_text = "Close below " + key_support + " = Abandon bullish view"
        elif market_bias["bias"] == "BEARISH":
            inv_text = "Close above " + key_resistance + " = Abandon bearish view"
        else:
            inv_text = "Break of " + key_support + " or " + key_resistance + " = Trend emerging"

        final_html += '<div style="margin-top:0.8rem; padding:0.6rem; background:rgba(255,170,0,0.05); border:1px solid rgba(255,170,0,0.2); border-radius:8px;">'
        final_html += '<div style="font-size:0.75rem; color:#ffaa00;">INVALIDATION: ' + inv_text + '</div>'
        final_html += '</div>'

    st.markdown(glass_card(final_html), unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════
    # OI ANALYSIS DASHBOARD
    # ══════════════════════════════════════════════════════════════════════
    if nifty_chain and nifty_chain.get("records", {}).get("data"):
        all_records = nifty_chain["records"]["data"]

        # Build full chain data
        chain_data = []
        for r in all_records:
            strike = r["strikePrice"]
            ce = r.get("CE")
            pe = r.get("PE")
            ce_oi = ce.get("openInterest", 0) if ce else 0
            pe_oi = pe.get("openInterest", 0) if pe else 0
            ce_chg = ce.get("changeinOpenInterest", 0) if ce else 0
            pe_chg = pe.get("changeinOpenInterest", 0) if pe else 0
            ce_ltp = ce.get("lastPrice", 0) if ce else 0
            pe_ltp = pe.get("lastPrice", 0) if pe else 0
            ce_vol = ce.get("totalTradedVolume", 0) if ce else 0
            pe_vol = pe.get("totalTradedVolume", 0) if pe else 0
            if ce_oi > 0 or pe_oi > 0:
                chain_data.append({
                    "strike": strike, "ce_oi": ce_oi, "pe_oi": pe_oi,
                    "ce_chg": ce_chg, "pe_chg": pe_chg,
                    "ce_ltp": ce_ltp, "pe_ltp": pe_ltp,
                    "ce_vol": ce_vol, "pe_vol": pe_vol,
                    "pcr": round(pe_oi / ce_oi, 3) if ce_oi > 0 else 0,
                    "straddle_oi": ce_oi + pe_oi,
                    "straddle_chg": ce_chg + pe_chg,
                })

        if chain_data:
            atm_strike = min([d["strike"] for d in chain_data], key=lambda x: abs(x - spot_price)) if spot_price else chain_data[len(chain_data) // 2]["strike"]
            total_ce_oi = sum(d["ce_oi"] for d in chain_data)
            total_pe_oi = sum(d["pe_oi"] for d in chain_data)
            total_ce_chg = sum(d["ce_chg"] for d in chain_data)
            total_pe_chg = sum(d["pe_chg"] for d in chain_data)
            overall_pcr = round(total_pe_oi / total_ce_oi, 3) if total_ce_oi else 0
            max_ce_strike = max(chain_data, key=lambda d: d["ce_oi"])
            max_pe_strike = max(chain_data, key=lambda d: d["pe_oi"])

            def fmt_lakh(v):
                if abs(v) >= 100000:
                    return f"{v/100000:.2f}L"
                return f"{v:,.0f}"

            # ── OI HEADER BAR ────────────────────────────────────────────
            mp_str = f"{max_pain:,.0f}" if max_pain else "N/A"
            vix_str = f'{vix_data["current"]:.2f} ({vix_data["change"]:+.1f}%)' if vix_data else "N/A"
            vix_chg_color = "#ff4444" if vix_data and vix_data["change"] > 0 else "#00ff88"

            oi_hdr = '<div class="oi-header">'
            oi_hdr += '<div class="oi-title">NIFTY OPTION CHAIN</div>'
            oi_hdr += f'<div class="oi-spot">{spot_price:,.2f}</div>'
            oi_hdr += f'<div class="oi-metric">PCR <span>{overall_pcr:.3f}</span></div>'
            oi_hdr += f'<div class="oi-metric">MAX PAIN <span>{mp_str}</span></div>'
            oi_hdr += f'<div class="oi-metric">CALL OI <span style="color:#ff4444">{fmt_lakh(total_ce_oi)}</span></div>'
            oi_hdr += f'<div class="oi-metric">PUT OI <span style="color:#00ff88">{fmt_lakh(total_pe_oi)}</span></div>'
            oi_hdr += f'<div class="oi-metric">VIX <span style="color:{vix_chg_color}">{vix_str}</span></div>'
            oi_hdr += '</div>'

            # Summary bar
            oi_hdr += '<div style="display:flex;gap:1.5rem;flex-wrap:wrap;font-size:0.72rem;color:#888;margin-bottom:0.5rem;">'
            ce_chg_color = "#ff4444" if total_ce_chg > 0 else "#00ff88"
            pe_chg_color = "#00ff88" if total_pe_chg > 0 else "#ff4444"
            oi_hdr += f'<span>CE TOTAL OI: <span style="color:#fff">{fmt_lakh(total_ce_oi)}</span> OI CHG: <span style="color:{ce_chg_color}">{fmt_lakh(total_ce_chg)}</span></span>'
            oi_hdr += f'<span>PE TOTAL OI: <span style="color:#fff">{fmt_lakh(total_pe_oi)}</span> PE CHG: <span style="color:{pe_chg_color}">{fmt_lakh(total_pe_chg)}</span></span>'
            oi_hdr += f'<span>PCR: <span style="color:#ffaa00">{overall_pcr:.3f}</span></span>'
            oi_hdr += f'<span>SPOT: <span style="color:#fff">{spot_price:,.2f}</span></span>'
            oi_hdr += f'<span>MAX PAIN: <span style="color:#fff">{mp_str}</span></span>'
            oi_hdr += '</div>'

            st.markdown(glass_card(oi_hdr), unsafe_allow_html=True)

            # ── STRIKE SELECTOR + FILTERS ────────────────────────────────
            margin = 15
            all_strikes = [d["strike"] for d in chain_data]
            atm_idx = all_strikes.index(atm_strike) if atm_strike in all_strikes else len(all_strikes) // 2
            lo = max(0, atm_idx - margin)
            hi = min(len(all_strikes), atm_idx + margin + 1)
            visible = chain_data[lo:hi]
            visible_strikes = [d["strike"] for d in visible]

            col_filter1, col_filter2 = st.columns([3, 1])
            with col_filter1:
                num_strikes = st.select_slider("Strikes", options=[10, 15, 20, 25, 30], value=15, key="oi_strikes")
            with col_filter2:
                chart_view = st.selectbox("View", ["CE + PE Lines", "Straddle Combined"], key="oi_view")

            # Recalculate visible range with selected strike count
            half = num_strikes // 2
            lo = max(0, atm_idx - half)
            hi = min(len(all_strikes), atm_idx + half + 1)
            visible = chain_data[lo:hi]
            visible_strikes = [d["strike"] for d in visible]

            # Strike buttons as HTML
            btn_html = '<div style="margin-bottom:0.8rem;">'
            btn_html += '<div style="font-size:0.7rem;color:#666;margin-bottom:0.3rem;">OI BY STRIKE</div>'
            for d in visible:
                s = d["strike"]
                if s == atm_strike:
                    cls = "strike-btn active-atm"
                elif s == max_ce_strike["strike"]:
                    cls = "strike-btn active-ce"
                elif s == max_pe_strike["strike"]:
                    cls = "strike-btn active-pe"
                else:
                    cls = "strike-btn"
                btn_html += f'<span class="{cls}">{int(s)}</span>'
            btn_html += '</div>'
            st.markdown(btn_html, unsafe_allow_html=True)

            # ── LINE CHART ───────────────────────────────────────────────
            strike_labels = [str(int(s)) for s in visible_strikes]

            fig_lines = go.Figure()

            if chart_view == "CE + PE Lines":
                # CE OI line (solid, pink/red)
                fig_lines.add_trace(go.Scatter(
                    x=strike_labels,
                    y=[d["ce_oi"] for d in visible],
                    name="CE OI", mode="lines+markers",
                    line=dict(color="#ff4477", width=2.5),
                    marker=dict(size=5, color="#ff4477"),
                ))
                # PE OI line (solid, green)
                fig_lines.add_trace(go.Scatter(
                    x=strike_labels,
                    y=[d["pe_oi"] for d in visible],
                    name="PE OI", mode="lines+markers",
                    line=dict(color="#00ff88", width=2.5),
                    marker=dict(size=5, color="#00ff88"),
                ))
                # CE OI Change (dashed, pink)
                fig_lines.add_trace(go.Scatter(
                    x=strike_labels,
                    y=[d["ce_chg"] for d in visible],
                    name="CE OI Chg", mode="lines+markers",
                    line=dict(color="#ff4477", width=1.5, dash="dash"),
                    marker=dict(size=3, color="#ff4477"),
                    yaxis="y2",
                ))
                # PE OI Change (dashed, green)
                fig_lines.add_trace(go.Scatter(
                    x=strike_labels,
                    y=[d["pe_chg"] for d in visible],
                    name="PE OI Chg", mode="lines+markers",
                    line=dict(color="#00ff88", width=1.5, dash="dash"),
                    marker=dict(size=3, color="#00ff88"),
                    yaxis="y2",
                ))
            else:
                # Straddle combined view
                fig_lines.add_trace(go.Scatter(
                    x=strike_labels,
                    y=[d["straddle_oi"] for d in visible],
                    name="Straddle OI (CE+PE)", mode="lines+markers",
                    line=dict(color="#00d4ff", width=2.5),
                    marker=dict(size=5, color="#00d4ff"),
                ))
                fig_lines.add_trace(go.Scatter(
                    x=strike_labels,
                    y=[d["straddle_chg"] for d in visible],
                    name="Straddle OI Chg", mode="lines+markers",
                    line=dict(color="#ffaa00", width=1.5, dash="dash"),
                    marker=dict(size=3, color="#ffaa00"),
                    yaxis="y2",
                ))

            # ATM vertical line
            if str(int(atm_strike)) in strike_labels:
                atm_x = strike_labels.index(str(int(atm_strike)))
                fig_lines.add_vline(
                    x=atm_x, line_dash="dash", line_color="#00d4ff", line_width=2,
                    annotation_text=f"ATM {int(atm_strike)}", annotation_font_color="#00d4ff",
                    annotation_font_size=10,
                )

            # Max Pain vertical line
            if max_pain and str(int(max_pain)) in strike_labels:
                mp_x = strike_labels.index(str(int(max_pain)))
                fig_lines.add_vline(
                    x=mp_x, line_dash="dot", line_color="#ffaa00", line_width=1.5,
                    annotation_text=f"MaxPain {int(max_pain)}", annotation_font_color="#ffaa00",
                    annotation_font_size=9, annotation_position="bottom",
                )

            fig_lines.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="JetBrains Mono, monospace", size=10, color="#aaa"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=9)),
                margin=dict(l=50, r=50, t=30, b=40),
                height=420,
                xaxis=dict(title="Strike Price", gridcolor="rgba(255,255,255,0.05)", tickangle=-45),
                yaxis=dict(title="Open Interest", gridcolor="rgba(255,255,255,0.05)", side="left"),
                yaxis2=dict(title="OI Change", overlaying="y", side="right", gridcolor="rgba(255,255,255,0.03)"),
                hovermode="x unified",
            )
            st.plotly_chart(fig_lines, use_container_width=True, key="oi_line_chart")

            # ── FULL OPTION CHAIN TABLE (mirror layout) ──────────────────
            tbl = '<div style="max-height:450px; overflow-y:auto; border:1px solid rgba(255,255,255,0.06); border-radius:8px;">'
            tbl += '<table class="oi-full-table">'
            tbl += '<tr>'
            tbl += '<th>CE LTP</th><th>CE Vol</th><th>CE ΔOI</th><th>CE OI</th>'
            tbl += '<th class="strike-col">STRIKE</th>'
            tbl += '<th>PE OI</th><th>PE ΔOI</th><th>PE Vol</th><th>PE LTP</th>'
            tbl += '</tr>'

            for d in visible:
                s = d["strike"]
                row_cls = ""
                if s == atm_strike:
                    row_cls = ' class="atm-row"'
                elif s == max_ce_strike["strike"]:
                    row_cls = ' class="max-ce"'
                elif s == max_pe_strike["strike"]:
                    row_cls = ' class="max-pe"'

                ce_oi_style = ' style="color:#ff4444;font-weight:600"' if s == max_ce_strike["strike"] else ""
                pe_oi_style = ' style="color:#00ff88;font-weight:600"' if s == max_pe_strike["strike"] else ""
                ce_chg_cls = "highlight-red" if d["ce_chg"] > 0 else "highlight-green" if d["ce_chg"] < 0 else ""
                pe_chg_cls = "highlight-green" if d["pe_chg"] > 0 else "highlight-red" if d["pe_chg"] < 0 else ""

                atm_marker = " ◄" if s == atm_strike else ""

                tbl += f'<tr{row_cls}>'
                tbl += f'<td>{d["ce_ltp"]:,.2f}</td>'
                tbl += f'<td>{d["ce_vol"]:,}</td>'
                tbl += f'<td class="{ce_chg_cls}">{d["ce_chg"]:+,}</td>'
                tbl += f'<td{ce_oi_style}>{d["ce_oi"]:,}</td>'
                tbl += f'<td class="strike-col">{int(s):,}{atm_marker}</td>'
                tbl += f'<td{pe_oi_style}>{d["pe_oi"]:,}</td>'
                tbl += f'<td class="{pe_chg_cls}">{d["pe_chg"]:+,}</td>'
                tbl += f'<td>{d["pe_vol"]:,}</td>'
                tbl += f'<td>{d["pe_ltp"]:,.2f}</td>'
                tbl += '</tr>'

            tbl += '</table></div>'
            st.markdown(glass_card(tbl), unsafe_allow_html=True)

            # ── INSIGHT PANEL ────────────────────────────────────────────
            oi_imbalance = total_pe_oi - total_ce_oi
            if oi_imbalance > 0:
                signal_text = "PE HEAVY → BULLISH"
                signal_color = "#00ff88"
            else:
                signal_text = "CE HEAVY → BEARISH"
                signal_color = "#ff4444"

            insight = '<div class="insight-panel">'
            insight += '<div class="insight-item"><div class="insight-label">Resistance</div>'
            insight += f'<div class="insight-value" style="color:#ff4444">{int(max_ce_strike["strike"]):,} ({fmt_lakh(max_ce_strike["ce_oi"])})</div></div>'
            insight += '<div class="insight-item"><div class="insight-label">Support</div>'
            insight += f'<div class="insight-value" style="color:#00ff88">{int(max_pe_strike["strike"]):,} ({fmt_lakh(max_pe_strike["pe_oi"])})</div></div>'
            insight += '<div class="insight-item"><div class="insight-label">Max Pain</div>'
            insight += f'<div class="insight-value" style="color:#ffaa00">{mp_str}</div></div>'
            insight += '<div class="insight-item"><div class="insight-label">OI Signal</div>'
            insight += f'<div class="insight-value" style="color:{signal_color}">{signal_text}</div></div>'
            insight += '</div>'

            # CE/PE buildup zones
            ce_top2 = sorted(visible, key=lambda d: d["ce_oi"], reverse=True)[:2]
            pe_top2 = sorted(visible, key=lambda d: d["pe_oi"], reverse=True)[:2]
            insight += '<div style="margin-top:0.5rem; font-size:0.72rem; color:#888;">'
            insight += f'<div>CE OI Buildup: <span style="color:#ff4444">{int(ce_top2[0]["strike"]):,}–{int(ce_top2[1]["strike"]):,}</span> zone → Strong writing = Resistance ceiling</div>'
            insight += f'<div>PE OI Buildup: <span style="color:#00ff88">{int(pe_top2[0]["strike"]):,}–{int(pe_top2[1]["strike"]):,}</span> zone → Strong writing = Support floor</div>'
            insight += '</div>'

            st.markdown(glass_card(insight), unsafe_allow_html=True)

            # ── MULTI-STRIKE OI COMPARISON ───────────────────────────────
            st.markdown(glass_card(section_title("MULTI-STRIKE OI COMPARISON")), unsafe_allow_html=True)

            # Color palette for selected strikes
            STRIKE_COLORS = [
                "#ff4477", "#00ff88", "#00d4ff", "#ffaa00", "#ff6633",
                "#aa66ff", "#66ffcc", "#ff66aa", "#33ccff", "#ffff44",
            ]

            # Default: ATM ± 2 key strikes + max CE/PE
            default_strikes = set()
            default_strikes.add(atm_strike)
            if max_ce_strike:
                default_strikes.add(max_ce_strike["strike"])
            if max_pe_strike:
                default_strikes.add(max_pe_strike["strike"])
            # Add ATM ± 1-2 intervals
            for d in chain_data:
                if abs(d["strike"] - atm_strike) <= 200:
                    default_strikes.add(d["strike"])
                if len(default_strikes) >= 5:
                    break

            all_strike_opts = [int(d["strike"]) for d in chain_data]
            default_list = sorted([int(s) for s in default_strikes if int(s) in all_strike_opts])

            selected = st.multiselect(
                "Select strikes to compare",
                options=all_strike_opts,
                default=default_list[:6],
                key="multi_strike_select",
            )

            if selected:
                sel_data = [d for d in chain_data if int(d["strike"]) in selected]
                sel_data.sort(key=lambda d: d["strike"])

                # ── Chart 1: CE vs PE OI per selected strike (grouped bar) ──
                fig_ms = go.Figure()
                strike_labels = [str(int(d["strike"])) for d in sel_data]

                fig_ms.add_trace(go.Bar(
                    x=strike_labels,
                    y=[d["ce_oi"] for d in sel_data],
                    name="CE OI",
                    marker_color="#ff4477",
                    opacity=0.9,
                ))
                fig_ms.add_trace(go.Bar(
                    x=strike_labels,
                    y=[d["pe_oi"] for d in sel_data],
                    name="PE OI",
                    marker_color="#00ff88",
                    opacity=0.9,
                ))

                # ATM marker
                atm_label = str(int(atm_strike))
                if atm_label in strike_labels:
                    fig_ms.add_vline(
                        x=strike_labels.index(atm_label),
                        line_dash="dash", line_color="#00d4ff", line_width=2,
                        annotation_text=f"ATM {atm_label}",
                        annotation_font_color="#00d4ff", annotation_font_size=10,
                    )

                fig_ms.update_layout(
                    barmode="group",
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="JetBrains Mono, monospace", size=10, color="#aaa"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=9)),
                    margin=dict(l=50, r=20, t=30, b=40),
                    height=350,
                    xaxis=dict(title="Strike", gridcolor="rgba(255,255,255,0.05)"),
                    yaxis=dict(title="Open Interest", gridcolor="rgba(255,255,255,0.05)"),
                )
                st.plotly_chart(fig_ms, use_container_width=True, key="ms_bar")

                # ── Chart 2: Individual strike lines (CE solid, PE dashed) ──
                fig_lines2 = go.Figure()
                for i, d in enumerate(sel_data):
                    color = STRIKE_COLORS[i % len(STRIKE_COLORS)]
                    label = str(int(d["strike"]))
                    is_atm = d["strike"] == atm_strike

                    fig_lines2.add_trace(go.Bar(
                        x=["CE OI", "PE OI", "CE ΔOI", "PE ΔOI"],
                        y=[d["ce_oi"], d["pe_oi"], d["ce_chg"], d["pe_chg"]],
                        name=label + (" ◄ATM" if is_atm else ""),
                        marker_color=color,
                        opacity=0.85,
                    ))

                fig_lines2.update_layout(
                    barmode="group",
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="JetBrains Mono, monospace", size=10, color="#aaa"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(size=9)),
                    margin=dict(l=50, r=20, t=40, b=40),
                    height=350,
                    xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                    yaxis=dict(title="Value", gridcolor="rgba(255,255,255,0.05)"),
                )
                st.plotly_chart(fig_lines2, use_container_width=True, key="ms_compare")

                # ── Quick insight for selected strikes ───────────────────
                ms_insight = '<div style="display:flex;gap:1rem;flex-wrap:wrap;font-size:0.72rem;">'
                for i, d in enumerate(sel_data):
                    color = STRIKE_COLORS[i % len(STRIKE_COLORS)]
                    pcr_val = f"{d['pcr']:.2f}" if d['pcr'] else "∞"
                    ce_arrow = "▲" if d["ce_chg"] > 0 else "▼"
                    pe_arrow = "▲" if d["pe_chg"] > 0 else "▼"
                    atm_tag = " ◄ATM" if d["strike"] == atm_strike else ""
                    ms_insight += f'<div style="padding:0.4rem 0.6rem;background:rgba(255,255,255,0.03);border-left:3px solid {color};border-radius:4px;min-width:140px;">'
                    ms_insight += f'<div style="color:{color};font-weight:700;">{int(d["strike"]):,}{atm_tag}</div>'
                    ms_insight += f'<div style="color:#aaa;">CE: {d["ce_oi"]:,} <span style="color:{"#ff4444" if d["ce_chg"]>0 else "#00ff88"}">{ce_arrow}{abs(d["ce_chg"]):,}</span></div>'
                    ms_insight += f'<div style="color:#aaa;">PE: {d["pe_oi"]:,} <span style="color:{"#00ff88" if d["pe_chg"]>0 else "#ff4444"}">{pe_arrow}{abs(d["pe_chg"]):,}</span></div>'
                    ms_insight += f'<div style="color:#ffaa00;">PCR: {pcr_val}</div>'
                    ms_insight += '</div>'
                ms_insight += '</div>'
                st.markdown(glass_card(ms_insight), unsafe_allow_html=True)

    # ── Disclaimer ───────────────────────────────────────────────────────
    st.markdown("""
    <div class="disclaimer">
        This dashboard is for educational and informational purposes only. Not SEBI-registered investment advice.
        Derivatives trading involves substantial risk. Data sourced from Groww &amp; Yahoo Finance. Consult a SEBI-registered advisor.
    </div>
    """, unsafe_allow_html=True)

    # ── Sidebar: Refresh ─────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### Controls")
        if st.button("Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.markdown(f"**Cache TTL:** 5 min")
        st.markdown(f"**Last fetch:** {data['timestamp']}")


if __name__ == "__main__":
    main()
