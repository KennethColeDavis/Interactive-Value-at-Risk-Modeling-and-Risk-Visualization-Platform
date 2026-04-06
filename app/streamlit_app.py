import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy import stats

from data_loader import load_portfolio
from var_models import run_all, results_to_dataframe

# ── Page config ────────────────────────────────────────────────────
st.set_page_config(
    page_title="VaR Risk Dashboard",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Interactive VaR Risk Dashboard")
st.caption("Historical · Parametric · Monte Carlo — Value at Risk & Expected Shortfall")

# ── Sidebar ────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Portfolio Settings")

    tickers_input = st.text_input(
        "Tickers (comma separated)",
        value="AAPL, MSFT, GOOGL",
    )
    tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start date", value=pd.to_datetime("2020-01-01"))
    with col2:
        end_date = st.date_input("End date", value=pd.to_datetime("2024-12-31"))

    st.subheader("Weights")
    use_equal = st.checkbox("Equal weight", value=True)
    weights = None
    if not use_equal:
        weight_inputs = []
        for ticker in tickers:
            w = st.number_input(f"{ticker} weight", min_value=0.0, max_value=1.0,
                                value=round(1 / len(tickers), 4), step=0.01)
            weight_inputs.append(w)
        if abs(sum(weight_inputs) - 1.0) > 0.01:
            st.warning(f"Weights sum to {sum(weight_inputs):.2f} — must equal 1.0")
        else:
            weights = weight_inputs

    st.subheader("Risk Parameters")
    confidence = st.select_slider(
        "Confidence level",
        options=[0.90, 0.95, 0.99],
        value=0.95,
        format_func=lambda x: f"{x:.0%}",
    )
    portfolio_value = st.number_input(
        "Portfolio value ($)",
        min_value=1_000,
        max_value=100_000_000,
        value=100_000,
        step=1_000,
    )
    n_sims = st.select_slider(
        "Monte Carlo simulations",
        options=[1_000, 5_000, 10_000, 50_000],
        value=10_000,
        format_func=lambda x: f"{x:,}",
    )

    run = st.button("Calculate VaR", type="primary", use_container_width=True)

# ── Main ───────────────────────────────────────────────────────────
if not run:
    st.info("Configure your portfolio in the sidebar and click **Calculate VaR** to begin.")
    st.stop()

# Load data
with st.spinner("Downloading price data..."):
    try:
        port_returns, ind_returns, prices, weights_arr = load_portfolio(
            tickers,
            start=str(start_date),
            end=str(end_date),
            weights=weights,
        )
    except Exception as e:
        st.error(f"Data loading failed: {e}")
        st.stop()

# Run models
with st.spinner("Running VaR models..."):
    results, mc_sims = run_all(
        port_returns,
        confidence=confidence,
        portfolio_value=portfolio_value,
        n_sims=n_sims,
    )

hist_r, para_r, mc_r = results

# ── Summary metrics ────────────────────────────────────────────────
st.subheader("Results")

cols = st.columns(3)
method_colors = {"Historical": "#e74c3c", "Parametric": "#3498db", "Monte Carlo": "#2ecc71"}

for col, result in zip(cols, results):
    with col:
        st.markdown(f"**{result.method}**")
        m1, m2 = st.columns(2)
        m1.metric("VaR",  f"${result.var_usd:,.0f}",  f"{result.var_pct:.2%}")
        m2.metric("CVaR", f"${result.cvar_usd:,.0f}", f"{result.cvar_pct:.2%}")

st.divider()

# ── Summary table ──────────────────────────────────────────────────
st.subheader("Summary Table")
st.dataframe(results_to_dataframe(results), use_container_width=True)

st.divider()

# ── Plots ──────────────────────────────────────────────────────────
st.subheader("Visualisations")

fig = plt.figure(figsize=(18, 12))
gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.4, wspace=0.3)

COLORS = {
    "Historical":  "#e74c3c",
    "Parametric":  "#3498db",
    "Monte Carlo": "#2ecc71",
}

