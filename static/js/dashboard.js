/**
 * Franchise Scorecard & Operations Dashboard
 * Dynamic data visualizer, multi-select store filter, ChartDataLabels engine
 */

// Register Chart.js DataLabels plugin globally if available
if (window.ChartDataLabels) {
  Chart.register(ChartDataLabels);
}

let charts = {};

document.addEventListener("DOMContentLoaded", function () {
  loadDashboardData();
  initParamToggles();

  // Close store dropdown when clicking outside
  document.addEventListener("click", function (e) {
    const container = document.getElementById("store-multiselect-container");
    const menu = document.getElementById("store-dropdown-menu");
    if (container && menu && !container.contains(e.target)) {
      menu.style.display = "none";
    }
  });
});

// Switch active tab
function switchTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === tabId);
  });
  document.querySelectorAll(".tab-panel").forEach(panel => {
    panel.classList.toggle("active", panel.id === tabId);
  });
  // Trigger chart re-render/resize on tab switch after DOM paint
  setTimeout(() => {
    Object.values(charts).forEach(c => {
      if (c && c.resize) {
        c.resize();
        if (c.update) c.update("none");
      }
    });
  }, 40);
}

// Format helpers
const formatCurrency = num => "$" + Number(num || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
const formatCompactCurrency = num => {
  const n = Number(num || 0);
  if (Math.abs(n) >= 1000000) return "$" + (n / 1000000).toFixed(1) + "M";
  if (Math.abs(n) >= 1000) return "$" + (n / 1000).toFixed(1) + "k";
  return "$" + n.toLocaleString("en-US", { maximumFractionDigits: 0 });
};
const formatNumber = num => Number(num || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });

// Multi-select Store Dropdown Controls
function toggleStoreDropdown() {
  const menu = document.getElementById("store-dropdown-menu");
  if (!menu) return;
  menu.style.display = menu.style.display === "none" || !menu.style.display ? "block" : "none";
}

function setAllStoreCheckboxes(checked) {
  document.querySelectorAll(".loc-checkbox").forEach(cb => {
    cb.checked = checked;
  });
  onLocationSelectionChange();
}

function filterStoreCheckboxes() {
  const q = document.getElementById("store-search-box").value.toLowerCase();
  document.querySelectorAll(".store-checkbox-item").forEach(item => {
    const name = item.dataset.name || "";
    item.style.display = name.includes(q) ? "flex" : "none";
  });
}

function getSelectedLocationIds() {
  const checkedBoxes = Array.from(document.querySelectorAll(".loc-checkbox:checked"));
  const allBoxes = Array.from(document.querySelectorAll(".loc-checkbox"));

  if (checkedBoxes.length === 0) {
    return "none";
  }
  if (checkedBoxes.length === allBoxes.length) {
    return "all";
  }
  return checkedBoxes.map(cb => cb.value).join(",");
}

function onLocationSelectionChange() {
  const checkedBoxes = Array.from(document.querySelectorAll(".loc-checkbox:checked"));
  const allBoxes = Array.from(document.querySelectorAll(".loc-checkbox"));
  const labelEl = document.getElementById("store-multiselect-label");

  if (labelEl) {
    if (checkedBoxes.length === 0) {
      labelEl.innerText = "No stores selected";
    } else if (checkedBoxes.length === allBoxes.length) {
      labelEl.innerText = `All Accessible Stores (${allBoxes.length})`;
    } else if (checkedBoxes.length === 1) {
      const storeNum = checkedBoxes[0].dataset.storeNum;
      const storeName = (checkedBoxes[0].dataset.name || "").replace("Mobile Klinik ", "");
      labelEl.innerText = `#${storeNum} ${storeName}`;
    } else {
      labelEl.innerText = `${checkedBoxes.length} Stores Selected`;
    }
  }

  loadDashboardData();
}

