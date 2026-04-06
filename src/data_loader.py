"""
 Handles all data fetching and portfolio construction/weights for the VaR application.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# Possible user choices for lookback periods
LOOKBACK_PERIODS = {
    "6mo":  180,
    "1y":   365,
    "2y":   730,
}

#Convert a lookback string to (start_date, end_date) strings.
def _resolve_dates(lookback: str) -> tuple[str, str]:
    if lookback not in LOOKBACK_PERIODS:
        raise ValueError(f"Invalid lookback '{lookback}'. Choose from: {list(LOOKBACK_PERIODS)}")
    days = LOOKBACK_PERIODS[lookback]
    end   = datetime.today()
    start = end - timedelta(days=days)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def fetch_prices(tickers: list[str], lookback: str = "1y") -> pd.DataFrame:

    tickers = [t.upper().strip() for t in tickers]
    start, end = _resolve_dates(lookback)

    raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)

    if raw.empty:
        raise ValueError(f"No price data returned for tickers: {tickers}")

    # Handle single vs multiple ticker response shape
    if len(tickers) == 1:
        prices = raw[["Close"]].copy()
        prices.columns = tickers
    else:
        prices = raw["Close"].copy()

    prices.dropna(how="all", inplace=True)

    # Warn about any tickers with significant missing data
    for col in prices.columns:
        missing = prices[col].isna().sum()
        if missing > 5:
            print(f"  ⚠️  {col}: {missing} missing price days — check ticker symbol")

    prices.dropna(inplace=True) 
    return prices


def get_current_prices(tickers: list[str]) -> dict[str, float]:
    tickers = [t.upper().strip() for t in tickers]
    current_prices = {}

    for symbol in tickers:
        try:
            info = yf.Ticker(symbol).info
            price = (
                info.get("currentPrice")
                or info.get("regularMarketPrice")
                or info.get("previousClose")
            )
            if price is None:
                raise ValueError(f"No price found for {symbol}")
            current_prices[symbol] = round(float(price), 2)
        except Exception as e:
            raise ValueError(f"Could not fetch price for {symbol}: {e}")

    return current_prices


def build_portfolio(holdings: dict[str, float], lookback: str = "1y") -> dict:

    if not holdings:
        raise ValueError("Holdings cannot be empty.")

    tickers = list(holdings.keys())
    shares  = {t.upper().strip(): float(s) for t, s in holdings.items()}

    # ── Current prices & position values ──────────────────────────────────
    current_prices  = get_current_prices(tickers)
    position_values = {t: shares[t] * current_prices[t] for t in tickers}
    portfolio_value = sum(position_values.values())

    if portfolio_value <= 0:
        raise ValueError("Portfolio value must be greater than zero.")

    # Weights derived from actual holdings
    weights = np.array([position_values[t] / portfolio_value for t in tickers])

    # Historical price data 
    prices = fetch_prices(tickers, lookback)

    # Daily log-returns 
    returns      = np.log(prices / prices.shift(1)).dropna()
    port_returns = (returns * weights).sum(axis=1) 

    return {
        "tickers":         tickers,
        "shares":          shares,
        "current_prices":  current_prices,
        "position_values": position_values,
        "portfolio_value": round(portfolio_value, 2),
        "weights":         weights,
        "prices":          prices,
        "returns":         returns,
        "port_returns":    port_returns,
    }


def portfolio_summary(portfolio: dict) -> pd.DataFrame:
    rows = []
    for t in portfolio["tickers"]:
        rows.append({
            "Ticker": t,
            "Shares": portfolio["shares"][t],
            "Price":  f"${portfolio['current_prices'][t]:,.2f}",
            "Value":  f"${portfolio['position_values'][t]:,.2f}",
            "Weight": f"{portfolio['position_values'][t] / portfolio['portfolio_value']:.1%}",
        })

    df = pd.DataFrame(rows).set_index("Ticker")
    return df
