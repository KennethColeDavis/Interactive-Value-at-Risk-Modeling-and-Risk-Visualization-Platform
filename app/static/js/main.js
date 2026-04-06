const state = {
  holdings: [],
  confidence: "95",
  lookback: "1y",
  holdingPeriod: "1d",
  charts: {},
};

let tickerTimers = {};

// ── Boot ──────────────────────────────────────────────────────────────────

async function init() {
  await loadConfig();
  addHolding();
  addHolding();
  document.getElementById("add-holding-btn").addEventListener("click", addHolding);
  document.getElementById("analyse-btn").addEventListener("click", runAnalysis);
  document.getElementById("backtest-btn").addEventListener("click", runBacktest);
}

async function loadConfig() {
  const res  = await fetch("/api/config");
  const data = await res.json();
  const cfg  = data.config;

  buildPills("confidence-pills",    cfg.confidence_levels,  "confidence");
  buildPills("lookback-pills",      cfg.lookback_periods,   "lookback");
  buildPills("holding-period-pills", cfg.holding_periods,   "holdingPeriod");
}

// ── Pills ─────────────────────────────────────────────────────────────────

function buildPills(containerId, options, stateKey) {
  const container = document.getElementById(containerId);
  options.forEach(opt => {
    const btn = document.createElement("button");
    btn.className = "pill" + (state[stateKey] === opt.value ? " active" : "");
    btn.textContent = opt.label;
    btn.dataset.value = opt.value;
    btn.addEventListener("click", () => {
      state[stateKey] = opt.value;
      container.querySelectorAll(".pill").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
    });
    container.appendChild(btn);
  });
}

// ── Holdings ──────────────────────────────────────────────────────────────

function addHolding() {
  const id = Date.now();
  state.holdings.push({ id, ticker: "", shares: "", valid: false });

  const row = document.createElement("div");
  row.className = "holding-row";
  row.dataset.id = id;
  row.innerHTML = `
    <div>
      <input class="ticker-input" type="text" placeholder="AAPL" maxlength="10" data-field="ticker" />
      <div class="ticker-hint" data-hint="${id}"></div>
    </div>
    <input type="number" placeholder="Shares" min="0.0001" step="any" data-field="shares" />
    <button class="remove-btn" title="Remove">✕</button>
  `;

  row.querySelector("[data-field='ticker']").addEventListener("input", e => onTickerInput(e, id));
  row.querySelector("[data-field='shares']").addEventListener("input", e => onSharesInput(e, id));
  row.querySelector(".remove-btn").addEventListener("click", () => removeHolding(id));

  document.getElementById("holdings-list").appendChild(row);
  row.querySelector("[data-field='ticker']").focus();
  checkRunnable();
}

function removeHolding(id) {
  state.holdings = state.holdings.filter(h => h.id !== id);
  const row = document.querySelector(`.holding-row[data-id="${id}"]`);
  if (row) row.remove();
  checkRunnable();
}

function onSharesInput(e, id) {
  const h = state.holdings.find(h => h.id === id);
  if (h) h.shares = e.target.value;
  checkRunnable();
}

function onTickerInput(e, id) {
  const val = e.target.value.toUpperCase().trim();
  e.target.value = val;

  const h = state.holdings.find(h => h.id === id);
  if (h) { h.ticker = val; h.valid = false; }

  const hint = document.querySelector(`[data-hint="${id}"]`);
  hint.textContent = "";
  hint.className = "ticker-hint";
  e.target.classList.remove("input-valid", "input-error");

  clearTimeout(tickerTimers[id]);

  if (val.length < 1) { checkRunnable(); return; }

  tickerTimers[id] = setTimeout(() => validateTicker(val, id, e.target, hint), 600);
  checkRunnable();
}

