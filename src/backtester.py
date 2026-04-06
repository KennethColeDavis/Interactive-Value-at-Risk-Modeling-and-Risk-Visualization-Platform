"""
backtester.py
Rolling-window VaR backtest
 
- For each day t in the test period:
  1. Estimate VaR using the preceding window of trading days
  2. Record whether the actual return on day t+1 violated that VaR
- Two formal statistical tests:
  - Kupiec POF (proportion of failures)
  - Christoffersen interval forecast test (violation independence)
"""
 
import numpy as np
import pandas as pd
from scipy import stats
 
 
WINDOW = 252  # estimation window in trading days
 
 
def _historical_var_fast(returns, alpha):
    return np.percentile(returns, alpha * 100)
 
 
def _parametric_var_fast(returns, alpha):
    mu    = returns.mean()
    sigma = returns.std(ddof=1)
    z     = stats.norm.ppf(alpha)
    return mu + z * sigma
 
 
def _mc_var_fast(returns, alpha, n_sims=5000, seed=42):
    mu    = returns.mean()
    sigma = returns.std(ddof=1)
    np.random.seed(seed)
    sims = np.random.normal(mu, sigma, n_sims)
    return np.percentile(sims, alpha * 100)
 
 
def rolling_backtest(port_returns: pd.Series, confidence: float = 0.95, window: int = WINDOW) -> dict:
    alpha   = 1 - confidence
    returns = port_returns.values
    dates   = port_returns.index
 
    n_total = len(returns)
    if n_total < window + 30:
        raise ValueError(
            f"Insufficient data for rolling backtest. Need at least {window + 30} observations, "
            f"got {n_total}. Use a longer lookback window."
        )
 
    test_dates      = []
    actual_returns  = []
    hist_vars, para_vars, mc_vars = [], [], []
 
    for t in range(window, n_total):
        window_returns = returns[t - window: t]
        actual_r       = returns[t]
 
        hist_vars.append(_historical_var_fast(window_returns, alpha))
        para_vars.append(_parametric_var_fast(window_returns, alpha))
        mc_vars.append(_mc_var_fast(window_returns, alpha))
 
        actual_returns.append(float(actual_r))
        test_dates.append(dates[t].strftime("%Y-%m-%d") if hasattr(dates[t], "strftime") else str(dates[t]))
 
    actual_arr = np.array(actual_returns)
    n_test     = len(actual_arr)
 
    results = {}
    for method_key, var_series in [
        ("historical", hist_vars),
        ("parametric", para_vars),
        ("monte_carlo", mc_vars),
    ]:
        var_arr    = np.array(var_series)
        violations = (actual_arr < var_arr).astype(int)
 
        results[method_key] = {
            "var_series":         var_arr.tolist(),
            "violations":         violations.tolist(),
            "n_violations":       int(violations.sum()),
            "violation_rate":     round(float(violations.mean()), 4),
            "expected_rate":      round(alpha, 4),
            "kupiec":             _kupiec_test(violations, alpha),
            "christoffersen":     _christoffersen_test(violations),
        }
 
    return {
        "dates":                test_dates,
        "actual_returns":       actual_arr.tolist(),
        "results":              results,
        "n_observations":       n_test,
        "expected_violations":  round(n_test * alpha),
        "confidence":           confidence,
        "window":               window,
    }
 
 
def _kupiec_test(violations: np.ndarray, alpha: float) -> dict:
    n  = len(violations)
    x  = violations.sum()
    p  = alpha
    p_hat = x / n if x > 0 else 1e-10
 
    if x == 0 or x == n:
        return {
            "statistic": None,
            "pvalue":    None,
            "passed":    x == 0,
            "note":      "No violations — cannot compute LR statistic.",
        }
 
    lr = -2 * (
        x * np.log(p / p_hat) + (n - x) * np.log((1 - p) / (1 - p_hat))
    )
    pvalue = 1 - stats.chi2.cdf(lr, df=1)
    passed = pvalue > 0.05
 
    return {
        "statistic": round(float(lr), 4),
        "pvalue":    round(float(pvalue), 4),
        "passed":    bool(passed),
        "note":      "H0: violation rate equals expected rate. p > 0.05 = pass.",
    }
 
 
def _christoffersen_test(violations: np.ndarray) -> dict:
    v = violations
    n = len(v)
 
    if n < 2:
        return {"statistic": None, "pvalue": None, "passed": None, "note": "Insufficient data."}
 
    # Transition counts
    n00 = ((v[:-1] == 0) & (v[1:] == 0)).sum()
    n01 = ((v[:-1] == 0) & (v[1:] == 1)).sum()
    n10 = ((v[:-1] == 1) & (v[1:] == 0)).sum()
    n11 = ((v[:-1] == 1) & (v[1:] == 1)).sum()
 
    if (n01 + n11) == 0 or (n00 + n10) == 0:
        return {
            "statistic": None,
            "pvalue":    None,
            "passed":    True,
            "note":      "Insufficient transitions to compute test.",
        }
 
    pi_01 = n01 / (n00 + n01) if (n00 + n01) > 0 else 1e-10
    pi_11 = n11 / (n10 + n11) if (n10 + n11) > 0 else 1e-10
    pi    = (n01 + n11) / (n00 + n01 + n10 + n11)
 
    def safe_log(x):
        return np.log(max(x, 1e-10))
 
    lr_unc = (
        (n00 + n10) * safe_log(1 - pi) +
        (n01 + n11) * safe_log(pi)
    )
    lr_dep = (
        n00 * safe_log(1 - pi_01) + n01 * safe_log(pi_01) +
        n10 * safe_log(1 - pi_11) + n11 * safe_log(pi_11)
    )
    lr     = -2 * (lr_unc - lr_dep)
    pvalue = 1 - stats.chi2.cdf(lr, df=1)
    passed = pvalue > 0.05
 
    return {
        "statistic": round(float(lr), 4),
        "pvalue":    round(float(pvalue), 4),
        "passed":    bool(passed),
        "note":      "H0: violations are independent (no clustering). p > 0.05 = pass.",
    }
 
 
def backtest_summary(backtest: dict) -> pd.DataFrame:
    rows = []
    labels = {"historical": "Historical", "parametric": "Parametric (Gaussian)", "monte_carlo": "Monte Carlo"}
    for key, label in labels.items():
        r  = backtest["results"][key]
        kp = r["kupiec"]
        ch = r["christoffersen"]
        rows.append({
            "Method":           label,
            "Violations":       f"{r['n_violations']} / {backtest['n_observations']}",
            "Violation Rate":   f"{r['violation_rate']:.1%}",
            "Expected Rate":    f"{r['expected_rate']:.1%}",
            "Kupiec p-value":   f"{kp['pvalue']:.3f}" if kp["pvalue"] is not None else "N/A",
            "Kupiec Pass":      "✓" if kp["passed"] else "✗",
            "Independence Pass": "✓" if ch["passed"] else "✗",
        })
    return pd.DataFrame(rows).set_index("Method")