// Fetch scorecard data and render everything
async function loadDashboardData() {
  const periodSelect = document.getElementById("period-select");
  if (!periodSelect) return;

  const locParam = getSelectedLocationIds();
  const periodId = periodSelect.value;

  try {
    const res = await fetch(`/api/scorecard-data?period_id=${periodId}&location_id=${locParam}`);
    if (!res.ok) throw new Error("Failed to fetch scorecard data");
    const data = await res.json();

    updateExecutiveTab(data);
    updateActivationsTab(data);
    updateCpoTab(data);
    updateRepairsTab(data);
    updateAccessoriesTab(data);
    updateTrafficTab(data);
    updateBenchmarkTab(data);

    // Also fetch weekly trends for the selected locations
    loadWeeklyTrends(locParam);

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
  
  if (s.foot_traffic_total > 0) {
    document.getElementById("kpi-conversion-rate").innerText = (s.conversion_rate_pct || 0) + "%";
    document.getElementById("kpi-traffic-count").innerText = formatNumber(s.foot_traffic_total);
  } else {
    document.getElementById("kpi-conversion-rate").innerHTML = "<span style='font-size:0.85rem;color:var(--accent-amber);'>Sensors Offline</span>";
    document.getElementById("kpi-traffic-count").innerHTML = "<span style='font-size:0.85rem;color:var(--text-muted);'>N/A</span>";
  }

  // Render Revenue Mix Bar Chart with Datalabels
  renderRevenueMixChart(s);

  // Render Benchmark Radar Chart with Datalabels and Normalized Multi-Store Index
  renderBenchmarkRadarChart(s, data.benchmark || {}, data);

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
      layout: { padding: { top: 25 } },
      plugins: {
        legend: { display: false },
        datalabels: {
          display: true,
          color: "#ffffff",
          anchor: "end",
          align: "top",
          offset: 4,
          font: { weight: "bold", size: 11 },
          formatter: v => v > 0 ? formatCompactCurrency(v) : ""
        },
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

function renderBenchmarkRadarChart(s, bm, data) {
  const ctx = document.getElementById("chart-benchmark-radar");
  if (!ctx) return;
  if (charts.benchmarkRadar) charts.benchmarkRadar.destroy();

  const bmLabel = document.getElementById("benchmark-region-label");
  if (bmLabel) bmLabel.innerText = `${bm.region || 'West'} Region Average (${bm.store_count || 0} Stores)`;

  const storeCnt = Math.max(1, (data && data.store_rows ? data.store_rows.length : 1));
  const perStoreRev = (s.gross_revenue_actual || 0) / storeCnt;
  const perStoreActs = (s.activations_total || 0) / storeCnt;
  const perStoreCpo = (s.cpo_units_actual || 0) / storeCnt;
  const perStoreRep = (s.repairs_oow_volume || 0) / storeCnt;
  const perStoreTraf = (s.foot_traffic_total || 0) / storeCnt;

  charts.benchmarkRadar = new Chart(ctx, {
    type: "radar",
    data: {
      labels: ["Revenue Index", "Activations", "CPO Units", "Repairs", "Traffic Index"],
      datasets: [
        {
          label: storeCnt > 1 ? `Selected Avg (${storeCnt} Stores)` : "Your Store",
          data: [
            bm.avg_revenue ? Math.round((perStoreRev / bm.avg_revenue) * 100) : 100,
            bm.avg_activations ? Math.round((perStoreActs / bm.avg_activations) * 100) : 100,
            bm.avg_cpo ? Math.round((perStoreCpo / bm.avg_cpo) * 100) : 100,
            bm.avg_repairs ? Math.round((perStoreRep / bm.avg_repairs) * 100) : 100,
            bm.avg_traffic ? Math.round((perStoreTraf / bm.avg_traffic) * 100) : 100
          ],
          borderColor: "#6366f1",
          backgroundColor: "rgba(99, 102, 241, 0.25)",
          pointBackgroundColor: "#6366f1",
          pointRadius: 4
        },
        {
          label: "Regional Baseline (100%)",
          data: [100, 100, 100, 100, 100],
          borderColor: "rgba(255,255,255,0.3)",
          borderDash: [4, 4],
          backgroundColor: "rgba(255,255,255,0.03)",
          pointBackgroundColor: "rgba(255,255,255,0.5)",
          pointRadius: 2
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
        datalabels: {
          display: true,
          color: ctx => ctx.datasetIndex === 0 ? "#a5b4fc" : "transparent",
          font: { weight: "600", size: 10 },
          align: "top",
          formatter: v => v + "%"
        },
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

  const totActs = (s.activations_new || 0) + (s.activations_renewals || 0) + (s.activations_migrations || 0);

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
        legend: { position: "bottom", labels: { color: "#94a3b8" } },
        datalabels: {
          display: true,
          color: "#ffffff",
          font: { weight: "bold", size: 11 },
          formatter: (v, ctx) => {
            if (!v || totActs === 0) return "";
            const pct = Math.round((v / totActs) * 100);
            return `${v}\n(${pct}%)`;
          }
        }
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

  const totRep = (s.repairs_oow_volume || 0) + (s.repairs_insurance_volume || 0);

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
        legend: { position: "bottom", labels: { color: "#94a3b8" } },
        datalabels: {
          display: true,
          color: "#ffffff",
          font: { weight: "bold", size: 11 },
          formatter: (v, ctx) => {
            if (!v || totRep === 0) return "";
            const pct = Math.round((v / totRep) * 100);
            return `${v}\n(${pct}%)`;
          }
        }
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

  if (s.tickets_opened_7day_ma > 0) {
    document.getElementById("funnel-tickets").innerText = formatNumber(s.tickets_opened_7day_ma);
  } else {
    document.getElementById("funnel-tickets").innerHTML = "<span style='font-size:0.8rem;color:var(--text-muted);'>Not Tracked in Period</span>";
  }

  const totalSales = (s.activations_total || 0) + (s.cpo_units_actual || 0) + (s.repairs_oow_volume || 0);
  document.getElementById("funnel-sales").innerText = formatNumber(totalSales);

  if (s.foot_traffic_total > 0) {
    const rate = Math.round((totalSales / s.foot_traffic_total) * 1000) / 10;
    if (rate > 100) {
      document.getElementById("funnel-conversion-rate").innerHTML = `
        <span>${rate}%</span>
        <div style="font-size:0.75rem;font-weight:500;color:var(--accent-amber);margin-top:6px;line-height:1.3;">
          ⚠️ Corporate sensor outage occurred in Week 2. Rate reflects 18-day sales vs Week 1 captured traffic.
        </div>
      `;
    } else {
      document.getElementById("funnel-conversion-rate").innerText = rate + "%";
    }
    const tPct = s.foot_traffic_total > 0 ? Math.min(100, Math.round((s.tickets_opened_7day_ma / s.foot_traffic_total) * 100)) : 0;
    const sPct = s.foot_traffic_total > 0 ? Math.min(100, Math.round((totalSales / s.foot_traffic_total) * 100)) : 0;
    document.getElementById("funnel-tickets-bar").style.width = tPct > 0 ? Math.max(5, tPct) + "%" : "0%";
    document.getElementById("funnel-sales-bar").style.width = sPct > 0 ? Math.max(5, sPct) + "%" : "0%";
  } else {
    document.getElementById("funnel-conversion-rate").innerHTML = "<span style='font-size:1.1rem;color:var(--accent-amber);'>Sensors Offline for Period</span>";
    document.getElementById("funnel-tickets-bar").style.width = "0%";
    document.getElementById("funnel-sales-bar").style.width = "0%";
  }
}

// 7. Update Benchmark & Ranking Tab
function updateBenchmarkTab(data) {
  const stores = data.store_rows || [];
  const ctx = document.getElementById("chart-multi-store-bar");
  if (!ctx || !stores.length) return;
  if (charts.multiStoreBar) charts.multiStoreBar.destroy();

  const labels = stores.map(s => s.name.replace("Mobile Klinik ", ""));
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
      layout: { padding: { top: 25 } },
      plugins: {
        legend: { labels: { color: "#94a3b8" } },
        datalabels: {
          display: true,
          font: { weight: "600", size: 9 },
          anchor: "end",
          align: "top",
          offset: 2,
          color: ctx => ctx.datasetIndex === 0 ? "#34d399" : "#c084fc",
          formatter: (v, ctx) => {
            if (!v) return "";
            return ctx.datasetIndex === 0 ? formatCompactCurrency(v) : v;
          }
        }
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

// Weekly Trends Fetcher & Visualizer with Datalabels
async function loadWeeklyTrends(locParam) {
  const metrics = [
    { type: "activation", chartId: "chart-weekly-activations", color: "#8b5cf6", format: v => v },
    { type: "cpo", chartId: "chart-weekly-cpo", color: "#10b981", format: v => v },
    { type: "repair", chartId: "chart-weekly-repairs", color: "#f59e0b", format: v => v },
    { type: "traffic", chartId: "chart-weekly-traffic", color: "#f43f5e", format: v => formatNumber(v) }
  ];

  for (const m of metrics) {
    try {
      const res = await fetch(`/api/weekly-trend?metric_type=${m.type}&location_id=${locParam}`);
      if (!res.ok) continue;
      const data = await res.json();
      renderWeeklyLineChart(m.chartId, data.trend || [], m.color, m.format);
    } catch (err) {
      console.warn("Trend fetch error:", err);
    }
  }
}

function renderWeeklyLineChart(canvasId, trendData, color, formatter) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  if (charts[canvasId]) charts[canvasId].destroy();

  const labels = trendData.map(t => {
    // Format YYYY-MM-DD to readable Mon DD (e.g. Jan 05)
    const parts = t.week_end_date.split("-");
    if (parts.length === 3) {
      const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const mIdx = parseInt(parts[1], 10) - 1;
      return `${months[mIdx]} ${parts[2]}`;
    }
    return t.week_end_date;
  });
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
        pointBorderColor: "#ffffff",
        pointBorderWidth: 1.5,
        pointRadius: 5,
        pointHoverRadius: 7
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { top: 22, right: 12 } },
      plugins: {
        legend: { display: false },
        datalabels: {
          display: true,
          color: "#ffffff",
          align: "top",
          offset: 6,
          font: { weight: "700", size: 10 },
          formatter: v => v > 0 ? (formatter ? formatter(v) : v) : ""
        }
      },
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
  const periodSelect = document.getElementById("period-select");
  if (!periodSelect) return;
  const locParam = getSelectedLocationIds();
  window.location.href = `/api/export-csv?period_id=${periodSelect.value}&location_id=${locParam}`;
}
