/**
 * Franchise Scorecard & Operations Dashboard
 * Dynamic data visualizer, tab manager, and parameter customization engine
 */

let charts = {};

document.addEventListener("DOMContentLoaded", function () {
  loadDashboardData();
  initParamToggles();
});

// Switch active tab
function switchTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === tabId);
  });
  document.querySelectorAll(".tab-panel").forEach(panel => {
    panel.classList.toggle("active", panel.id === tabId);
  });
  // Trigger chart re-render/resize on tab switch
  Object.values(charts).forEach(c => c && c.resize && c.resize());
}

// Format numbers
const formatCurrency = num => "$" + Number(num || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
const formatNumber = num => Number(num || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });

// Fetch scorecard data and render everything
async function loadDashboardData() {
  const locSelect = document.getElementById("location-select");
  const periodSelect = document.getElementById("period-select");
  if (!locSelect || !periodSelect) return;

  const locId = locSelect.value;
  const periodId = periodSelect.value;

  try {
    const res = await fetch(`/api/scorecard-data?period_id=${periodId}&location_id=${locId}`);
    if (!res.ok) throw new Error("Failed to fetch scorecard data");
    const data = await res.json();

    updateExecutiveTab(data);
    updateActivationsTab(data);
    updateCpoTab(data);
    updateRepairsTab(data);
    updateAccessoriesTab(data);
    updateTrafficTab(data);
    updateBenchmarkTab(data);

    // Also fetch weekly trends for the selected location
    loadWeeklyTrends(locId);

  } catch (err) {
    console.error("Error loading dashboard data:", err);
  }
}

// 1. Update Executive Tab
function updateExecutiveTab(data) {
  const s = data.summary || {};
  document.getElementById("kpi-gross-revenue").innerText = formatCurrency(s.gross_revenue_actual);
  document.getElementById("kpi-projected-revenue").innerText = formatCurrency(s.gross_revenue_projected);
  document.getElementById("kpi-sales-volume").innerText = formatNumber(s.sales_volume);
  document.getElementById("kpi-asp").innerText = formatCurrency(s.asp);
  document.getElementById("kpi-activations").innerText = formatNumber(s.activations_total);
  document.getElementById("kpi-activations-new").innerText = formatNumber(s.activations_new);
  document.getElementById("kpi-activations-renewals").innerText = formatNumber(s.activations_renewals);
  document.getElementById("kpi-cpo-units").innerText = formatNumber(s.cpo_units_actual);
  document.getElementById("kpi-cpo-revenue").innerText = formatCurrency(s.cpo_revenue_actual);
  document.getElementById("kpi-repairs-total").innerText = formatNumber(s.repairs_oow_volume + s.repairs_insurance_volume);
  document.getElementById("kpi-repairs-oow").innerText = formatNumber(s.repairs_oow_volume);
  document.getElementById("kpi-repairs-ins").innerText = formatNumber(s.repairs_insurance_volume);
  document.getElementById("kpi-conversion-rate").innerText = (s.conversion_rate_pct || 0) + "%";
  document.getElementById("kpi-traffic-count").innerText = formatNumber(s.foot_traffic_total);

  // Render Revenue Mix Bar Chart
  renderRevenueMixChart(s);

  // Render Benchmark Radar Chart
  renderBenchmarkRadarChart(s, data.benchmark || {});

  // Render Store Leaderboard Table
  renderLeaderboardTable(data.store_rows || []);
}

function renderRevenueMixChart(s) {
  const ctx = document.getElementById("chart-revenue-mix");
  if (!ctx) return;
  if (charts.revenueMix) charts.revenueMix.destroy();

  charts.revenueMix = new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["CPO Sales", "OOW Repairs", "Insurance Repairs", "Accessories"],
      datasets: [{
        label: "Revenue Contribution ($)",
        data: [s.cpo_revenue_actual, s.repairs_oow_revenue, s.repairs_insurance_revenue, s.accessories_revenue],
        backgroundColor: ["#10b981", "#f59e0b", "#06b6d4", "#6366f1"],
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: { label: ctx => " " + formatCurrency(ctx.parsed.y) }
        }
      },
      scales: {
        y: {
          grid: { color: "rgba(255,255,255,0.05)" },
          ticks: { color: "#94a3b8", callback: v => "$" + (v / 1000) + "k" }
        },
        x: {
          grid: { display: false },
          ticks: { color: "#94a3b8" }
        }
      }
    }
  });
}

