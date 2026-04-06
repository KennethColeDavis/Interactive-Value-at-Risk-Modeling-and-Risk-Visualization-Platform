# Interactive Value-at-Risk Modeling and Risk Visualization Platform

A full-stack portfolio risk analytics web application built with Flask. Enter any portfolio of stocks by ticker and share count, calculate Value-at-Risk using three methods, and backtest model accuracy against real historical data.

---
## Example output
![alt text](image.png)

## Features

### Portfolio Input
- Enter any number of tickers and share quantities
- Live ticker validation with company name and current price
- Portfolio value and weights derived automatically from current market prices

### VaR Calculations
Three methods run simultaneously, all returning VaR and CVaR/Expected Shortfall in both % and dollar terms:

- **Historical VaR** — non-parametric, based on actual empirical return distribution
- **Parametric (Gaussian) VaR** — assumes normally distributed returns, fitted to sample mean and volatility
- **Monte Carlo VaR** — 10,000 simulated GBM return paths

### User Controls
- Confidence level: 90%, 95%, 99%
- Lookback window: 6 months, 1 year, 2 years
- Holding period: 1-day, 5-day, 10-day (scaled via square-root-of-time rule)

### Visualizations
- Three return distribution charts, one per method, with VaR threshold line marked
- Holdings breakdown table with live prices and portfolio weights
- Method comparison table (VaR %, VaR $, CVaR $)

### Backtesting
Rolling 252-day window backtest evaluating model accuracy over time:

- **Kupiec POF test** — formally tests whether the violation rate matches the expected rate
- **Christoffersen independence test** — checks whether violations cluster in time
- Violation timeline chart showing actual returns vs all three rolling VaR lines
- Pass/fail stat cards per method

---

## Project Structure

```
├── app/
│   ├── app.py                  # Flask routes and API
│   ├── templates/
│   │   └── index.html          # Single-page UI
│   └── static/
│       ├── css/style.css
│       └── js/main.js
├── src/
│   ├── data_loader.py          # yfinance data fetching and portfolio construction
│   ├── var_models.py           # Historical, Parametric, and Monte Carlo VaR
│   └── backtester.py           # Rolling backtest engine and statistical tests
├── notebooks/
│   └── var_calculator_exploration.ipynb
├── requirements.txt
└── LICENSE
```

---

## Getting Started

### Prerequisites
- Python 3.9+
- Anaconda recommended

### Installation

```bash
git clone https://github.com/KennethColeDavis/Interactive-Value-at-Risk-Modeling-and-Risk-Visualization-Platform.git
cd Interactive-Value-at-Risk-Modeling-and-Risk-Visualization-Platform
pip install -r requirements.txt
```

### Running the App

```bash
python app/app.py
```

Open your browser and go to `http://127.0.0.1:5000`

---

## API Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Serves the main UI |
| GET | `/api/config` | Returns valid parameter options for dropdowns |
| GET | `/api/validate_ticker/<symbol>` | Live ticker validation — returns name and price |
| POST | `/api/analyse` | Runs all three VaR models for a given portfolio |
| POST | `/api/backtest` | Runs rolling window backtest with statistical tests |


---

## How VaR Works

**Value-at-Risk (VaR)** answers: *"What is the maximum I should expect to lose on a bad day?"*

At 95% confidence with a 1-day holding period, a VaR of $500 means: on 95% of days, losses will not exceed $500. On the worst 5% of days, they will.

**CVaR (Conditional VaR / Expected Shortfall)** answers the follow-up: *"When we do breach the VaR threshold, how bad does it get on average?"* CVaR is always larger than VaR and is a better measure of tail risk.

**Backtesting** validates these estimates by checking historical predictions against what actually happened. The Kupiec test checks whether the violation rate (days the loss exceeded VaR) is statistically consistent with the chosen confidence level. The Christoffersen test checks whether violations are randomly spread across time or cluster together — clustering suggests the model fails precisely when risk is highest.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| Flask | Web framework |
| yfinance | Market data |
| pandas | Data manipulation |
| numpy | Numerical computations |
| scipy | Statistical tests and distributions |
| Chart.js | Frontend charting (CDN) |

---

## License

MIT License 

© 2026 Kenneth "Cole" Davis
