"""All derivative calculations: straddle, PCR, synthetic futures, pivots, OI analysis."""


def find_atm_strike(records, spot_price):
    """Find the At-The-Money strike closest to spot price."""
    strikes = set()
    for r in records:
        strikes.add(r["strikePrice"])
    if not strikes:
        return None
    return min(strikes, key=lambda x: abs(x - spot_price))


def calculate_straddle(option_chain_data, spot_price):
    """
    Calculate ATM straddle price from option chain.
    Returns: (atm_strike, ce_premium, pe_premium, straddle_price, implied_move)
    """
    if not option_chain_data:
        return None

    records = option_chain_data.get("records", {}).get("data", [])
    if not records:
        return None

    atm_strike = find_atm_strike(records, spot_price)
    if atm_strike is None:
        return None

    ce_premium = 0
    pe_premium = 0

    for r in records:
        if r["strikePrice"] == atm_strike:
            ce_data = r.get("CE")
            pe_data = r.get("PE")
            if ce_data:
                ce_premium = ce_data.get("lastPrice", 0)
            if pe_data:
                pe_premium = pe_data.get("lastPrice", 0)

    straddle_price = ce_premium + pe_premium
    implied_move = round(straddle_price * 0.85, 2)

    return {
        "atm_strike": atm_strike,
        "ce_premium": ce_premium,
        "pe_premium": pe_premium,
        "straddle_price": round(straddle_price, 2),
        "implied_move": implied_move,
        "upper_range": round(spot_price + implied_move, 2),
        "lower_range": round(spot_price - implied_move, 2),
    }


def calculate_pcr(option_chain_data):
    """
    Calculate Put-Call Ratio from option chain OI data.
    PCR = Total Put OI / Total Call OI
    """
    if not option_chain_data:
        return None

    records = option_chain_data.get("records", {}).get("data", [])
    total_call_oi = 0
    total_put_oi = 0

    for r in records:
        ce = r.get("CE")
        pe = r.get("PE")
        if ce:
            total_call_oi += ce.get("openInterest", 0)
        if pe:
            total_put_oi += pe.get("openInterest", 0)

    if total_call_oi == 0:
        return None

    pcr = total_put_oi / total_call_oi

    if pcr > 1.3:
        sentiment = "Overbought — Extreme bullish positioning"
    elif pcr > 1.1:
        sentiment = "Bullish — Put writers dominating"
    elif pcr > 0.9:
        sentiment = "Neutral — Balanced market"
    elif pcr > 0.7:
        sentiment = "Bearish — Call writers dominating"
    else:
        sentiment = "Oversold — Extreme bearish positioning"

    return {
        "pcr": round(pcr, 4),
        "total_call_oi": total_call_oi,
        "total_put_oi": total_put_oi,
        "sentiment": sentiment,
    }


def calculate_synthetic_futures(option_chain_data, spot_price):
    """
    Synthetic Futures Price = ATM Strike + CE Premium - PE Premium
    """
    if not option_chain_data:
        return None

    records = option_chain_data.get("records", {}).get("data", [])
    atm_strike = find_atm_strike(records, spot_price)
    if atm_strike is None:
        return None

    ce_premium = 0
    pe_premium = 0

    for r in records:
        if r["strikePrice"] == atm_strike:
            ce = r.get("CE")
            pe = r.get("PE")
            if ce:
                ce_premium = ce.get("lastPrice", 0)
            if pe:
                pe_premium = pe.get("lastPrice", 0)

    synthetic_price = atm_strike + ce_premium - pe_premium

    return {
        "synthetic_price": round(synthetic_price, 2),
        "atm_strike": atm_strike,
        "ce_premium": ce_premium,
        "pe_premium": pe_premium,
        "spot_price": spot_price,
        "premium_discount": round(synthetic_price - spot_price, 2),
    }