function renderBenchmarkRadarChart(s, bm) {
  const ctx = document.getElementById("chart-benchmark-radar");
  if (!ctx) return;
  if (charts.benchmarkRadar) charts.benchmarkRadar.destroy();

  const bmLabel = document.getElementById("benchmark-region-label");
  if (bmLabel) bmLabel.innerText = `${bm.region || 'West'} Region Average (${bm.store_count || 0} Stores)`;

  charts.benchmarkRadar = new Chart(ctx, {
    type: "radar",
    data: {
      labels: ["Revenue Index", "Activations", "CPO Units", "Repairs", "Traffic Index"],
      datasets: [
        {
          label: "Your Performance",
          data: [
            bm.avg_revenue ? Math.min(150, (s.gross_revenue_actual / bm.avg_revenue) * 100) : 100,
            bm.avg_activations ? Math.min(150, (s.activations_total / bm.avg_activations) * 100) : 100,
            bm.avg_cpo ? Math.min(150, (s.cpo_units_actual / bm.avg_cpo) * 100) : 100,
            bm.avg_repairs ? Math.min(150, (s.repairs_oow_volume / bm.avg_repairs) * 100) : 100,
            bm.avg_traffic ? Math.min(150, (s.foot_traffic_total / bm.avg_traffic) * 100) : 100
          ],
          borderColor: "#6366f1",
          backgroundColor: "rgba(99, 102, 241, 0.25)",
          pointBackgroundColor: "#6366f1"
        },
        {
          label: "Regional Baseline (100%)",
          data: [100, 100, 100, 100, 100],
          borderColor: "rgba(255,255,255,0.3)",
          borderDash: [4, 4],
          backgroundColor: "rgba(255,255,255,0.03)",
          pointBackgroundColor: "rgba(255,255,255,0.5)"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          grid: { color: "rgba(255,255,255,0.06)" },
          angleLines: { color: "rgba(255,255,255,0.06)" },
          ticks: { display: false },
          pointLabels: { color: "#94a3b8", font: { size: 10 } }
        }
      },
      plugins: {
        legend: { labels: { color: "#94a3b8", font: { size: 11 } } },
        tooltip: {
          callbacks: { label: ctx => ` ${ctx.dataset.label}: ${Math.round(ctx.raw)}% of avg` }
        }
      }
    }
  });
}

function renderLeaderboardTable(stores) {
  const tbody = document.getElementById("leaderboard-tbody");
  const countEl = document.getElementById("leaderboard-count");
  if (!tbody) return;

  if (countEl) countEl.innerText = `Showing ${stores.length} store(s)`;
  tbody.innerHTML = "";

  stores.forEach((st, idx) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>#${st.store_number}</strong></td>
      <td><strong>${st.name}</strong></td>
      <td><span class="role-pill" style="background:rgba(255,255,255,0.05);">${st.region}</span></td>
      <td><span style="color:#10b981;font-weight:600;">${formatCurrency(st.revenue)}</span></td>
      <td>${formatNumber(st.sales_volume)}</td>
      <td><span style="color:#a855f7;font-weight:600;">${st.activations}</span></td>
      <td>${st.cpo_units}</td>
      <td>${st.repairs_oow}</td>
      <td>${formatNumber(st.traffic)}</td>
      <td><span class="delta-badge ${st.conversion_rate_pct >= 10 ? 'delta-positive' : 'delta-neutral'}">${st.conversion_rate_pct}%</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// 2. Update Carrier Activations Tab
function updateActivationsTab(data) {
  const s = data.summary || {};
  document.getElementById("kpi-postpaid-split").innerText = `${s.activations_telus_post || 0} / ${s.activations_koodo_post || 0}`;
  document.getElementById("kpi-finance-count").innerText = formatNumber(s.koodo_finance + s.telus_finance);
  document.getElementById("kpi-migrations-count").innerText = formatNumber(s.activations_migrations + s.activations_renewals);

  const ctx = document.getElementById("chart-activation-types");
  if (!ctx) return;
  if (charts.activationTypes) charts.activationTypes.destroy();

  charts.activationTypes = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["New Activations", "Renewals", "Migrations"],
      datasets: [{
        data: [s.activations_new, s.activations_renewals, s.activations_migrations],
        backgroundColor: ["#8b5cf6", "#6366f1", "#06b6d4"],
        borderColor: "#0e131f",
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { color: "#94a3b8" } }
      }
    }
  });
}

