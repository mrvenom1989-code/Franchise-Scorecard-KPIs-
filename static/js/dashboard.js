/**
 * Franchise Scorecard & Operations Dashboard
 * Dynamic data visualizer, multi-select store filter, ChartDataLabels engine
 */

// Register Chart.js DataLabels plugin globally if available
if (window.ChartDataLabels) {
  Chart.register(ChartDataLabels);
}

let charts = {};
let currentScorecardData = null;
let currentBenchmarkMode = "regional"; // 'regional', 'global', 'portfolio', 'compare_all'
let chartModes = {
  revenue: "timeline",
  activations: "timeline",
  cpo: "timeline",
  repairs: "timeline",
  traffic: "timeline"
};
let monthlyTrendsData = null;

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
    currentScorecardData = data;

    updateExecutiveTab(data);
    updateActivationsTab(data);
    updateCpoTab(data);
    updateRepairsTab(data);
    updateAccessoriesTab(data);
    updateTrafficTab(data);
    updateBenchmarkTab(data);

    // Fetch monthly historical trends & YoY/MoM comparisons across all tabs
    loadMonthlyTrends(locParam);

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

  const migSub = document.getElementById("kpi-activations-migrations-sub");
  if (migSub) migSub.innerText = formatNumber(s.activations_migrations || 0);

  const renSub = document.getElementById("kpi-activations-renewals");
  if (renSub) renSub.innerText = formatNumber(s.activations_renewals || 0);

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

  // Render Benchmark Radar Chart
  renderBenchmarkRadarChart(s, currentBenchmarkMode, data);

  // Render Store Leaderboard Table with Top 3 Highlights
  renderLeaderboardTable(data.store_rows || []);

  if (window.feather) feather.replace();
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
        borderColor: ["#34d399", "#fbbf24", "#22d3ee", "#818cf8"],
        borderWidth: 1.5,
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { top: 32 } },
      plugins: {
        legend: { display: false },
        datalabels: {
          display: true,
          color: ctx => ["#34d399", "#fbbf24", "#22d3ee", "#a5b4fc"][ctx.dataIndex] || "#ffffff",
          backgroundColor: "rgba(15, 23, 42, 0.94)",
          borderColor: ctx => ["#10b981", "#f59e0b", "#06b6d4", "#6366f1"][ctx.dataIndex] || "#38bdf8",
          borderWidth: 1.5,
          borderRadius: 6,
          padding: { top: 3, bottom: 3, left: 6, right: 6 },
          anchor: "end",
          align: "top",
          offset: 5,
          font: { family: "'Plus Jakarta Sans', sans-serif", weight: "800", size: 11 },
          formatter: v => v > 0 ? formatCompactCurrency(v) : ""
        },
        tooltip: {
          callbacks: { label: ctx => " " + formatCurrency(ctx.parsed.y) }
        }
      },
      scales: {
        y: {
          grid: { color: "rgba(255, 255, 255, 0.08)" },
          ticks: { color: "#e2e8f0", font: { weight: "600", size: 11 }, callback: v => "$" + (v / 1000) + "k" }
        },
        x: {
          grid: { display: false },
          ticks: { color: "#e2e8f0", font: { weight: "600", size: 11 } }
        }
      }
    }
  });
}

// Benchmark Mode Switcher (Req 4: Regional, Global Network, User Stores, Compare All)
function setBenchmarkMode(mode) {
  currentBenchmarkMode = mode;
  document.querySelectorAll(".bm-toggle-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.bm === mode);
  });
  if (currentScorecardData) {
    renderBenchmarkRadarChart(currentScorecardData.summary || {}, currentBenchmarkMode, currentScorecardData);
  }
}

