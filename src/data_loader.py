import yfinance as yf
import numpy as np
import pandas as pd
from typing import Optional


def fetch_prices(
    tickers: list[str],
    start: str,
    end: str,
) -> pd.DataFrame:
    """Download adjusted close prices for one or more tickers."""
    raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)

    prices = raw["Close"] if len(tickers) > 1 else raw[["Close"]]
    prices.columns = tickers if len(tickers) > 1 else tickers

    prices = prices.dropna()

    if prices.empty:
        raise ValueError(f"No price data returned for {tickers} between {start} and {end}.")

    return prices


def compute_returns(
    prices: pd.DataFrame,
    weights: Optional[list[float]] = None,
) -> tuple[pd.Series, pd.DataFrame, np.ndarray]:
    """
    Compute weighted portfolio log-returns from a price DataFrame.

    Returns
    -------
    port_returns : pd.Series
        Weighted daily log-return series for the portfolio.
    individual_returns : pd.DataFrame
        Log-return series for each individual ticker.
    weights_arr : np.ndarray
        Weight vector used (equal-weighted if weights=None).
    """
    individual_returns = np.log(prices / prices.shift(1)).dropna()

    n = individual_returns.shape[1]
    weights_arr = np.array(weights) if weights is not None else np.ones(n) / n

    if len(weights_arr) != n:
        raise ValueError(f"Expected {n} weights, got {len(weights_arr)}.")
    if not np.isclose(weights_arr.sum(), 1.0):
        raise ValueError(f"Weights must sum to 1.0, got {weights_arr.sum():.4f}.")

    port_returns = individual_returns @ weights_arr

    return port_returns, individual_returns, weights_arr


def load_portfolio(
    tickers: list[str],
    start: str,
    end: str,
    weights: Optional[list[float]] = None,
) -> tuple[pd.Series, pd.DataFrame, pd.DataFrame, np.ndarray]:
    """
    Convenience wrapper: fetch prices and compute returns in one call.

    Returns
    -------
    port_returns       : pd.Series       — weighted portfolio log-returns
    individual_returns : pd.DataFrame    — per-ticker log-returns
    prices             : pd.DataFrame    — raw adjusted close prices
    weights_arr        : np.ndarray      — weight vector applied
    """
    prices = fetch_prices(tickers, start, end)
    port_returns, individual_returns, weights_arr = compute_returns(prices, weights)
    return port_returns, individual_returns, prices, weights_arr