// 3. Update CPO Hardware Tab
function updateCpoTab(data) {
  const s = data.summary || {};
  document.getElementById("cpo-attach-rate-display").innerText = (s.cpo_attach_rate_pct || 0) + "%";
  document.getElementById("disp-cpo-total").innerText = formatNumber(s.cpo_units_actual);
  document.getElementById("disp-cpo-attached").innerText = formatNumber(s.cpo_attach_activations_count);
  document.getElementById("disp-trade-ins").innerText = formatNumber(s.trade_in_units);
}

// 4. Update Repairs Tab
function updateRepairsTab(data) {
  const s = data.summary || {};
  document.getElementById("kpi-repairs-daily").innerText = s.repairs_oow_daily_avg || 0;
  document.getElementById("kpi-repair-attach-rate").innerText = (s.repair_attach_rate_pct || 0) + "%";
  document.getElementById("kpi-total-repair-rev").innerText = formatCurrency(s.repairs_oow_revenue + s.repairs_insurance_revenue);

  const ctx = document.getElementById("chart-repairs-split");
  if (!ctx) return;
  if (charts.repairsSplit) charts.repairsSplit.destroy();

  charts.repairsSplit = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Out of Warranty (OOW)", "Insurance Repairs"],
      datasets: [{
        data: [s.repairs_oow_volume, s.repairs_insurance_volume],
        backgroundColor: ["#f59e0b", "#06b6d4"],
        borderColor: "#0e131f",
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { color: "#94a3b8" } }
      }
    }
  });
}

// 5. Update Accessories Tab
function updateAccessoriesTab(data) {
  const s = data.summary || {};
  document.getElementById("kpi-acc-revenue").innerText = formatCurrency(s.accessories_revenue);
  document.getElementById("kpi-acc-volume").innerText = formatNumber(s.accessories_volume);
  document.getElementById("kpi-protection-bundles").innerText = formatNumber(s.protection_bundles_volume);
}

// 6. Update Traffic Tab
function updateTrafficTab(data) {
  const s = data.summary || {};
  document.getElementById("funnel-traffic").innerText = formatNumber(s.foot_traffic_total);
  document.getElementById("funnel-tickets").innerText = formatNumber(s.tickets_opened_7day_ma);
  const totalSales = s.activations_total + s.cpo_units_actual + s.repairs_oow_volume;
  document.getElementById("funnel-sales").innerText = formatNumber(totalSales);
  document.getElementById("funnel-conversion-rate").innerText = (s.conversion_rate_pct || 0) + "%";

  if (s.foot_traffic_total > 0) {
    const tPct = Math.min(100, Math.round((s.tickets_opened_7day_ma / s.foot_traffic_total) * 100));
    const sPct = Math.min(100, Math.round((totalSales / s.foot_traffic_total) * 100));
    document.getElementById("funnel-tickets-bar").style.width = Math.max(8, tPct) + "%";
    document.getElementById("funnel-sales-bar").style.width = Math.max(5, sPct) + "%";
  }
}

// 7. Update Benchmark & Ranking Tab
function updateBenchmarkTab(data) {
  const stores = data.store_rows || [];
  const ctx = document.getElementById("chart-multi-store-bar");
  if (!ctx || !stores.length) return;
  if (charts.multiStoreBar) charts.multiStoreBar.destroy();

  const labels = stores.map(s => s.name);
  const revenues = stores.map(s => s.revenue);
  const activations = stores.map(s => s.activations);

  charts.multiStoreBar = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Gross Revenue ($)",
          data: revenues,
          backgroundColor: "#10b981",
          borderRadius: 6,
          yAxisID: "y"
        },
        {
          label: "Activations (Units)",
          data: activations,
          backgroundColor: "#8b5cf6",
          borderRadius: 6,
          yAxisID: "y1"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#94a3b8" } }
      },
      scales: {
        y: {
          type: "linear",
          position: "left",
          grid: { color: "rgba(255,255,255,0.05)" },
          ticks: { color: "#10b981", callback: v => "$" + (v / 1000) + "k" }
        },
        y1: {
          type: "linear",
          position: "right",
          grid: { display: false },
          ticks: { color: "#8b5cf6" }
        },
        x: {
          grid: { display: false },
          ticks: { color: "#94a3b8", maxRotation: 45, minRotation: 20 }
        }
      }
    }
  });
}