function renderBenchmarkRadarChart(s, modeOrBm, data) {
  const ctx = document.getElementById("chart-benchmark-radar");
  if (!ctx) return;
  if (charts.benchmarkRadar) charts.benchmarkRadar.destroy();

  const bmMode = typeof modeOrBm === "string" ? modeOrBm : currentBenchmarkMode;
  const regBm = (data && data.regional_benchmark) || (data && data.benchmark) || {};
  const globBm = (data && data.global_benchmark) || {};
  const portBm = (data && data.portfolio_benchmark) || {};

  const bmLabel = document.getElementById("benchmark-region-label");

  const storeCnt = Math.max(1, (data && data.store_rows ? data.store_rows.length : 1));
  const perStoreRev = (s.gross_revenue_actual || 0) / storeCnt;
  const perStoreActs = (s.activations_total || 0) / storeCnt;
  const perStoreCpo = (s.cpo_units_actual || 0) / storeCnt;
  const perStoreRep = (s.repairs_oow_volume || 0) / storeCnt;
  const perStoreTraf = (s.foot_traffic_total || 0) / storeCnt;

  const calcIndices = (bm) => [
    bm && bm.avg_revenue ? Math.round((perStoreRev / bm.avg_revenue) * 100) : 100,
    bm && bm.avg_activations ? Math.round((perStoreActs / bm.avg_activations) * 100) : 100,
    bm && bm.avg_cpo ? Math.round((perStoreCpo / bm.avg_cpo) * 100) : 100,
    bm && bm.avg_repairs ? Math.round((perStoreRep / bm.avg_repairs) * 100) : 100,
    bm && bm.avg_traffic ? Math.round((perStoreTraf / bm.avg_traffic) * 100) : 100
  ];

  let datasets = [];

  if (bmMode === "compare_all") {
    if (bmLabel) bmLabel.innerText = "Multi-Benchmark Comparison (Selected vs Region vs Global)";
    datasets = [
      {
        label: storeCnt > 1 ? `Selected (${storeCnt} Stores)` : "Your Store",
        data: calcIndices(globBm),
        borderColor: "#06b6d4",
        backgroundColor: "rgba(6, 182, 212, 0.22)",
        pointBackgroundColor: "#06b6d4",
        pointRadius: 4
      },
      {
        label: `Regional (${regBm.region || 'Region'} Avg)`,
        data: globBm.avg_revenue ? [
          Math.round((regBm.avg_revenue / globBm.avg_revenue) * 100),
          Math.round((regBm.avg_activations / globBm.avg_activations) * 100),
          Math.round((regBm.avg_cpo / globBm.avg_cpo) * 100),
          Math.round((regBm.avg_repairs / globBm.avg_repairs) * 100),
          Math.round((regBm.avg_traffic / globBm.avg_traffic) * 100)
        ] : [100, 100, 100, 100, 100],
        borderColor: "#a855f7",
        backgroundColor: "rgba(168, 85, 247, 0.15)",
        pointBackgroundColor: "#a855f7",
        pointRadius: 3
      },
      {
        label: "Global Baseline (100%)",
        data: [100, 100, 100, 100, 100],
        borderColor: "rgba(255,255,255,0.3)",
        borderDash: [4, 4],
        backgroundColor: "rgba(255,255,255,0.02)",
        pointBackgroundColor: "rgba(255,255,255,0.5)",
        pointRadius: 2
      }
    ];
  } else {
    let targetBm = regBm;
    let bmTitle = `${regBm.region || 'West'} Region Average (${regBm.store_count || 0} Stores)`;
    let baselineName = "Regional Baseline (100%)";

    if (bmMode === "global") {
      targetBm = globBm;
      bmTitle = `Global Network Average (${globBm.store_count || 0} Franchise Stores)`;
      baselineName = "Global Network Baseline (100%)";
    } else if (bmMode === "portfolio") {
      if (portBm && portBm.store_count) {
        targetBm = portBm;
        bmTitle = `Your Multi-Store Portfolio Average (${portBm.store_count} Stores)`;
        baselineName = "Your Portfolio Baseline (100%)";
      } else {
        targetBm = regBm;
        bmTitle = `Single Store Profile (Comparing with ${regBm.region || 'Regional'} Benchmark)`;
        baselineName = "Regional Baseline (100%)";
      }
    }

    if (bmLabel) bmLabel.innerText = bmTitle;

    datasets = [
      {
        label: storeCnt > 1 ? `Selected Avg (${storeCnt} Stores)` : "Your Store",
        data: calcIndices(targetBm),
        borderColor: "#6366f1",
        backgroundColor: "rgba(99, 102, 241, 0.25)",
        pointBackgroundColor: "#6366f1",
        pointRadius: 4
      },
      {
        label: baselineName,
        data: [100, 100, 100, 100, 100],
        borderColor: "rgba(255,255,255,0.3)",
        borderDash: [4, 4],
        backgroundColor: "rgba(255,255,255,0.03)",
        pointBackgroundColor: "rgba(255,255,255,0.5)",
        pointRadius: 2
      }
    ];
  }

  charts.benchmarkRadar = new Chart(ctx, {
    type: "radar",
    data: {
      labels: ["Revenue Index", "Activations", "CPO Units", "Repairs", "Traffic Index"],
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          grid: { color: "rgba(255, 255, 255, 0.08)" },
          angleLines: { color: "rgba(255, 255, 255, 0.08)" },
          ticks: { display: false },
          pointLabels: { color: "#e2e8f0", font: { family: "'Plus Jakarta Sans', sans-serif", size: 11, weight: "600" } }
        }
      },
      plugins: {
        legend: { labels: { color: "#e2e8f0", font: { family: "'Plus Jakarta Sans', sans-serif", size: 12, weight: "600" } } },
        datalabels: {
          display: true,
          color: ctx => ctx.datasetIndex === 0 ? "#818cf8" : "transparent",
          backgroundColor: "rgba(15, 23, 42, 0.94)",
          borderColor: "#6366f1",
          borderWidth: 1.5,
          borderRadius: 5,
          padding: { top: 2, bottom: 2, left: 5, right: 5 },
          font: { weight: "800", size: 10 },
          align: "top",
          formatter: v => v + "%"
        },
        tooltip: {
          callbacks: { label: ctx => ` ${ctx.dataset.label}: ${Math.round(ctx.raw)}% of baseline` }
        }
      }
    }
  });
}