def calculate_pivot_levels(high, low, close):
    """
    Standard Pivot Point calculation.
    Returns pivot, S1, S2, R1, R2.
    """
    pivot = (high + low + close) / 3
    s1 = 2 * pivot - high
    s2 = pivot - (high - low)
    r1 = 2 * pivot - low
    r2 = pivot + (high - low)

    return {
        "pivot": round(pivot, 2),
        "s1": round(s1, 2),
        "s2": round(s2, 2),
        "r1": round(r1, 2),
        "r2": round(r2, 2),
    }


def analyze_open_interest(option_chain_data, top_n=5):
    """
    Analyze OI data to find:
    - Highest Call OI strikes (resistance)
    - Highest Put OI strikes (support)
    - Biggest OI changes
    """
    if not option_chain_data:
        return None

    records = option_chain_data.get("records", {}).get("data", [])

    call_oi_data = []
    put_oi_data = []

    for r in records:
        strike = r["strikePrice"]
        ce = r.get("CE")
        pe = r.get("PE")

        if ce and ce.get("openInterest", 0) > 0:
            call_oi_data.append({
                "strike": strike,
                "oi": ce.get("openInterest", 0),
                "oi_change": ce.get("changeinOpenInterest", 0),
                "volume": ce.get("totalTradedVolume", 0),
                "ltp": ce.get("lastPrice", 0),
            })

        if pe and pe.get("openInterest", 0) > 0:
            put_oi_data.append({
                "strike": strike,
                "oi": pe.get("openInterest", 0),
                "oi_change": pe.get("changeinOpenInterest", 0),
                "volume": pe.get("totalTradedVolume", 0),
                "ltp": pe.get("lastPrice", 0),
            })

    # Sort by OI descending
    call_oi_data.sort(key=lambda x: x["oi"], reverse=True)
    put_oi_data.sort(key=lambda x: x["oi"], reverse=True)

    # Sort by OI change for biggest changes
    call_oi_change = sorted(call_oi_data, key=lambda x: abs(x["oi_change"]), reverse=True)
    put_oi_change = sorted(put_oi_data, key=lambda x: abs(x["oi_change"]), reverse=True)

    highest_call_oi = call_oi_data[:top_n] if call_oi_data else []
    highest_put_oi = put_oi_data[:top_n] if put_oi_data else []

    # Determine support and resistance zones
    resistance_zone = [c["strike"] for c in highest_call_oi[:2]] if highest_call_oi else []
    support_zone = [p["strike"] for p in highest_put_oi[:2]] if highest_put_oi else []

    return {
        "highest_call_oi": highest_call_oi,
        "highest_put_oi": highest_put_oi,
        "biggest_call_oi_change": call_oi_change[:3] if call_oi_change else [],
        "biggest_put_oi_change": put_oi_change[:3] if put_oi_change else [],
        "resistance_zone": resistance_zone,
        "support_zone": support_zone,
    }


def calculate_max_pain(option_chain_data):
    """Calculate Max Pain strike where total loss for option buyers is maximum."""
    if not option_chain_data:
        return None
    records = option_chain_data.get("records", {}).get("data", [])
    strikes = []
    for r in records:
        ce = r.get("CE")
        pe = r.get("PE")
        if ce or pe:
            strikes.append({
                "strike": r["strikePrice"],
                "ce_oi": ce.get("openInterest", 0) if ce else 0,
                "pe_oi": pe.get("openInterest", 0) if pe else 0,
            })
    if not strikes:
        return None

    min_pain = float("inf")
    max_pain_strike = 0
    for target in strikes:
        total_pain = 0
        for s in strikes:
            # CE buyers lose if strike < target
            if s["strike"] < target["strike"]:
                total_pain += s["ce_oi"] * (target["strike"] - s["strike"])
            # PE buyers lose if strike > target
            if s["strike"] > target["strike"]:
                total_pain += s["pe_oi"] * (s["strike"] - target["strike"])
        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = target["strike"]
    return max_pain_strike


