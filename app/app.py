from flask import Flask, jsonify, render_template
import yfinance as yf
import numpy as np
 
app = Flask(__name__)
 
 
@app.route("/")
def index():
    return render_template("index.html")
 
 
@app.route("/api/ticker/<symbol>")
def get_ticker(symbol):
    """
    Fetches company name, current price, and 30-day annualised historical
    volatility for a given ticker symbol via yfinance.
    """
    symbol = symbol.upper().strip()
 
    try:
        ticker = yf.Ticker(symbol)
        info   = ticker.info
 
        # ── Company name ──────────────────────────────────────────────────
        name = (
            info.get("longName")
            or info.get("shortName")
            or symbol
        )
 
        # ── Current price ─────────────────────────────────────────────────
        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        )
        if price is None:
            return jsonify({"error": f"No price data found for {symbol}"}), 404
 
        # ── 30-day historical volatility (annualised) ─────────────────────
        # Download ~60 days of daily closes to ensure 30 trading days
        hist = ticker.history(period="60d", interval="1d")
        if hist.empty or len(hist) < 5:
            return jsonify({"error": f"Insufficient history for {symbol}"}), 404
 
        closes      = hist["Close"].dropna().values
        log_returns = np.diff(np.log(closes))          # daily log returns
        daily_vol   = float(np.std(log_returns, ddof=1))
        annual_vol  = round(daily_vol * np.sqrt(252), 4)  # annualise
 
        return jsonify({
            "symbol":     symbol,
            "name":       name,
            "price":      round(float(price), 2),
            "volatility": annual_vol,        # e.g. 0.28 = 28%
            "vol_pct":    round(annual_vol * 100, 2),  # e.g. 28.0
        })
 
    except Exception as e:
        return jsonify({"error": str(e)}), 500
 
 
if __name__ == "__main__":
    app.run(debug=True)