async function validateTicker(symbol, id, input, hint) {
  hint.textContent = "checking...";
  hint.className = "ticker-hint";

  try {
    const res  = await fetch(`/api/validate_ticker/${symbol}`);
    const data = await res.json();
    const h    = state.holdings.find(h => h.id === id);

    if (data.success) {
      hint.textContent = `${data.name} · $${data.price.toLocaleString()}`;
      hint.className = "ticker-hint valid";
      input.classList.add("input-valid");
      input.classList.remove("input-error");
      if (h) h.valid = true;
    } else {
      hint.textContent = "ticker not found";
      hint.className = "ticker-hint error";
      input.classList.add("input-error");
      input.classList.remove("input-valid");
      if (h) h.valid = false;
    }
  } catch {
    hint.textContent = "";
  }
  checkRunnable();
}

function checkRunnable() {
  const filled = state.holdings.filter(h => h.ticker && parseFloat(h.shares) > 0);
  const enabled = filled.length > 0;
  document.getElementById("analyse-btn").disabled  = !enabled;
  document.getElementById("backtest-btn").disabled = !enabled;
}

// ── Analysis ──────────────────────────────────────────────────────────────

async function runAnalysis() {
  const holdings = state.holdings
    .filter(h => h.ticker && parseFloat(h.shares) > 0)
    .map(h => ({ ticker: h.ticker, shares: parseFloat(h.shares) }));

  if (holdings.length === 0) return;

  setLoading(true);
  hideError();

  try {
    const res = await fetch("/api/analyse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        holdings,
        confidence:     state.confidence,
        lookback:       state.lookback,
        holding_period: state.holdingPeriod,
      }),
    });

    const data = await res.json();

    if (!data.success) {
      showError(data.error);
    } else {
      renderResults(data);
    }
  } catch (err) {
    showError("Network error — is the server running?");
  } finally {
    setLoading(false);
  }
}

function setLoading(on) {
  const btn    = document.getElementById("analyse-btn");
  const text   = btn.querySelector(".btn-text");
  const loader = btn.querySelector(".btn-loader");
  btn.disabled = on;
  text.hidden  = on;
  loader.hidden = !on;
}

function showError(msg) {
  const el = document.getElementById("input-error");
  el.textContent = msg;
  el.hidden = false;
}

function hideError() {
  document.getElementById("input-error").hidden = true;
}

// ── Render results ────────────────────────────────────────────────────────