# Plot 1 — normalised price history
ax1 = fig.add_subplot(gs[0, 0])
norm = prices / prices.iloc[0] * 100
for col in norm.columns:
    ax1.plot(norm.index, norm[col], linewidth=1.8, label=col)
ax1.set_title("Normalised Price History (Base = 100)", fontsize=12, fontweight="bold")
ax1.set_ylabel("Indexed Price")
ax1.legend(fontsize=9)

# Plot 2 — return distribution with all VaR lines
ax2 = fig.add_subplot(gs[0, 1])
ax2.hist(port_returns, bins=80, density=True, color="#7f8c8d", alpha=0.5, label="Empirical returns")
x = np.linspace(port_returns.min(), port_returns.max(), 400)
ax2.plot(x, stats.norm.pdf(x, port_returns.mean(), port_returns.std()),
         color=COLORS["Parametric"], lw=1.5, label="Normal fit")
for r in results:
    ax2.axvline(r.var_pct, color=COLORS[r.method], lw=2,
                linestyle="--", label=f"{r.method} VaR {r.var_pct:.2%}")
ax2.set_title(f"Return Distribution & VaR ({confidence:.0%} confidence)", fontsize=12, fontweight="bold")
ax2.set_xlabel("Daily log-return")
ax2.set_ylabel("Density")
ax2.legend(fontsize=8)

# Plot 3 — Monte Carlo loss distribution
ax3 = fig.add_subplot(gs[1, 0])
losses = -mc_sims * portfolio_value
ax3.hist(losses, bins=100, color=COLORS["Monte Carlo"], alpha=0.6, label="Simulated P&L")
ax3.axvline(mc_r.var_usd,  color="black",  lw=2,   linestyle="--", label=f"VaR  ${mc_r.var_usd:,.0f}")
ax3.axvline(mc_r.cvar_usd, color="orange", lw=1.8, linestyle=":",  label=f"CVaR ${mc_r.cvar_usd:,.0f}")
ax3.set_title(f"Monte Carlo Loss Distribution ({n_sims:,} simulations)", fontsize=12, fontweight="bold")
ax3.set_xlabel("Loss ($)")
ax3.set_ylabel("Frequency")
ax3.legend(fontsize=8)

# Plot 4 — VaR vs CVaR bar chart
ax4 = fig.add_subplot(gs[1, 1])
methods   = [r.method for r in results]
var_vals  = [r.var_usd  for r in results]
cvar_vals = [r.cvar_usd for r in results]
colors    = [COLORS[r.method] for r in results]
x_pos     = np.arange(len(methods))
bar_w     = 0.35

bars1 = ax4.bar(x_pos - bar_w / 2, var_vals,  bar_w, color=colors, alpha=0.85, label="VaR")
bars2 = ax4.bar(x_pos + bar_w / 2, cvar_vals, bar_w, color=colors, alpha=0.45, label="CVaR")
ax4.set_xticks(x_pos)
ax4.set_xticklabels(methods)
ax4.set_ylabel("Loss ($)")
ax4.set_title(f"VaR vs CVaR by Method\n(${portfolio_value:,} portfolio, {confidence:.0%} confidence)",
              fontsize=12, fontweight="bold")
ax4.legend()
ax4.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
for bar in bars1:
    ax4.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 20,
             f"${bar.get_height():,.0f}", ha="center", va="bottom", fontsize=8)

fig.suptitle(
    f"Portfolio Risk Analytics — {' | '.join(tickers)}",
    fontsize=15, fontweight="bold", y=1.01,
)

st.pyplot(fig)

# ── Footer metadata ────────────────────────────────────────────────
st.divider()
with st.expander("Portfolio details"):
    st.write(f"**Tickers:** {tickers}")
    st.write(f"**Period:** {start_date} → {end_date}")
    st.write(f"**Observations:** {len(port_returns):,} trading days")
    st.write(f"**Mean daily return:** {port_returns.mean():.4%}")
    st.write(f"**Daily volatility:** {port_returns.std():.4%}")
    weight_df = pd.DataFrame({"Ticker": tickers, "Weight": weights_arr})
    st.dataframe(weight_df, use_container_width=True)