// Weekly Trends Fetcher & Visualizer
async function loadWeeklyTrends(locId) {
  const metrics = [
    { type: "activation", chartId: "chart-weekly-activations", color: "#8b5cf6" },
    { type: "cpo", chartId: "chart-weekly-cpo", color: "#10b981" },
    { type: "repair", chartId: "chart-weekly-repairs", color: "#f59e0b" },
    { type: "traffic", chartId: "chart-weekly-traffic", color: "#f43f5e" }
  ];

  for (const m of metrics) {
    try {
      const res = await fetch(`/api/weekly-trend?metric_type=${m.type}&location_id=${locId}`);
      if (!res.ok) continue;
      const data = await res.json();
      renderWeeklyLineChart(m.chartId, data.trend || [], m.color);
    } catch (err) {
      console.warn("Trend fetch error:", err);
    }
  }
}

function renderWeeklyLineChart(canvasId, trendData, color) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  if (charts[canvasId]) charts[canvasId].destroy();

  const labels = trendData.map(t => t.week_end_date);
  const values = trendData.map(t => t.total);

  charts[canvasId] = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [{
        label: "Weekly Volume",
        data: values,
        borderColor: color,
        backgroundColor: color.replace(")", ", 0.1)").replace("rgb", "rgba"),
        fill: true,
        tension: 0.35,
        pointBackgroundColor: color,
        pointRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: {
          grid: { color: "rgba(255,255,255,0.05)" },
          ticks: { color: "#94a3b8" }
        },
        x: {
          grid: { display: false },
          ticks: { color: "#94a3b8" }
        }
      }
    }
  });
}

// Parameter Filter Modal & Visibility Controls
function openParamModal() {
  document.getElementById("param-modal").classList.add("active");
}

function closeParamModal() {
  document.getElementById("param-modal").classList.remove("active");
}

function toggleCardVisibility(kpiName, isVisible) {
  document.querySelectorAll(`[data-kpi="${kpiName}"]`).forEach(card => {
    card.style.display = isVisible ? "block" : "none";
  });
  // Save preference to localStorage
  try {
    const prefs = JSON.parse(localStorage.getItem("mk_kpi_prefs") || "{}");
    prefs[kpiName] = isVisible;
    localStorage.setItem("mk_kpi_prefs", JSON.stringify(prefs));
  } catch (e) {}
}

function applyPreset(presetType) {
  const configs = {
    executive: { revenue: true, volume: true, activations: true, cpo: true, repairs: true, conversion: true },
    sales: { revenue: true, volume: true, activations: true, cpo: true, repairs: false, conversion: true },
    service: { revenue: false, volume: false, activations: false, cpo: false, repairs: true, conversion: true },
    all: { revenue: true, volume: true, activations: true, cpo: true, repairs: true, conversion: true }
  };
  const cfg = configs[presetType] || configs.all;
  for (const [kpi, val] of Object.entries(cfg)) {
    const chk = document.getElementById(`chk-${kpi}`);
    if (chk) chk.checked = val;
    toggleCardVisibility(kpi, val);
  }
}

function initParamToggles() {
  try {
    const prefs = JSON.parse(localStorage.getItem("mk_kpi_prefs") || "{}");
    for (const [kpi, val] of Object.entries(prefs)) {
      const chk = document.getElementById(`chk-${kpi}`);
      if (chk) chk.checked = val;
      toggleCardVisibility(kpi, val);
    }
  } catch (e) {}
}

function exportData() {
  const locSelect = document.getElementById("location-select");
  const periodSelect = document.getElementById("period-select");
  if (!locSelect || !periodSelect) return;
  window.location.href = `/api/export-csv?period_id=${periodSelect.value}&location_id=${locSelect.value}`;
}