// Store Performance Leaderboard with Top 3 Highlights (Req 5)
function renderLeaderboardTable(stores) {
  const tbody = document.getElementById("leaderboard-tbody");
  const countEl = document.getElementById("leaderboard-count");
  if (!tbody) return;

  if (countEl) countEl.innerText = `Showing ${stores.length} store(s)`;
  tbody.innerHTML = "";

  stores.forEach((st, idx) => {
    const tr = document.createElement("tr");
    let rankBadge = "";
    if (idx === 0) {
      tr.className = "top-performer rank-1";
      rankBadge = `<span class="rank-badge rank-1">🥇 #1</span>`;
    } else if (idx === 1) {
      tr.className = "top-performer rank-2";
      rankBadge = `<span class="rank-badge rank-2">🥈 #2</span>`;
    } else if (idx === 2) {
      tr.className = "top-performer rank-3";
      rankBadge = `<span class="rank-badge rank-3">🥉 #3</span>`;
    } else {
      tr.className = "";
      rankBadge = `<span class="rank-badge rank-default">#${idx + 1}</span>`;
    }

    tr.innerHTML = `
      <td style="text-align: center;">${rankBadge}</td>
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

// 2. Update Activations Tab (Req 1 & 2: Architecture Rule & 6 KPI Cards)
function updateActivationsTab(data) {
  const s = data.summary || {};

  // Banner Total Activations (Total = New + Migrations)
  const bannerTotal = document.getElementById("kpi-act-total-banner");
  if (bannerTotal) bannerTotal.innerText = formatNumber(s.activations_total || 0);

  // 6 Dedicated KPI Cards
  const actNewEl = document.getElementById("kpi-act-new");
  if (actNewEl) actNewEl.innerText = formatNumber(s.activations_new || 0);

  const telusPostEl = document.getElementById("kpi-act-telus-post");
  if (telusPostEl) telusPostEl.innerText = formatNumber(s.activations_telus_post || 0);

  const koodoPostEl = document.getElementById("kpi-act-koodo-post");
  if (koodoPostEl) koodoPostEl.innerText = formatNumber(s.activations_koodo_post || 0);

  const koodoPreEl = document.getElementById("kpi-act-koodo-pre");
  if (koodoPreEl) koodoPreEl.innerText = formatNumber(s.activations_koodo_pre || 0);

  const renewalsEl = document.getElementById("kpi-act-renewals");
  if (renewalsEl) renewalsEl.innerText = formatNumber(s.activations_renewals || 0);

  const migrationsEl = document.getElementById("kpi-act-migrations");
  if (migrationsEl) migrationsEl.innerText = formatNumber(s.activations_migrations || 0);

  // Doughnut Breakdown
  const ctx = document.getElementById("chart-activation-types");
  if (!ctx) return;
  if (charts.activationTypes) charts.activationTypes.destroy();

  const totActs = (s.activations_new || 0) + (s.activations_renewals || 0) + (s.activations_migrations || 0);

  charts.activationTypes = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["New Activations", "Renewals", "Migrations"],
      datasets: [{
        data: [s.activations_new || 0, s.activations_renewals || 0, s.activations_migrations || 0],
        backgroundColor: ["#a855f7", "#10b981", "#06b6d4"],
        borderColor: "#0e131f",
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { color: "#e2e8f0", font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 12 } } },
        datalabels: {
          display: true,
          color: "#ffffff",
          backgroundColor: "rgba(15, 23, 42, 0.94)",
          borderColor: "rgba(255, 255, 255, 0.25)",
          borderWidth: 1.5,
          borderRadius: 6,
          padding: { top: 3, bottom: 3, left: 6, right: 6 },
          font: { family: "'Plus Jakarta Sans', sans-serif", weight: "800", size: 11 },
          formatter: (v) => {
            if (!v || totActs === 0) return "";
            const pct = Math.round((v / totActs) * 100);
            return `${v} (${pct}%)`;
          }
        }
      }
    }
  });
}

// 3. Update CPO Hardware Tab
function updateCpoTab(data) {
  const s = data.summary || {};
  const cpoTot = document.getElementById("disp-cpo-total-tab");
  if (cpoTot) cpoTot.innerText = formatNumber(s.cpo_units_actual || 0);

  const cpoRev = document.getElementById("disp-cpo-rev-tab");
  if (cpoRev) cpoRev.innerText = formatCurrency(s.cpo_revenue_actual || 0);

  const cpoAtt = document.getElementById("disp-cpo-attached-tab");
  if (cpoAtt) cpoAtt.innerText = formatNumber(s.cpo_attach_activations_count || 0);

  const cpoTrade = document.getElementById("disp-cpo-tradeins-tab");
  if (cpoTrade) cpoTrade.innerText = formatNumber(s.trade_in_units || 0);

  const attachDisp = document.getElementById("cpo-attach-rate-display");
  if (attachDisp) attachDisp.innerText = (s.cpo_attach_rate_pct || 0) + "%";

  const dispTot = document.getElementById("disp-cpo-total");
  if (dispTot) dispTot.innerText = formatNumber(s.cpo_units_actual || 0);

  const dispAtt = document.getElementById("disp-cpo-attached");
  if (dispAtt) dispAtt.innerText = formatNumber(s.cpo_attach_activations_count || 0);

  const dispTrade = document.getElementById("disp-trade-ins");
  if (dispTrade) dispTrade.innerText = formatNumber(s.trade_in_units || 0);
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
        data: [s.repairs_oow_volume || 0, s.repairs_insurance_volume || 0],
        backgroundColor: ["#f59e0b", "#06b6d4"],
        borderColor: "#0e131f",
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { color: "#e2e8f0", font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 12 } } },
        datalabels: {
          display: true,
          color: "#ffffff",
          backgroundColor: "rgba(15, 23, 42, 0.94)",
          borderColor: "rgba(255, 255, 255, 0.25)",
          borderWidth: 1.5,
          borderRadius: 6,
          padding: { top: 3, bottom: 3, left: 6, right: 6 },
          font: { family: "'Plus Jakarta Sans', sans-serif", weight: "800", size: 11 },
          formatter: (v) => {
            if (!v || totRep === 0) return "";
            const pct = Math.round((v / totRep) * 100);
            return `${v} (${pct}%)`;
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
      layout: { padding: { top: 32 } },
      plugins: {
        legend: { labels: { color: "#e2e8f0", font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 12 } } },
        datalabels: {
          display: true,
          font: { family: "'Plus Jakarta Sans', sans-serif", weight: "800", size: 11 },
          anchor: "end",
          align: "top",
          offset: 5,
          color: ctx => ctx.datasetIndex === 0 ? "#34d399" : "#c084fc",
          backgroundColor: "rgba(15, 23, 42, 0.94)",
          borderColor: ctx => ctx.datasetIndex === 0 ? "#10b981" : "#8b5cf6",
          borderWidth: 1.5,
          borderRadius: 6,
          padding: { top: 3, bottom: 3, left: 6, right: 6 },
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
          grid: { color: "rgba(255, 255, 255, 0.08)" },
          ticks: { color: "#34d399", font: { weight: "600", size: 11 }, callback: v => "$" + (v / 1000) + "k" }
        },
        y1: {
          type: "linear",
          position: "right",
          grid: { display: false },
          ticks: { color: "#c084fc", font: { weight: "600", size: 11 } }
        },
        x: {
          grid: { display: false },
          ticks: { color: "#e2e8f0", font: { weight: "600", size: 11 }, maxRotation: 45, minRotation: 20 }
        }
      }
    }
  });
}

// Chart View Switcher: Toggle between 'timeline' (14-Mo Trend) and 'yoy' (2025 vs 2026 Overlay)
function setChartViewMode(metric, mode, btn) {
  chartModes[metric] = mode;
  const switcher = document.getElementById(`switcher-${metric}`);
  if (switcher) {
    switcher.querySelectorAll(".chart-view-btn").forEach(b => {
      b.classList.toggle("active", b === btn);
    });
  }
  if (!monthlyTrendsData) return;
  const trend = monthlyTrendsData.trend || [];
  const yoyByMonth = monthlyTrendsData.yoy_by_month || [];

  if (metric === "revenue") renderExecutiveRevenueTrendChart(trend, yoyByMonth, mode);
  else if (metric === "activations") renderMonthlyActivationsChart(trend, yoyByMonth, mode);
  else if (metric === "cpo") renderMonthlyCPOChart(trend, yoyByMonth, mode);
  else if (metric === "repairs") renderMonthlyRepairsChart(trend, yoyByMonth, mode);
  else if (metric === "traffic") renderMonthlyTrafficChart(trend, yoyByMonth, mode);
}

// Monthly Trends Fetcher & Visualizer with YoY / MoM Data (Req 3)
async function loadMonthlyTrends(locParam) {
  try {
    const res = await fetch(`/api/monthly-trend?location_id=${locParam}`);
    if (!res.ok) throw new Error("Failed to fetch monthly trends");
    const data = await res.json();
    monthlyTrendsData = data;
    const trend = data.trend || [];
    const yoyByMonth = data.yoy_by_month || [];
    const growthMatrix = data.growth_matrix || [];
    const mom = data.mom || {};
    const yoy = data.yoy || {};

    // 1. Render Executive Pulse Growth Matrix (YoY & MoM Comparative Breakdown)
    renderExecutiveGrowthMatrix(growthMatrix, mom, yoy);

    // 2. Render Charts across all tabs (with Timeline & YoY modes)
    renderExecutiveRevenueTrendChart(trend, yoyByMonth, chartModes.revenue);
    renderMonthlyActivationsChart(trend, yoyByMonth, chartModes.activations);
    renderMonthlyCPOChart(trend, yoyByMonth, chartModes.cpo);
    renderMonthlyRepairsChart(trend, yoyByMonth, chartModes.repairs);
    renderMonthlyTrafficChart(trend, yoyByMonth, chartModes.traffic);

    // 3. Helper to format delta tags
    const applyDelta = (elementId, deltaObj, label) => {
      const el = document.getElementById(elementId);
      if (!el) return;
      if (!deltaObj || deltaObj.current === undefined) {
        el.innerText = `${label}: --`;
        el.className = "delta-tag neutral";
        return;
      }
      const pct = deltaObj.pct !== undefined ? deltaObj.pct : 0;
      const isPos = pct > 0;
      const isNeg = pct < 0;
      const sign = isPos ? "+" : "";
      el.innerText = `${label}: ${sign}${pct}%`;
      el.className = `delta-tag ${isPos ? "positive" : isNeg ? "negative" : "neutral"}`;
      el.title = `Current: ${deltaObj.current}, Previous: ${deltaObj.previous}, Delta: ${deltaObj.delta}`;
    };

    // 4. Update Executive Pulse Header Badges
    applyDelta("badge-exec-rev-yoy", yoy.revenue, "Revenue YoY");
    applyDelta("badge-exec-act-yoy", yoy.activations, "Activations YoY");

    // 5. Update MoM & YoY Badges across detail tabs
    applyDelta("badge-act-mom", mom.activations, `MoM (${mom.previous_period || 'Prior Mo'})`);
    applyDelta("badge-act-yoy", yoy.activations, `YoY (${yoy.prior_year_period || 'Last Yr'})`);

    applyDelta("badge-cpo-units-mom", mom.cpo_units, "MoM");
    applyDelta("badge-cpo-units-yoy", yoy.cpo_units, "YoY");
    applyDelta("badge-cpo-rev-mom", mom.cpo_revenue, "MoM");
    applyDelta("badge-cpo-rev-yoy", yoy.cpo_revenue, "YoY");
    applyDelta("badge-cpo-mom", mom.cpo_units, `MoM (${mom.previous_period || 'Prior Mo'})`);
    applyDelta("badge-cpo-yoy", yoy.cpo_units, `YoY (${yoy.prior_year_period || 'Last Yr'})`);

    applyDelta("badge-rep-rev-mom", mom.repairs_revenue, "MoM");
    applyDelta("badge-rep-rev-yoy", yoy.repairs_revenue, "YoY");
    applyDelta("badge-rep-mom", mom.repairs_volume, `MoM (${mom.previous_period || 'Prior Mo'})`);
    applyDelta("badge-rep-yoy", yoy.repairs_volume, `YoY (${yoy.prior_year_period || 'Last Yr'})`);

    applyDelta("badge-traffic-mom", mom.traffic, `MoM (${mom.previous_period || 'Prior Mo'})`);
    applyDelta("badge-traffic-yoy", yoy.traffic, `YoY (${yoy.prior_year_period || 'Last Yr'})`);

  } catch (err) {
    console.error("Error loading monthly trends:", err);
  }
}

// Executive Pulse: Render Year-on-Year (YoY) & Month-on-Month (MoM) Growth Matrix
function renderExecutiveGrowthMatrix(matrix, mom, yoy) {
  const container = document.getElementById("exec-growth-matrix-grid");
  if (!container) return;

  const currLbl = document.getElementById("matrix-curr-lbl");
  if (currLbl && mom.current_period) currLbl.innerText = mom.current_period;

  const momLbl = document.getElementById("matrix-mom-lbl");
  if (momLbl && mom.previous_period) momLbl.innerText = mom.previous_period;

  const yoyLbl = document.getElementById("matrix-yoy-lbl");
  if (yoyLbl && yoy.prior_year_period) yoyLbl.innerText = yoy.prior_year_period;

  if (!matrix || matrix.length === 0) {
    container.innerHTML = `<div style="color:var(--text-dim);font-size:0.85rem;padding:12px;">Growth metrics loading...</div>`;
    return;
  }

  container.innerHTML = "";
  matrix.forEach(m => {
    let fmtVal = "";
    if (m.format === "currency") fmtVal = formatCurrency(m.current);
    else if (m.format === "percent") fmtVal = (m.current || 0) + "%";
    else fmtVal = formatNumber(m.current);

    const momPct = m.mom_pct !== null && m.mom_pct !== undefined ? m.mom_pct : 0;
    const momClass = momPct > 0 ? "positive" : (momPct < 0 ? "negative" : "neutral");
    const momSign = momPct > 0 ? "+" : "";

    const yoyPct = m.yoy_pct !== null && m.yoy_pct !== undefined ? m.yoy_pct : 0;
    const yoyClass = yoyPct > 0 ? "positive" : (yoyPct < 0 ? "negative" : "neutral");
    const yoySign = yoyPct > 0 ? "+" : "";

    let momPrevFmt = "";
    if (m.mom_previous !== null && m.mom_previous !== undefined) {
      momPrevFmt = m.format === "currency" ? formatCompactCurrency(m.mom_previous) : (m.format === "percent" ? m.mom_previous + "%" : formatNumber(m.mom_previous));
    } else {
      momPrevFmt = "--";
    }

    let yoyPrevFmt = "";
    if (m.yoy_previous !== null && m.yoy_previous !== undefined) {
      yoyPrevFmt = m.format === "currency" ? formatCompactCurrency(m.yoy_previous) : (m.format === "percent" ? m.yoy_previous + "%" : formatNumber(m.yoy_previous));
    } else {
      yoyPrevFmt = "--";
    }

    const card = document.createElement("div");
    card.className = "growth-card";
    card.innerHTML = `
      <div class="growth-card-header">
        <span class="growth-card-title">${m.name}</span>
        <span class="role-pill" style="font-size:0.68rem;background:rgba(255,255,255,0.05);">${m.current_period || ''}</span>
      </div>
      <div class="growth-card-val">${fmtVal}</div>
      <div class="growth-comparisons">
        <div class="growth-row">
          <span class="growth-row-label">
            <i data-feather="calendar" style="width:12px;height:12px;"></i> MoM (${m.mom_period || 'Prior Mo'}):
          </span>
          <span class="growth-row-value">
            <span style="color:var(--text-muted);">${momPrevFmt}</span>
            <span class="delta-tag ${momClass}">${momSign}${momPct}%</span>
          </span>
        </div>
        <div class="growth-row">
          <span class="growth-row-label">
            <i data-feather="clock" style="width:12px;height:12px;"></i> YoY (${m.yoy_period || 'Prior Yr'}):
          </span>
          <span class="growth-row-value">
            <span style="color:var(--text-muted);">${yoyPrevFmt}</span>
            <span class="delta-tag ${yoyClass}">${yoySign}${yoyPct}%</span>
          </span>
        </div>
      </div>
    `;
    container.appendChild(card);
  });

  if (window.feather) feather.replace();
}

// ============================================================================
// HIGH-VISIBILITY DATA LABELS & CHART STYLING ENGINE
// ============================================================================

/**
 * Creates an executive glassmorphic pill badge data label for ChartDataLabels.
 * Prevents numbers from blending into dark backgrounds, lines, or bars.
 */
function makePillDataLabel(options = {}) {
  return {
    display: options.display !== undefined ? options.display : true,
    align: options.align || "top",
    anchor: options.anchor || "end",
    offset: options.offset !== undefined ? options.offset : 6,
    clamp: false,
    clip: false,
    color: options.color || "#ffffff",
    backgroundColor: options.backgroundColor || "rgba(15, 23, 42, 0.95)",
    borderColor: options.borderColor || "rgba(255, 255, 255, 0.25)",
    borderWidth: 1.5,
    borderRadius: 6,
    padding: options.padding || { top: 3, bottom: 3, left: 6, right: 6 },
    font: {
      family: "'Plus Jakarta Sans', -apple-system, sans-serif",
      weight: "800",
      size: options.fontSize || 11
    },
    formatter: options.formatter || (v => (v > 0 ? v : ""))
  };
}

// 1. Executive Monthly Revenue Trend & YoY Comparison Chart
function renderExecutiveRevenueTrendChart(trend, yoyByMonth, mode) {
  const ctx = document.getElementById("chart-executive-revenue-trend");
  if (!ctx) return;
  if (charts.executiveRevenue) charts.executiveRevenue.destroy();

  if (mode === "yoy") {
    const labels = yoyByMonth.map(m => m.month_name);
    const data2025 = yoyByMonth.map(m => (m.p2025 ? m.p2025.revenue : null));
    const data2026 = yoyByMonth.map(m => (m.p2026 ? m.p2026.revenue : null));

    charts.executiveRevenue = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "2025 Revenue (Prior Year)",
            data: data2025,
            backgroundColor: "rgba(245, 158, 11, 0.35)",
            borderColor: "#f59e0b",
            borderWidth: 2,
            borderRadius: 6
          },
          {
            label: "2026 Revenue (Current Year)",
            data: data2026,
            backgroundColor: "#10b981",
            borderColor: "#34d399",
            borderWidth: 2,
            borderRadius: 6
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 35, bottom: 5, left: 5, right: 10 } },
        plugins: {
          legend: {
            labels: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 12 },
              usePointStyle: true,
              boxWidth: 8
            }
          },
          datalabels: {
            display: true,
            color: ctx => (ctx.datasetIndex === 0 ? "#fbbf24" : "#34d399"),
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            borderColor: ctx => (ctx.datasetIndex === 0 ? "#f59e0b" : "#10b981"),
            borderWidth: 1.5,
            borderRadius: 6,
            padding: { top: 3, bottom: 3, left: 6, right: 6 },
            font: { family: "'Plus Jakarta Sans', sans-serif", weight: "800", size: 11 },
            align: "top",
            anchor: "end",
            offset: 5,
            formatter: v => (v > 0 ? formatCompactCurrency(v) : "")
          },
          tooltip: {
            callbacks: {
              afterBody: items => {
                const idx = items[0].dataIndex;
                const m = yoyByMonth[idx];
                if (m && m.growth && m.growth.revenue_pct !== null) {
                  const s = m.growth.revenue_pct > 0 ? "+" : "";
                  return `YoY Growth: ${s}${m.growth.revenue_pct}%`;
                }
                return "";
              }
            }
          }
        },
        scales: {
          y: {
            grid: { color: "rgba(255, 255, 255, 0.08)" },
            ticks: {
              color: "#34d399",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 },
              callback: v => "$" + v / 1000 + "k"
            }
          },
          x: {
            grid: { display: false },
            ticks: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 }
            }
          }
        }
      }
    });
  } else {
    const labels = trend.map(t => t.label);
    const revenues = trend.map(t => t.gross_revenue_actual);

    charts.executiveRevenue = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Gross Revenue ($)",
            data: revenues,
            backgroundColor: "#10b981",
            borderColor: "#34d399",
            borderWidth: 1.5,
            borderRadius: 6
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 35, bottom: 5, left: 5, right: 10 } },
        plugins: {
          legend: {
            labels: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 12 },
              usePointStyle: true,
              boxWidth: 8
            }
          },
          datalabels: {
            display: true,
            color: "#34d399",
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            borderColor: "#10b981",
            borderWidth: 1.5,
            borderRadius: 6,
            padding: { top: 3, bottom: 3, left: 6, right: 6 },
            font: { family: "'Plus Jakarta Sans', sans-serif", weight: "800", size: 11 },
            align: "top",
            anchor: "end",
            offset: 5,
            formatter: v => (v > 0 ? formatCompactCurrency(v) : "")
          },
          tooltip: {
            callbacks: {
              afterLabel: ctx => {
                const item = trend[ctx.dataIndex];
                if (item && item.yoy_growth_revenue_pct !== null) {
                  const s = item.yoy_growth_revenue_pct > 0 ? "+" : "";
                  return `YoY Growth vs ${item.py_label}: ${s}${item.yoy_growth_revenue_pct}%`;
                }
                return "";
              }
            }
          }
        },
        scales: {
          y: {
            grid: { color: "rgba(255, 255, 255, 0.08)" },
            ticks: {
              color: "#34d399",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 },
              callback: v => "$" + v / 1000 + "k"
            }
          },
          x: {
            grid: { display: false },
            ticks: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 },
              maxRotation: 45,
              minRotation: 20
            }
          }
        }
      }
    });
  }
}

// 2. Monthly Activations Historical Trend Chart (Req 1 & 3: New + Migrations = Total with High Visibility)
function renderMonthlyActivationsChart(trend, yoyByMonth, mode) {
  const ctx = document.getElementById("chart-monthly-activations-trend");
  if (!ctx) return;
  if (charts.monthlyActivations) charts.monthlyActivations.destroy();

  if (mode === "yoy") {
    const labels = yoyByMonth.map(m => m.month_name);
    const data2025 = yoyByMonth.map(m => (m.p2025 ? m.p2025.activations : null));
    const data2026 = yoyByMonth.map(m => (m.p2026 ? m.p2026.activations : null));

    charts.monthlyActivations = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "2025 Total Activations (Prior Year)",
            data: data2025,
            backgroundColor: "rgba(245, 158, 11, 0.35)",
            borderColor: "#f59e0b",
            borderWidth: 2,
            borderRadius: 6
          },
          {
            label: "2026 Total Activations (Current Year)",
            data: data2026,
            backgroundColor: "#6366f1",
            borderColor: "#818cf8",
            borderWidth: 2,
            borderRadius: 6
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 35, bottom: 5, left: 5, right: 10 } },
        plugins: {
          legend: {
            labels: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 12 },
              usePointStyle: true,
              boxWidth: 8
            }
          },
          datalabels: {
            display: true,
            color: ctx => (ctx.datasetIndex === 0 ? "#fbbf24" : "#a5b4fc"),
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            borderColor: ctx => (ctx.datasetIndex === 0 ? "#f59e0b" : "#6366f1"),
            borderWidth: 1.5,
            borderRadius: 6,
            padding: { top: 3, bottom: 3, left: 6, right: 6 },
            font: { family: "'Plus Jakarta Sans', sans-serif", weight: "800", size: 11 },
            align: "top",
            anchor: "end",
            offset: 5,
            formatter: v => (v > 0 ? v : "")
          },
          tooltip: {
            callbacks: {
              afterBody: items => {
                const idx = items[0].dataIndex;
                const m = yoyByMonth[idx];
                if (m && m.growth && m.growth.activations_pct !== null) {
                  const s = m.growth.activations_pct > 0 ? "+" : "";
                  return `YoY Growth: ${s}${m.growth.activations_pct}%`;
                }
                return "";
              }
            }
          }
        },
        scales: {
          y: {
            grid: { color: "rgba(255, 255, 255, 0.08)" },
            ticks: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 }
            }
          },
          x: {
            grid: { display: false },
            ticks: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 }
            }
          }
        }
      }
    });
  } else {
    const labels = trend.map(t => t.label);
    const totalActs = trend.map(t => t.activations_total);
    const newActs = trend.map(t => t.activations_new);
    const migrations = trend.map(t => t.activations_migrations);

    charts.monthlyActivations = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "New Activations",
            data: newActs,
            backgroundColor: "#6366f1",
            borderColor: "#818cf8",
            borderWidth: 1,
            stack: "actStack",
            borderRadius: 4,
            order: 2
          },
          {
            label: "Migrations",
            data: migrations,
            backgroundColor: "#0ea5e9",
            borderColor: "#38bdf8",
            borderWidth: 1,
            stack: "actStack",
            borderRadius: 4,
            order: 2
          },
          {
            label: "Total Activations (Act + Mig)",
            data: totalActs,
            type: "line",
            borderColor: "#f59e0b",
            borderWidth: 3.5,
            backgroundColor: "transparent",
            pointBackgroundColor: "#ffffff",
            pointBorderColor: "#f59e0b",
            pointBorderWidth: 2,
            pointRadius: 5,
            pointHoverRadius: 7,
            tension: 0.3,
            order: 1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 35, bottom: 5, left: 5, right: 10 } },
        plugins: {
          legend: {
            labels: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 12 },
              usePointStyle: true,
              boxWidth: 8
            }
          },
          datalabels: {
            display: ctx => ctx.datasetIndex === 2,
            color: "#fbbf24",
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            borderColor: "#f59e0b",
            borderWidth: 1.5,
            borderRadius: 6,
            padding: { top: 3, bottom: 3, left: 7, right: 7 },
            font: { family: "'Plus Jakarta Sans', sans-serif", weight: "800", size: 11 },
            align: "top",
            anchor: "end",
            offset: 7,
            formatter: v => (v > 0 ? v : "")
          },
          tooltip: {
            callbacks: {
              afterLabel: ctx => {
                const item = trend[ctx.dataIndex];
                if (item && item.yoy_growth_activations_pct !== null && ctx.datasetIndex === 2) {
                  const s = item.yoy_growth_activations_pct > 0 ? "+" : "";
                  return `YoY Growth vs ${item.py_label}: ${s}${item.yoy_growth_activations_pct}%`;
                }
                return "";
              }
            }
          }
        },
        scales: {
          y: {
            grid: { color: "rgba(255, 255, 255, 0.08)" },
            ticks: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 }
            }
          },
          x: {
            grid: { display: false },
            ticks: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 },
              maxRotation: 45,
              minRotation: 20
            }
          }
        }
      }
    });
  }
}

// 3. Monthly CPO Historical Trend Chart (Units & Revenue with High Visibility)
function renderMonthlyCPOChart(trend, yoyByMonth, mode) {
  const ctx = document.getElementById("chart-monthly-cpo-trend");
  if (!ctx) return;
  if (charts.monthlyCPO) charts.monthlyCPO.destroy();

  if (mode === "yoy") {
    const labels = yoyByMonth.map(m => m.month_name);
    const data2025 = yoyByMonth.map(m => (m.p2025 ? m.p2025.cpo_units : null));
    const data2026 = yoyByMonth.map(m => (m.p2026 ? m.p2026.cpo_units : null));

    charts.monthlyCPO = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "2025 CPO Units (Prior Year)",
            data: data2025,
            backgroundColor: "rgba(245, 158, 11, 0.35)",
            borderColor: "#f59e0b",
            borderWidth: 2,
            borderRadius: 6
          },
          {
            label: "2026 CPO Units (Current Year)",
            data: data2026,
            backgroundColor: "#10b981",
            borderColor: "#34d399",
            borderWidth: 2,
            borderRadius: 6
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 35, bottom: 5, left: 5, right: 10 } },
        plugins: {
          legend: {
            labels: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 12 },
              usePointStyle: true,
              boxWidth: 8
            }
          },
          datalabels: {
            display: true,
            color: ctx => (ctx.datasetIndex === 0 ? "#fbbf24" : "#34d399"),
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            borderColor: ctx => (ctx.datasetIndex === 0 ? "#f59e0b" : "#10b981"),
            borderWidth: 1.5,
            borderRadius: 6,
            padding: { top: 3, bottom: 3, left: 6, right: 6 },
            font: { family: "'Plus Jakarta Sans', sans-serif", weight: "800", size: 11 },
            align: "top",
            anchor: "end",
            offset: 5,
            formatter: v => (v > 0 ? v : "")
          },
          tooltip: {
            callbacks: {
              afterBody: items => {
                const idx = items[0].dataIndex;
                const m = yoyByMonth[idx];
                if (m && m.growth && m.growth.cpo_pct !== null) {
                  const s = m.growth.cpo_pct > 0 ? "+" : "";
                  return `YoY Growth: ${s}${m.growth.cpo_pct}%`;
                }
                return "";
              }
            }
          }
        },
        scales: {
          y: {
            grid: { color: "rgba(255, 255, 255, 0.08)" },
            ticks: {
              color: "#34d399",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 }
            }
          },
          x: {
            grid: { display: false },
            ticks: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 }
            }
          }
        }
      }
    });
  } else {
    const labels = trend.map(t => t.label);
    const units = trend.map(t => t.cpo_units_actual);
    const revenues = trend.map(t => t.cpo_revenue_actual);

    charts.monthlyCPO = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "CPO Units Sold",
            data: units,
            backgroundColor: "#10b981",
            borderColor: "#34d399",
            borderWidth: 1.5,
            borderRadius: 6,
            yAxisID: "y",
            order: 2
          },
          {
            label: "CPO Revenue ($)",
            data: revenues,
            type: "line",
            borderColor: "#06b6d4",
            borderWidth: 3,
            backgroundColor: "transparent",
            pointBackgroundColor: "#ffffff",
            pointBorderColor: "#06b6d4",
            pointBorderWidth: 2,
            pointRadius: 4,
            tension: 0.3,
            yAxisID: "y1",
            order: 1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 35, bottom: 5, left: 5, right: 10 } },
        plugins: {
          legend: {
            labels: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 12 },
              usePointStyle: true,
              boxWidth: 8
            }
          },
          datalabels: {
            display: true,
            color: ctx => (ctx.datasetIndex === 0 ? "#34d399" : "#22d3ee"),
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            borderColor: ctx => (ctx.datasetIndex === 0 ? "#10b981" : "#06b6d4"),
            borderWidth: 1.5,
            borderRadius: 6,
            padding: { top: 3, bottom: 3, left: 6, right: 6 },
            font: { family: "'Plus Jakarta Sans', sans-serif", weight: "800", size: 11 },
            align: "top",
            anchor: "end",
            offset: 5,
            formatter: (v, ctx) =>
              ctx.datasetIndex === 0 ? (v > 0 ? v : "") : v > 0 ? formatCompactCurrency(v) : ""
          },
          tooltip: {
            callbacks: {
              afterLabel: ctx => {
                const item = trend[ctx.dataIndex];
                if (item && item.yoy_growth_cpo_pct !== null && ctx.datasetIndex === 0) {
                  const s = item.yoy_growth_cpo_pct > 0 ? "+" : "";
                  return `YoY Growth vs ${item.py_label}: ${s}${item.yoy_growth_cpo_pct}%`;
                }
                return "";
              }
            }
          }
        },
        scales: {
          y: {
            type: "linear",
            position: "left",
            grid: { color: "rgba(255, 255, 255, 0.08)" },
            ticks: {
              color: "#34d399",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 }
            }
          },
          y1: {
            type: "linear",
            position: "right",
            grid: { display: false },
            ticks: {
              color: "#22d3ee",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 },
              callback: v => "$" + v / 1000 + "k"
            }
          },
          x: {
            grid: { display: false },
            ticks: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 },
              maxRotation: 45,
              minRotation: 20
            }
          }
        }
      }
    });
  }
}

// 4. Monthly Repairs Historical Trend Chart (OOW vs Insurance & Revenue with High Visibility)
function renderMonthlyRepairsChart(trend, yoyByMonth, mode) {
  const ctx = document.getElementById("chart-monthly-repairs-trend");
  if (!ctx) return;
  if (charts.monthlyRepairs) charts.monthlyRepairs.destroy();

  if (mode === "yoy") {
    const labels = yoyByMonth.map(m => m.month_name);
    const data2025 = yoyByMonth.map(m => (m.p2025 ? m.p2025.repairs_volume : null));
    const data2026 = yoyByMonth.map(m => (m.p2026 ? m.p2026.repairs_volume : null));

    charts.monthlyRepairs = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "2025 Total Repairs (Prior Year)",
            data: data2025,
            backgroundColor: "rgba(245, 158, 11, 0.35)",
            borderColor: "#f59e0b",
            borderWidth: 2,
            borderRadius: 6
          },
          {
            label: "2026 Total Repairs (Current Year)",
            data: data2026,
            backgroundColor: "#14b8a6",
            borderColor: "#2dd4bf",
            borderWidth: 2,
            borderRadius: 6
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 35, bottom: 5, left: 5, right: 10 } },
        plugins: {
          legend: {
            labels: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 12 },
              usePointStyle: true,
              boxWidth: 8
            }
          },
          datalabels: {
            display: true,
            color: ctx => (ctx.datasetIndex === 0 ? "#fbbf24" : "#2dd4bf"),
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            borderColor: ctx => (ctx.datasetIndex === 0 ? "#f59e0b" : "#14b8a6"),
            borderWidth: 1.5,
            borderRadius: 6,
            padding: { top: 3, bottom: 3, left: 6, right: 6 },
            font: { family: "'Plus Jakarta Sans', sans-serif", weight: "800", size: 11 },
            align: "top",
            anchor: "end",
            offset: 5,
            formatter: v => (v > 0 ? v : "")
          },
          tooltip: {
            callbacks: {
              afterBody: items => {
                const idx = items[0].dataIndex;
                const m = yoyByMonth[idx];
                if (m && m.growth && m.growth.repairs_pct !== null) {
                  const s = m.growth.repairs_pct > 0 ? "+" : "";
                  return `YoY Growth: ${s}${m.growth.repairs_pct}%`;
                }
                return "";
              }
            }
          }
        },
        scales: {
          y: {
            grid: { color: "rgba(255, 255, 255, 0.08)" },
            ticks: {
              color: "#2dd4bf",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 }
            }
          },
          x: {
            grid: { display: false },
            ticks: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 }
            }
          }
        }
      }
    });
  } else {
    const labels = trend.map(t => t.label);
    const oow = trend.map(t => t.repairs_oow_volume);
    const ins = trend.map(t => t.repairs_insurance_volume);
    const revenues = trend.map(t => t.repairs_total_revenue);

    charts.monthlyRepairs = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Out of Warranty (OOW)",
            data: oow,
            backgroundColor: "#f59e0b",
            borderColor: "#fbbf24",
            borderWidth: 1,
            stack: "repStack",
            borderRadius: 4,
            yAxisID: "y",
            order: 2
          },
          {
            label: "Insurance Repairs",
            data: ins,
            backgroundColor: "#14b8a6",
            borderColor: "#2dd4bf",
            borderWidth: 1,
            stack: "repStack",
            borderRadius: 4,
            yAxisID: "y",
            order: 2
          },
          {
            label: "Total Repair Revenue ($)",
            data: revenues,
            type: "line",
            borderColor: "#3b82f6",
            borderWidth: 3,
            backgroundColor: "transparent",
            pointBackgroundColor: "#ffffff",
            pointBorderColor: "#3b82f6",
            pointBorderWidth: 2,
            pointRadius: 4,
            tension: 0.3,
            yAxisID: "y1",
            order: 1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 35, bottom: 5, left: 5, right: 10 } },
        plugins: {
          legend: {
            labels: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 12 },
              usePointStyle: true,
              boxWidth: 8
            }
          },
          datalabels: {
            display: ctx => ctx.datasetIndex === 2,
            color: "#60a5fa",
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            borderColor: "#3b82f6",
            borderWidth: 1.5,
            borderRadius: 6,
            padding: { top: 3, bottom: 3, left: 6, right: 6 },
            font: { family: "'Plus Jakarta Sans', sans-serif", weight: "800", size: 11 },
            align: "top",
            anchor: "end",
            offset: 5,
            formatter: (v, ctx) => (ctx.datasetIndex === 2 && v > 0 ? formatCompactCurrency(v) : "")
          },
          tooltip: {
            callbacks: {
              afterLabel: ctx => {
                const item = trend[ctx.dataIndex];
                if (
                  item &&
                  item.yoy_growth_repairs_pct !== null &&
                  (ctx.datasetIndex === 0 || ctx.datasetIndex === 1)
                ) {
                  const s = item.yoy_growth_repairs_pct > 0 ? "+" : "";
                  return `YoY Growth vs ${item.py_label}: ${s}${item.yoy_growth_repairs_pct}%`;
                }
                return "";
              }
            }
          }
        },
        scales: {
          y: {
            type: "linear",
            position: "left",
            grid: { color: "rgba(255, 255, 255, 0.08)" },
            ticks: {
              color: "#fbbf24",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 }
            }
          },
          y1: {
            type: "linear",
            position: "right",
            grid: { display: false },
            ticks: {
              color: "#60a5fa",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 },
              callback: v => "$" + v / 1000 + "k"
            }
          },
          x: {
            grid: { display: false },
            ticks: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 },
              maxRotation: 45,
              minRotation: 20
            }
          }
        }
      }
    });
  }
}

// 5. Monthly Foot Traffic & Conversion Rate Historical Trend Chart (with High Visibility)
function renderMonthlyTrafficChart(trend, yoyByMonth, mode) {
  const ctx = document.getElementById("chart-monthly-traffic-trend");
  if (!ctx) return;
  if (charts.monthlyTraffic) charts.monthlyTraffic.destroy();

  if (mode === "yoy") {
    const labels = yoyByMonth.map(m => m.month_name);
    const data2025 = yoyByMonth.map(m => (m.p2025 ? m.p2025.traffic : null));
    const data2026 = yoyByMonth.map(m => (m.p2026 ? m.p2026.traffic : null));

    charts.monthlyTraffic = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "2025 Door Traffic (Prior Year)",
            data: data2025,
            backgroundColor: "rgba(245, 158, 11, 0.35)",
            borderColor: "#f59e0b",
            borderWidth: 2,
            borderRadius: 6
          },
          {
            label: "2026 Door Traffic (Current Year)",
            data: data2026,
            backgroundColor: "rgba(244, 63, 94, 0.75)",
            borderColor: "#fb7185",
            borderWidth: 2,
            borderRadius: 6
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 35, bottom: 5, left: 5, right: 10 } },
        plugins: {
          legend: {
            labels: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 12 },
              usePointStyle: true,
              boxWidth: 8
            }
          },
          datalabels: {
            display: true,
            color: ctx => (ctx.datasetIndex === 0 ? "#fbbf24" : "#fb7185"),
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            borderColor: ctx => (ctx.datasetIndex === 0 ? "#f59e0b" : "#f43f5e"),
            borderWidth: 1.5,
            borderRadius: 6,
            padding: { top: 3, bottom: 3, left: 6, right: 6 },
            font: { family: "'Plus Jakarta Sans', sans-serif", weight: "800", size: 11 },
            align: "top",
            anchor: "end",
            offset: 5,
            formatter: v => (v > 0 ? (v >= 1000 ? (v / 1000).toFixed(0) + "k" : v) : "")
          },
          tooltip: {
            callbacks: {
              afterBody: items => {
                const idx = items[0].dataIndex;
                const m = yoyByMonth[idx];
                if (m && m.growth && m.growth.traffic_pct !== null) {
                  const s = m.growth.traffic_pct > 0 ? "+" : "";
                  return `YoY Growth: ${s}${m.growth.traffic_pct}%`;
                }
                return "";
              }
            }
          }
        },
        scales: {
          y: {
            grid: { color: "rgba(255, 255, 255, 0.08)" },
            ticks: {
              color: "#fb7185",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 },
              callback: v => (v >= 1000 ? (v / 1000).toFixed(0) + "k" : v)
            }
          },
          x: {
            grid: { display: false },
            ticks: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 }
            }
          }
        }
      }
    });
  } else {
    const labels = trend.map(t => t.label);
    const traffic = trend.map(t => t.foot_traffic_total);
    const convRates = trend.map(t => t.conversion_rate_pct);

    charts.monthlyTraffic = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Door Traffic",
            data: traffic,
            backgroundColor: "rgba(244, 63, 94, 0.65)",
            borderColor: "#f43f5e",
            borderWidth: 1.5,
            borderRadius: 6,
            yAxisID: "y",
            order: 2
          },
          {
            label: "Conversion Rate (%)",
            data: convRates,
            type: "line",
            borderColor: "#10b981",
            backgroundColor: "transparent",
            borderWidth: 3,
            pointBackgroundColor: "#ffffff",
            pointBorderColor: "#10b981",
            pointBorderWidth: 2,
            pointRadius: 4,
            tension: 0.3,
            yAxisID: "y1",
            order: 1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 35, bottom: 5, left: 5, right: 10 } },
        plugins: {
          legend: {
            labels: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 12 },
              usePointStyle: true,
              boxWidth: 8
            }
          },
          datalabels: {
            display: true,
            color: ctx => (ctx.datasetIndex === 0 ? "#fb7185" : "#34d399"),
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            borderColor: ctx => (ctx.datasetIndex === 0 ? "#f43f5e" : "#10b981"),
            borderWidth: 1.5,
            borderRadius: 6,
            padding: { top: 3, bottom: 3, left: 6, right: 6 },
            font: { family: "'Plus Jakarta Sans', sans-serif", weight: "800", size: 11 },
            align: "top",
            anchor: "end",
            offset: 5,
            formatter: (v, ctx) =>
              ctx.datasetIndex === 0 ? (v > 0 ? formatNumber(v) : "") : v > 0 ? v + "%" : ""
          },
          tooltip: {
            callbacks: {
              afterLabel: ctx => {
                const item = trend[ctx.dataIndex];
                if (item && item.yoy_growth_traffic_pct !== null && ctx.datasetIndex === 0) {
                  const s = item.yoy_growth_traffic_pct > 0 ? "+" : "";
                  return `YoY Growth vs ${item.py_label}: ${s}${item.yoy_growth_traffic_pct}%`;
                }
                return "";
              }
            }
          }
        },
        scales: {
          y: {
            type: "linear",
            position: "left",
            grid: { color: "rgba(255, 255, 255, 0.08)" },
            ticks: {
              color: "#fb7185",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 },
              callback: v => (v >= 1000 ? (v / 1000).toFixed(0) + "k" : v)
            }
          },
          y1: {
            type: "linear",
            position: "right",
            grid: { display: false },
            ticks: {
              color: "#34d399",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 },
              callback: v => v + "%"
            }
          },
          x: {
            grid: { display: false },
            ticks: {
              color: "#e2e8f0",
              font: { family: "'Plus Jakarta Sans', sans-serif", weight: "600", size: 11 },
              maxRotation: 45,
              minRotation: 20
            }
          }
        }
      }
    });
  }
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