def interpret_vix(current_vix, prev_vix):
    """Interpret India VIX reading."""
    change_pct = ((current_vix - prev_vix) / prev_vix * 100) if prev_vix else 0

    if current_vix > 25:
        level = "HIGH"
        desc = "Extreme fear / Volatility expansion expected"
    elif current_vix > 18:
        level = "ELEVATED"
        desc = "Above normal — Trending moves likely"
    elif current_vix > 13:
        level = "NORMAL"
        desc = "Stable market — Range-bound conditions"
    else:
        level = "LOW"
        desc = "Complacency — Potential for sudden spike"

    if change_pct > 5:
        trend = "Rising VIX — Fear increasing, premium expansion"
        market_imp = "Volatility expansion — Avoid naked option selling"
    elif change_pct < -5:
        trend = "Falling VIX — Stability returning, premium decay"
        market_imp = "Premium decay — Favorable for option sellers"
    else:
        trend = "VIX stable — No major shift in sentiment"
        market_imp = "Range-bound conditions likely"

    return {
        "level": level,
        "description": desc,
        "change_pct": round(change_pct, 2),
        "trend": trend,
        "market_implication": market_imp,
    }


def generate_market_bias(pcr_data, vix_data, oi_data, fii_data):
    """Auto-generate market bias from all signals."""
    score = 0  # Positive = bullish, Negative = bearish
    reasons = []

    # PCR signal
    if pcr_data:
        pcr = pcr_data["pcr"]
        if pcr > 1.1:
            score += 2
            reasons.append(f"PCR at {pcr:.2f} — Put heavy, supports bulls")
        elif pcr < 0.8:
            score -= 2
            reasons.append(f"PCR at {pcr:.2f} — Call heavy, bears in control")
        else:
            reasons.append(f"PCR at {pcr:.2f} — Neutral zone")

    # VIX signal
    if vix_data:
        vix_val = vix_data.get("current", 0)
        vix_change = vix_data.get("change", 0)
        if isinstance(vix_change, str):
            try:
                vix_change = float(vix_change)
            except ValueError:
                vix_change = 0
        if vix_change < -5:
            score += 1
            reasons.append(f"VIX falling {vix_change:.1f}% — Fear subsiding")
        elif vix_change > 5:
            score -= 1
            reasons.append(f"VIX rising {vix_change:.1f}% — Fear increasing")

    # OI signal
    if oi_data and oi_data.get("resistance_zone") and oi_data.get("support_zone"):
        reasons.append(
            f"OI Support: {oi_data['support_zone']} | Resistance: {oi_data['resistance_zone']}"
        )

    # FII signal
    if fii_data and fii_data.get("fii"):
        net = fii_data["fii"].get("net_value", 0)
        if isinstance(net, str):
            try:
                net = float(net.replace(",", ""))
            except ValueError:
                net = 0
        if net > 0:
            score += 1
            reasons.append(f"FII Net Buyers: +Rs {abs(net):,.0f} Cr")
        elif net < 0:
            score -= 1
            reasons.append(f"FII Net Sellers: -Rs {abs(net):,.0f} Cr")

    if score >= 2:
        bias = "BULLISH"
        confidence = "High" if score >= 3 else "Medium"
    elif score <= -2:
        bias = "BEARISH"
        confidence = "High" if score <= -3 else "Medium"
    else:
        bias = "NEUTRAL"
        confidence = "Low" if score == 0 else "Medium"

    return {
        "bias": bias,
        "confidence": confidence,
        "score": score,
        "reasons": reasons[:4],
    }


def calculate_basis(futures_price, spot_price):
    """Calculate Futures - Spot basis."""
    if not futures_price or not spot_price:
        return None

    basis = futures_price - spot_price
    basis_pct = (basis / spot_price) * 100

    if basis > 0:
        interpretation = "Positive basis (Premium) — Mildly Bullish"
    elif basis < 0:
        interpretation = "Negative basis (Discount) — Bearish sentiment"
    else:
        interpretation = "Flat basis — No directional cue"

    return {
        "basis": round(basis, 2),
        "basis_pct": round(basis_pct, 4),
        "interpretation": interpretation,
    }
