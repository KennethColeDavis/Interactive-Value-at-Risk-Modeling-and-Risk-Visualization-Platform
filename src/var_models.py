"""
var_models.py

All three VaR calculation methods for the portfolio risk application:
1. Historical VaR
2. Parametric (Gaussian) VaR
3. Monte Carlo VaR
"""

import numpy as np
import pandas as pd
from scipy import stats


# ── Holding period scaling ─────────────────────────────────────────────────
HOLDING_PERIODS = {
    "1d":  1,
    "5d":  5,
    "10d": 10,
}

CONFIDENCE_LEVELS = {
    "90": 0.90,
    "95": 0.95,
    "99": 0.99,
}


def _validate_inputs(port_returns: pd.Series, confidence: float, holding_period: int):
    if len(port_returns) < 30:
        raise ValueError(f"Insufficient return data: {len(port_returns)} observations (minimum 30 required).")
    if not (0 < confidence < 1):
        raise ValueError(f"Confidence must be between 0 and 1, got {confidence}.")
    if holding_period not in [1, 5, 10]:
        raise ValueError(f"Holding period must be 1, 5, or 10 days, got {holding_period}.")


def _scale_to_holding_period(var_1d: float, cvar_1d: float, holding_period: int) -> tuple[float, float]:
    scale = np.sqrt(holding_period)
    return var_1d * scale, cvar_1d * scale


def _build_result(
    method: str,
    var_pct: float,
    cvar_pct: float,
    portfolio_value: float,
    holding_period: int,
    confidence: float,
    extra: dict = None,
) -> dict:
    
    var_usd  = abs(var_pct)  * portfolio_value
    cvar_usd = abs(cvar_pct) * portfolio_value

    result = {
        "method":          method,
        "confidence":      confidence,
        "confidence_pct":  f"{confidence * 100:.0f}%",
        "holding_period":  holding_period,
        "portfolio_value": portfolio_value,
        # Percentage-based (negative = loss threshold)
        "var_pct":         round(var_pct,  6),
        "cvar_pct":        round(cvar_pct, 6),
        # Display-formatted
        "var_pct_fmt":     f"{var_pct:.3%}",
        "cvar_pct_fmt":    f"{cvar_pct:.3%}",
        # Dollar-based (positive = dollar loss)
        "var_usd":         round(var_usd,  2),
        "cvar_usd":        round(cvar_usd, 2),
        "var_usd_fmt":     f"${var_usd:,.2f}",
        "cvar_usd_fmt":    f"${cvar_usd:,.2f}",
    }

    if extra:
        result.update(extra)

    return result


# 1. Historical VaR

def historical_var(
    port_returns: pd.Series,
    portfolio_value: float,
    confidence: float = 0.95,
    holding_period: int = 1,
) -> dict:

    _validate_inputs(port_returns, confidence, holding_period)

    alpha   = 1 - confidence
    returns = port_returns.values

    # 1-day VaR and CVaR
    var_1d  = np.percentile(returns, alpha * 100)
    cvar_1d = returns[returns <= var_1d].mean()

    # Scale to holding period
    var_pct, cvar_pct = _scale_to_holding_period(var_1d, cvar_1d, holding_period)

    return _build_result(
        method="Historical",
        var_pct=var_pct,
        cvar_pct=cvar_pct,
        portfolio_value=portfolio_value,
        holding_period=holding_period,
        confidence=confidence,
        extra={
            "n_observations": len(returns),
            "return_series":  returns.tolist(),   # for charting
        }
    )


# 2. Parametric (Gaussian) VaR

def parametric_var(
    port_returns: pd.Series,
    portfolio_value: float,
    confidence: float = 0.95,
    holding_period: int = 1,
) -> dict:
    _validate_inputs(port_returns, confidence, holding_period)

    alpha  = 1 - confidence
    returns = port_returns.values

    mu    = returns.mean()
    sigma = returns.std(ddof=1)
    z     = stats.norm.ppf(alpha)

    # 1-day VaR and CVaR
    var_1d  = mu + z * sigma
    cvar_1d = mu - sigma * stats.norm.pdf(z) / alpha

    # Scale to holding period
    var_pct, cvar_pct = _scale_to_holding_period(var_1d, cvar_1d, holding_period)
    jb_stat, jb_pval = stats.jarque_bera(returns)

    return _build_result(
        method="Parametric (Gaussian)",
        var_pct=var_pct,
        cvar_pct=cvar_pct,
        portfolio_value=portfolio_value,
        holding_period=holding_period,
        confidence=confidence,
        extra={
            "mean_daily_return": round(float(mu), 6),
            "daily_volatility":  round(float(sigma), 6),
            "z_score":           round(float(z), 4),
            "normality_pvalue":  round(float(jb_pval), 4),
            "normality_warning": jb_pval < 0.05,   # True = returns may not be normal
        }
    )


# 3. Monte Carlo VaR

def monte_carlo_var(
    port_returns: pd.Series,
    portfolio_value: float,
    confidence: float = 0.95,
    holding_period: int = 1,
    n_simulations: int = 10_000,
    random_seed: int = 42,
) -> dict:

    _validate_inputs(port_returns, confidence, holding_period)

    alpha   = 1 - confidence
    returns = port_returns.values

    mu    = returns.mean()
    sigma = returns.std(ddof=1)

    np.random.seed(random_seed)
    simulated = np.random.normal(
        loc   = mu    * holding_period,
        scale = sigma * np.sqrt(holding_period),
        size  = n_simulations,
    )

    var_pct  = np.percentile(simulated, alpha * 100)
    cvar_pct = simulated[simulated <= var_pct].mean()

    return _build_result(
        method="Monte Carlo",
        var_pct=var_pct,
        cvar_pct=cvar_pct,
        portfolio_value=portfolio_value,
        holding_period=holding_period,
        confidence=confidence,
        extra={
            "n_simulations":    n_simulations,
            "simulated_returns": simulated.tolist(),   # for charting
            "mean_daily_return": round(float(mu), 6),
            "daily_volatility":  round(float(sigma), 6),
        }
    )


# 4. Run all three methods together

def compute_all_var(
    port_returns: pd.Series,
    portfolio_value: float,
    confidence: float = 0.95,
    holding_period: int = 1,
    n_simulations: int = 10_000,
) -> dict:

    hist = historical_var(port_returns, portfolio_value, confidence, holding_period)
    para = parametric_var(port_returns, portfolio_value, confidence, holding_period)
    mc   = monte_carlo_var(port_returns, portfolio_value, confidence, holding_period, n_simulations)

    summary = pd.DataFrame([
        {
            "Method":        r["method"],
            "VaR (%)":       r["var_pct_fmt"],
            "VaR ($)":       r["var_usd_fmt"],
            "CVaR / ES ($)": r["cvar_usd_fmt"],
        }
        for r in [hist, para, mc]
    ]).set_index("Method")

    return {
        "historical":  hist,
        "parametric":  para,
        "monte_carlo": mc,
        "summary":     summary,
    }
