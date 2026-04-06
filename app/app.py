import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from flask import Flask, jsonify, render_template, request
from data_loader import build_portfolio, portfolio_summary, LOOKBACK_PERIODS
from var_models import compute_all_var, HOLDING_PERIODS, CONFIDENCE_LEVELS
from backtester import rolling_backtest

app = Flask(__name__, template_folder="templates", static_folder="static")


def _error(message: str, status: int = 400):
    return jsonify({"success": False, "error": message}), status


def _parse_holdings(raw: list) -> dict[str, float]:
    if not raw or not isinstance(raw, list):
        raise ValueError("Holdings must be a non-empty list.")

    holdings = {}
    for item in raw:
        ticker = str(item.get("ticker", "")).upper().strip()
        shares = item.get("shares")

        if not ticker:
            raise ValueError("Each holding must include a ticker symbol.")
        if shares is None:
            raise ValueError(f"Missing share quantity for {ticker}.")

        try:
            shares = float(shares)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid share quantity for {ticker}: '{shares}'.")

        if shares <= 0:
            raise ValueError(f"Share quantity for {ticker} must be greater than zero.")
        if ticker in holdings:
            raise ValueError(f"Duplicate ticker: {ticker}. Each ticker can only appear once.")

        holdings[ticker] = shares

    return holdings


def _portfolio_to_json(portfolio: dict) -> dict:
    return {
        "tickers":         portfolio["tickers"],
        "portfolio_value": portfolio["portfolio_value"],
        "holdings": [
            {
                "ticker": t,
                "shares": portfolio["shares"][t],
                "price":  portfolio["current_prices"][t],
                "value":  round(portfolio["position_values"][t], 2),
                "weight": round(portfolio["position_values"][t] / portfolio["portfolio_value"], 4),
            }
            for t in portfolio["tickers"]
        ],
    }


def _var_result_to_json(result: dict) -> dict:
    clean = {k: v for k, v in result.items() if k not in ("simulated_returns", "return_series")}

    if "return_series" in result:
        clean["return_series"] = result["return_series"]
    if "simulated_returns" in result:
        clean["simulated_returns"] = result["simulated_returns"][:2000]

    return clean


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config")
def get_config():
    return jsonify({
        "success": True,
        "config": {
            "confidence_levels": [
                {"label": "90%", "value": "90"},
                {"label": "95%", "value": "95"},
                {"label": "99%", "value": "99"},
            ],
            "lookback_periods": [
                {"label": "6 Months", "value": "6mo"},
                {"label": "1 Year",   "value": "1y"},
                {"label": "2 Years",  "value": "2y"},
            ],
            "holding_periods": [
                {"label": "1 Day",   "value": "1d"},
                {"label": "5 Days",  "value": "5d"},
                {"label": "10 Days", "value": "10d"},
            ],
        }
    })


@app.route("/api/validate_ticker/<symbol>")
def validate_ticker(symbol: str):
    symbol = symbol.upper().strip()

    if not symbol or len(symbol) > 10:
        return _error("Invalid ticker symbol.")

    try:
        import yfinance as yf
        info  = yf.Ticker(symbol).info
        name  = info.get("longName") or info.get("shortName") or symbol
        price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")

        if price is None:
            return _error(f"No price data found for '{symbol}'.", 404)

        return jsonify({"success": True, "symbol": symbol, "name": name, "price": round(float(price), 2)})

    except Exception as e:
        return _error(f"Could not validate ticker '{symbol}': {str(e)}", 500)


@app.route("/api/analyse", methods=["POST"])
def analyse():
    data = request.get_json(silent=True)
    if not data:
        return _error("Request body must be JSON.")

    try:
        holdings = _parse_holdings(data.get("holdings", []))
    except ValueError as e:
        return _error(str(e))

    confidence_key = str(data.get("confidence", "95"))
    if confidence_key not in CONFIDENCE_LEVELS:
        return _error(f"Invalid confidence level '{confidence_key}'. Choose from: 90, 95, 99.")
    confidence = CONFIDENCE_LEVELS[confidence_key]

    lookback = data.get("lookback", "1y")
    if lookback not in LOOKBACK_PERIODS:
        return _error(f"Invalid lookback '{lookback}'. Choose from: 6mo, 1y, 2y.")

    holding_period_key = data.get("holding_period", "1d")
    if holding_period_key not in HOLDING_PERIODS:
        return _error(f"Invalid holding period '{holding_period_key}'. Choose from: 1d, 5d, 10d.")
    holding_period = HOLDING_PERIODS[holding_period_key]

    try:
        portfolio = build_portfolio(holdings, lookback=lookback)
    except ValueError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"Failed to fetch market data: {str(e)}", 500)

    try:
        results = compute_all_var(
            port_returns    = portfolio["port_returns"],
            portfolio_value = portfolio["portfolio_value"],
            confidence      = confidence,
            holding_period  = holding_period,
        )
    except ValueError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"VaR calculation failed: {str(e)}", 500)

    return jsonify({
        "success":   True,
        "portfolio": _portfolio_to_json(portfolio),
        "parameters": {
            "confidence":     confidence,
            "confidence_pct": f"{confidence * 100:.0f}%",
            "lookback":       lookback,
            "holding_period": holding_period,
        },
        "var_results": {
            "historical":  _var_result_to_json(results["historical"]),
            "parametric":  _var_result_to_json(results["parametric"]),
            "monte_carlo": _var_result_to_json(results["monte_carlo"]),
        },
    })


@app.route("/api/backtest", methods=["POST"])
def backtest():
    data = request.get_json(silent=True)
    if not data:
        return _error("Request body must be JSON.")

    try:
        holdings = _parse_holdings(data.get("holdings", []))
    except ValueError as e:
        return _error(str(e))

    confidence_key = str(data.get("confidence", "95"))
    if confidence_key not in CONFIDENCE_LEVELS:
        return _error(f"Invalid confidence level '{confidence_key}'.")
    confidence = CONFIDENCE_LEVELS[confidence_key]

    lookback = data.get("lookback", "2y")
    if lookback not in LOOKBACK_PERIODS:
        return _error(f"Invalid lookback '{lookback}'.")

    try:
        portfolio = build_portfolio(holdings, lookback=lookback)
    except ValueError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"Failed to fetch market data: {str(e)}", 500)

    try:
        bt = rolling_backtest(portfolio["port_returns"], confidence=confidence)
    except ValueError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"Backtest failed: {str(e)}", 500)

    # Slim down var_series for payload size
    for method_data in bt["results"].values():
        method_data["var_series"] = method_data["var_series"][::2]  # every other point

    return jsonify({"success": True, **bt})


if __name__ == "__main__":
    app.run(debug=True, port=5000)