function renderResults(data) {
  const { portfolio, parameters, var_results } = data;

  document.getElementById("results-empty").hidden   = true;
  document.getElementById("results-content").hidden = false;

  // Header
  document.getElementById("results-title").textContent =
    portfolio.tickers.join(" · ");
  document.getElementById("results-meta").textContent =
    `${parameters.confidence_pct} confidence · ${parameters.holding_period}-day holding · ${parameters.lookback} lookback`;
  document.getElementById("portfolio-value-display").textContent =
    "$" + portfolio.portfolio_value.toLocaleString("en-US", { minimumFractionDigits: 2 });

  // Holdings table
  const tbody = document.getElementById("holdings-table-body");
  tbody.innerHTML = "";
  portfolio.holdings.forEach(h => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="td-ticker">${h.ticker}</td>
      <td>${h.shares.toLocaleString()}</td>
      <td>$${h.price.toLocaleString("en-US", { minimumFractionDigits: 2 })}</td>
      <td>$${h.value.toLocaleString("en-US", { minimumFractionDigits: 2 })}</td>
      <td>${(h.weight * 100).toFixed(1)}%</td>
    `;
    tbody.appendChild(tr);
  });

  // VaR subtitle
  document.getElementById("var-subtitle").textContent =
    `Maximum expected loss at ${parameters.confidence_pct} confidence over a ${parameters.holding_period}-day holding period.`;

  // VaR cards
  const methods = [
    { key: "historical",  label: "Historical",           result: var_results.historical },
    { key: "parametric",  label: "Parametric (Gaussian)", result: var_results.parametric },
    { key: "monte_carlo", label: "Monte Carlo",           result: var_results.monte_carlo },
  ];

  const cardsEl = document.getElementById("var-cards");
  cardsEl.innerHTML = "";
  methods.forEach(m => {
    const card = document.createElement("div");
    card.className = "var-card";
    card.innerHTML = `
      <div class="var-card-accent"></div>
      <div class="var-card-method">${m.label}</div>
      <div class="var-card-value">$${m.result.var_usd.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
      <div class="var-card-pct">${m.result.var_pct_fmt}</div>
      <div class="var-card-divider"></div>
      <div class="var-card-cvar-label">CVaR / Expected Shortfall</div>
      <div class="var-card-cvar-value">$${m.result.cvar_usd.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
    `;
    cardsEl.appendChild(card);
  });

  // Summary table
  const stbody = document.getElementById("summary-table-body");
  stbody.innerHTML = "";
  methods.forEach(m => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="td-ticker">${m.label}</td>
      <td>${m.result.var_pct_fmt}</td>
      <td>${m.result.var_usd_fmt}</td>
      <td>${m.result.cvar_usd_fmt}</td>
    `;
    stbody.appendChild(tr);
  });

  // Normality warning
  const nw = document.getElementById("normality-warning");
  nw.hidden = !var_results.parametric.normality_warning;

  // Charts
  renderCharts(var_results, parameters.confidence_pct);
}

// ── Charts ────────────────────────────────────────────────────────────────

const METHOD_COLORS = {
  historical:  { line: "#FF3B30" },
  parametric:  { line: "#1A6BFF" },
  monte_carlo: { line: "#00B87A" },
};

function buildHistogram(values, bins = 55) {
  const min     = Math.min(...values);
  const max     = Math.max(...values);
  const binSize = (max - min) / bins;
  const counts  = new Array(bins).fill(0);
  values.forEach(v => {
    const i = Math.min(Math.floor((v - min) / binSize), bins - 1);
    counts[i]++;
  });
  const centers = counts.map((_, i) => min + (i + 0.5) * binSize);
  return { centers, counts };
}

// Generate synthetic normal distribution samples from mean + sigma
// so Parametric always has data to display
function generateNormalSamples(mu, sigma, n = 2000) {
  const samples = [];
  for (let i = 0; i < n; i++) {
    // Box-Muller transform
    const u1 = Math.random(), u2 = Math.random();
    const z  = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    samples.push(mu + sigma * z);
  }
  return samples;
}

function renderMethodChart(canvasId, badgeId, methodKey, result, confidencePct) {
  if (state.charts[methodKey]) state.charts[methodKey].destroy();

  const colors = METHOD_COLORS[methodKey];

  // Parametric has no raw series — generate one from its mean + sigma
  let values = result.return_series || result.simulated_returns;
  if (!values || values.length === 0) {
    if (result.mean_daily_return !== undefined && result.daily_volatility !== undefined) {
      values = generateNormalSamples(result.mean_daily_return, result.daily_volatility, 2000);
    } else {
      return;
    }
  }

  const { centers, counts } = buildHistogram(values, 55);
  const varVal  = result.var_pct;
  const labels  = centers.map(v => v.toFixed(4));
  const ctx     = document.getElementById(canvasId).getContext("2d");

  document.getElementById(badgeId).textContent =
    `VaR: ${result.var_pct_fmt}  ·  CVaR: ${result.cvar_pct_fmt}`;

  const tailCounts   = counts.map((c, i) => centers[i] <= varVal ? c : 0);
  const normalCounts = counts.map((c, i) => centers[i] >  varVal ? c : 0);

  // Find closest label index to the VaR value for the annotation line
  const varLabelIndex = labels.reduce((bestIdx, l, i) =>
    Math.abs(parseFloat(l) - varVal) < Math.abs(parseFloat(labels[bestIdx]) - varVal) ? i : bestIdx, 0
  );

  state.charts[methodKey] = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Loss tail",
          data: tailCounts,
          backgroundColor: hexToRgba(colors.line, 0.55),
          borderColor: colors.line,
          borderWidth: 0.5,
          borderRadius: 2,
        },
        {
          label: "Normal range",
          data: normalCounts,
          backgroundColor: "rgba(140,140,150,0.18)",
          borderColor: "rgba(140,140,150,0.3)",
          borderWidth: 0.5,
          borderRadius: 2,
        },
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: items => `Return: ${parseFloat(items[0].label).toFixed(4)}`,
            label: item  => `Count: ${item.raw}`,
          }
        },
        annotation: {
          annotations: {
            varLine: {
              type:        "line",
              scaleID:     "x",
              value:       varLabelIndex,
              borderColor: colors.line,
              borderWidth: 2,
              borderDash:  [5, 3],
              label: {
                display:         true,
                content:         `${confidencePct} VaR`,
                position:        "start",
                backgroundColor: colors.line,
                color:           "#fff",
                font:            { size: 10, weight: "500" },
                padding:         { x: 6, y: 3 },
              }
            }
          }
        }
      },
      scales: {
        x: {
          stacked: true,
          ticks: { maxTicksLimit: 5, font: { size: 10 }, color: "#888882" },
          grid:  { display: false },
        },
        y: {
          stacked: true,
          ticks: { font: { size: 10 }, color: "#888882" },
          grid:  { color: "rgba(0,0,0,0.04)" },
        }
      }
    }
  });
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function renderCharts(var_results, confidencePct) {
  renderMethodChart("hist-chart", "hist-badge", "historical",  var_results.historical,  confidencePct);
  renderMethodChart("para-chart", "para-badge", "parametric",  var_results.parametric,  confidencePct);
  renderMethodChart("mc-chart",   "mc-badge",   "monte_carlo", var_results.monte_carlo, confidencePct);
}

