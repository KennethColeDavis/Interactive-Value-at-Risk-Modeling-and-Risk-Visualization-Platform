import numpy as np
import pandas as pd
from scipy import stats
from dataclasses import dataclass


@dataclass
class VaRResult:
    """Holds VaR and CVaR outputs for a single method."""
    method:    str
    var_pct:   float
    var_usd:   float
    cvar_pct:  float
    cvar_usd:  float


def historical_var(
    returns: pd.Series,
    confidence: float,
    portfolio_value: float,
) -> VaRResult:
    """
    Non-parametric VaR from the empirical return distribution.
    No assumptions — uses actual observed returns directly.
    """
    alpha    = 1 - confidence
    var_pct  = np.percentile(returns, alpha * 100)
    cvar_pct = returns[returns <= var_pct].mean()

    return VaRResult(
        method        = "Historical",
        var_pct       = var_pct,
        var_usd       = abs(var_pct)  * portfolio_value,
        cvar_pct      = cvar_pct,
        cvar_usd      = abs(cvar_pct) * portfolio_value,
    )


def parametric_var(
    returns: pd.Series,
    confidence: float,
    portfolio_value: float,
) -> VaRResult:
    """
    Gaussian parametric VaR.
    Assumes returns are normally distributed; uses mu, sigma, and the Z-score.

    VaR  = mu + Z * sigma
    CVaR = mu - sigma * phi(Z) / alpha       (closed-form Expected Shortfall)
    """
    alpha    = 1 - confidence
    mu       = returns.mean()
    sigma    = returns.std()
    z        = stats.norm.ppf(alpha)

    var_pct  = mu + z * sigma
    cvar_pct = mu - sigma * stats.norm.pdf(z) / alpha

    return VaRResult(
        method        = "Parametric",
        var_pct       = var_pct,
        var_usd       = abs(var_pct)  * portfolio_value,
        cvar_pct      = cvar_pct,
        cvar_usd      = abs(cvar_pct) * portfolio_value,
    )


def monte_carlo_var(
    returns: pd.Series,
    confidence: float,
    portfolio_value: float,
    n_sims: int = 10_000,
    horizon: int = 1,
    seed: int = 42,
) -> tuple[VaRResult, np.ndarray]:
    """
    Monte Carlo VaR via Geometric Brownian Motion.
    Draws n_sims random returns from N(mu*horizon, sigma*sqrt(horizon)),
    then takes the empirical percentile of simulated outcomes.

    Returns the VaRResult and the raw simulated array (useful for plotting).
    """
    alpha     = 1 - confidence
    mu        = returns.mean()
    sigma     = returns.std()

    rng       = np.random.default_rng(seed)
    simulated = rng.normal(mu * horizon, sigma * np.sqrt(horizon), n_sims)

    var_pct   = np.percentile(simulated, alpha * 100)
    cvar_pct  = simulated[simulated <= var_pct].mean()

    result = VaRResult(
        method        = "Monte Carlo",
        var_pct       = var_pct,
        var_usd       = abs(var_pct)  * portfolio_value,
        cvar_pct      = cvar_pct,
        cvar_usd      = abs(cvar_pct) * portfolio_value,
    )
    return result, simulated


def run_all(
    returns: pd.Series,
    confidence: float,
    portfolio_value: float,
    n_sims: int = 10_000,
    horizon: int = 1,
    seed: int = 42,
) -> tuple[list[VaRResult], np.ndarray]:
    """
    Run all three VaR methods and return results as a list of VaRResult objects
    plus the Monte Carlo simulated array.

    Usage
    -----
    results, mc_sims = run_all(port_returns, confidence=0.95, portfolio_value=100_000)
    summary_df       = results_to_dataframe(results)
    """
    hist = historical_var(returns, confidence, portfolio_value)
    para = parametric_var(returns, confidence, portfolio_value)
    mc, simulated = monte_carlo_var(returns, confidence, portfolio_value, n_sims, horizon, seed)

    return [hist, para, mc], simulated


def results_to_dataframe(results: list[VaRResult]) -> pd.DataFrame:
    """Convert a list of VaRResult objects into a clean summary DataFrame."""
    rows = [
        {
            "Method"  : r.method,
            "VaR (%)" : f"{r.var_pct:.3%}",
            "VaR ($)" : f"${r.var_usd:,.0f}",
            "CVaR ($)": f"${r.cvar_usd:,.0f}",
        }
        for r in results
    ]
    return pd.DataFrame(rows).set_index("Method")
