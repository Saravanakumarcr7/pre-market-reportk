import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, time as dtime
from data_fetcher import NSEFetcher
from calculations import (
    calculate_straddle, calculate_pcr, calculate_synthetic_futures,
    calculate_pivot_levels, analyze_open_interest, interpret_vix,
    generate_market_bias, calculate_basis,
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
    sensex_index = fetcher.get_index_data("NIFTY FINANCIAL SERVICES")  # fallback
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
    with st.spinner("Fetching live data from NSE..."):
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
            call_chg_colors = ["#ff4444" if v > 0 else "#ff444466" for v in f_call_chg]
            put_chg_colors = ["#00ff88" if v > 0 else "#00ff8866" for v in f_put_chg]

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
        final_html += f"""
        <div style="margin-top:0.8rem; padding:0.6rem; background:rgba(255,170,0,0.05); border:1px solid rgba(255,170,0,0.2); border-radius:8px;">
            <div style="font-size:0.75rem; color:#ffaa00;">
                INVALIDATION: {'Close below ' + key_support + ' = Abandon bullish view' if market_bias['bias'] == 'BULLISH' else 'Close above ' + key_resistance + ' = Abandon bearish view' if market_bias['bias'] == 'BEARISH' else 'Break of ' + key_support + ' or ' + key_resistance + ' = Trend emerging'}
            </div>
        </div>
        """

    st.markdown(glass_card(final_html), unsafe_allow_html=True)

    # ── Disclaimer ───────────────────────────────────────────────────────
    st.markdown("""
    <div class="disclaimer">
        This dashboard is for educational and informational purposes only. Not SEBI-registered investment advice.
        Derivatives trading involves substantial risk. Data sourced from NSE India. Consult a SEBI-registered advisor.
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