// ── Backtest ──────────────────────────────────────────────────────────────

async function runBacktest() {
  const holdings = state.holdings
    .filter(h => h.ticker && parseFloat(h.shares) > 0)
    .map(h => ({ ticker: h.ticker, shares: parseFloat(h.shares) }));

  if (holdings.length === 0) return;

  const btn    = document.getElementById("backtest-btn");
  const text   = btn.querySelector(".btn-text");
  const loader = btn.querySelector(".btn-loader");
  btn.disabled  = true;
  text.hidden   = true;
  loader.hidden = false;
  hideError();

  // Backtest needs max data — force 2y lookback
  const lookback = state.lookback === "6mo" ? "1y" : state.lookback;

  try {
    const res = await fetch("/api/backtest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        holdings,
        confidence: state.confidence,
        lookback,
      }),
    });

    const data = await res.json();

    if (!data.success) {
      showError(data.error);
    } else {
      // Show results panel if not already visible
      document.getElementById("results-empty").hidden   = true;
      document.getElementById("results-content").hidden = false;
      renderBacktest(data);
    }
  } catch (err) {
    showError("Network error — is the server running?");
  } finally {
    btn.disabled  = false;
    text.hidden   = false;
    loader.hidden = true;
  }
}

function renderBacktest(bt) {
  const el = document.getElementById("backtest-results");
  el.hidden = false;
  el.scrollIntoView({ behavior: "smooth", block: "start" });

  const methodLabels = {
    historical:  "Historical",
    parametric:  "Parametric",
    monte_carlo: "Monte Carlo",
  };
  const methodColors = {
    historical:  "#FF3B30",
    parametric:  "#1A6BFF",
    monte_carlo: "#00B87A",
  };

  document.getElementById("backtest-subtitle").textContent =
    `Rolling ${bt.window}-day estimation window · ${bt.n_observations} test days · ` +
    `expected ${bt.expected_violations} violations at ${(bt.confidence * 100).toFixed(0)}% confidence`;

  // Stat cards
  const row = document.getElementById("backtest-stat-row");
  row.innerHTML = "";
  for (const [key, label] of Object.entries(methodLabels)) {
    const r        = bt.results[key];
    const kp       = r.kupiec;
    const ch       = r.christoffersen;
    const overRate = r.violation_rate > r.expected_rate * 1.5;
    const status   = (!kp.passed || !ch.passed) ? "fail" : overRate ? "fail" : "pass";

    const card = document.createElement("div");
    card.className = `backtest-stat-card ${status}`;
    card.innerHTML = `
      <div class="bsc-method">${label}</div>
      <div class="bsc-rate">${(r.violation_rate * 100).toFixed(1)}%</div>
      <div class="bsc-label">violation rate (expected ${(r.expected_rate * 100).toFixed(0)}%)</div>
      <div class="bsc-badges">
        <span class="bsc-badge ${kp.passed ? 'pass' : 'fail'}">Kupiec ${kp.passed ? '✓' : '✗'}</span>
        <span class="bsc-badge ${ch.passed ? 'pass' : 'fail'}">Independence ${ch.passed ? '✓' : '✗'}</span>
      </div>
    `;
    row.appendChild(card);
  }

  // Table
  const tbody = document.getElementById("backtest-table-body");
  tbody.innerHTML = "";
  for (const [key, label] of Object.entries(methodLabels)) {
    const r  = bt.results[key];
    const kp = r.kupiec;
    const ch = r.christoffersen;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="td-ticker">${label}</td>
      <td>${r.n_violations} / ${bt.n_observations}</td>
      <td>${(r.violation_rate * 100).toFixed(2)}%</td>
      <td>${(r.expected_rate * 100).toFixed(1)}%</td>
      <td>${kp.pvalue !== null ? kp.pvalue.toFixed(3) : "N/A"}</td>
      <td class="${kp.passed ? 'td-pass' : 'td-fail'}">${kp.passed ? "Pass ✓" : "Fail ✗"}</td>
      <td class="${ch.passed ? 'td-pass' : 'td-fail'}">${ch.passed ? "Pass ✓" : "Fail ✗"}</td>
    `;
    tbody.appendChild(tr);
  }

  // Timeline chart
  renderBacktestChart(bt, methodColors);
}

function renderBacktestChart(bt, methodColors) {
  if (state.charts.backtest) state.charts.backtest.destroy();

  const labels  = bt.dates;
  const actuals = bt.actual_returns;
  const step    = Math.max(1, Math.floor(labels.length / 300));
  const sliced  = (arr) => arr.filter((_, i) => i % step === 0);
  const slicedLabels = sliced(labels);

  const datasets = [
    {
      label:           "Actual Return",
      data:            sliced(actuals),
      type:            "bar",
      backgroundColor: actuals
        .filter((_, i) => i % step === 0)
        .map(v => v < 0 ? "rgba(80,80,90,0.35)" : "rgba(80,80,90,0.15)"),
      borderWidth:     0,
      order:           4,
    },
  ];

  for (const [key, color] of Object.entries(methodColors)) {
    const varSeries = bt.results[key].var_series;
    datasets.push({
      label:       `${key.replace("_", " ")} VaR`,
      data:        sliced(varSeries.length === labels.length ? varSeries : varSeries),
      type:        "line",
      borderColor: color,
      borderWidth: 1.5,
      pointRadius: 0,
      tension:     0.3,
      fill:        false,
      order:       1,
    });
  }

  const ctx = document.getElementById("backtest-chart").getContext("2d");
  state.charts.backtest = new Chart(ctx, {
    type: "bar",
    data: { labels: slicedLabels, datasets },
    options: {
      responsive:          true,
      maintainAspectRatio: true,
      interaction:         { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: item => `${item.dataset.label}: ${parseFloat(item.raw).toFixed(4)}`,
          }
        }
      },
      scales: {
        x: {
          ticks: { maxTicksLimit: 8, font: { size: 10 }, color: "#888882" },
          grid:  { display: false },
        },
        y: {
          ticks: { font: { size: 10 }, color: "#888882" },
          grid:  { color: "rgba(0,0,0,0.04)" },
        }
      }
    }
  });
}

document.addEventListener("DOMContentLoaded", init);