# Project Learnings: Mobile Klinik Franchise Scorecard & Operations Dashboard

This document records architectural insights, data anomalies, API quirks, and technical solutions discovered during the design, ingestion, and deployment of the Mobile Klinik Franchise Scorecard application.

---

## 1. Excel Data Normalization & Ingestion Quirks

### Sensor Outages & Weekly Fallback Logic
*   **The Issue**: On the `Jan 26 MTD` sheet of `Franchise Scorecard KPIs - WoW ending 01-18-26.xlsx`, corporate completely omitted the foot traffic column (leaving it as 0). Consequently, conversion rate formulas evaluated to 0%.
*   **Root Cause**: In the `WOW Traffic` sheet, corporate explicitly noted `"System Data Error This Week"` for Week 2 of January (`2026-01-12` was marked `NA`), indicating a network failure in their door counters. Because the month was incomplete, corporate omitted foot traffic from the MTD summary sheet.
*   **Solution**: In `ingest_scorecard.py`, we implemented an automated weekly fallback: if `foot_traffic_total == 0` for any period, the parser checks `WOW Traffic`, filters by the period's date range, and aggregates all recorded weekly door visits (recovering **3,111 door visits** for Week 1).
*   **UI Insight**: When conversion rates exceed 100% due to partial foot traffic logging (18 days of closed sales vs. 7 days of captured traffic), the UI must display a clear explanatory badge (`⚠️ Corporate sensor outage in Week 2. Showing Week 1 traffic`) rather than letting users assume the calculation is flawed.

### Corporate Workbook Date Typos
*   **The Issue**: In the weekly time series sheets (`WOW Traffic`, `WOW Activation`, `WOW CPO Volume`, `WOW WI Repair Volume`), column headers for December 22 and December 29 were erroneously typed as `2026-12-22` and `2026-12-29` instead of `2025-12-22` and `2025-12-29`.
*   **Impact**: When inserted into PostgreSQL, December 2025 sorted *after* January 2026, breaking chronological weekly trend lines.
*   **Solution**: Added automatic date normalization in `parse_wow_sheet()`:
    ```python
    if d.year == 2026 and d.month == 12:
        d = date(2025, 12, d.day)
    ```
    This guarantees that historical December data is strictly ordered before January 2026.

### Dynamic Sheet Discovery for Overlapping Monthly Files
*   **The Issue**: Initial scripts hardcoded sheet names `['Jan 26 MTD', 'Dec 2025 ', 'Nov 25', ...]`. Subsequent monthly files (e.g. February, March) with new sheet names would have been ignored.
*   **Solution**: Replaced hardcoded sheet lists with dynamic inspection: any sheet not prefixed with `WOW` or `Cover` is dynamically parsed and validated for store numbers and scorecard metrics, ensuring future overlapping scorecards are ingested seamlessly without code changes.

### Cell Cleaning & Formula Error Suppression
*   Excel exports frequently contain `#DIV/0!`, `#VALUE!`, `#N/A`, currency symbols (`$`), commas, and trailing percentages.
*   `clean_num(val, default=0.0)` sanitizes raw cell data into strict Python `float` or `int` types, replacing Excel formula errors with 0.0 to prevent database type violations.

---

## 2. PostgreSQL & PostgREST / Supabase Patterns

### UUID Type-Casting & Empty Filter Pitfalls
*   **The Issue**: When users clicked "Clear" in the multi-select location dropdown, the frontend previously passed `location_id=none` to the API. PostgREST attempted to execute `.in_('location_id', ['none'])`, resulting in PostgreSQL error `22P02: invalid input syntax for type uuid: "none"` (HTTP 500).
*   **Solution**:
    1.  Implemented `is_valid_uuid(val)` in `routes/api.py` to ensure only syntactically valid UUID strings reach the database layer.
    2.  Explicitly handled `requested_location_id in ['none', 'empty']` at the top of route handlers, returning clean empty structures (`count: 0`, `store_rows: []`, `summary: {}`) without querying Postgres.

### Composite Unique Constraints on Batch Upserts
*   Both `monthly_kpis` and `weekly_kpis` use composite keys for idempotency:
    *   `monthly_kpis`: `(location_id, period_id)`
    *   `weekly_kpis`: `(location_id, week_end_date, metric_type)`
*   When executing Supabase `.upsert()`, always pass `on_conflict="location_id,period_id"` or `on_conflict="location_id,week_end_date,metric_type"` to prevent constraint violation errors on re-ingestion.

### Supabase Auth Admin API for Password Updates
*   In administrative workflows, resetting team member credentials should bypass email confirmation links:
    ```python
    supabase.auth.admin.update_user_by_id(user_id, {"password": new_password})
    ```
    This updates the user's password directly in `auth.users` while preserving their identity and session integrity.

---

## 3. Multi-Tenant Role-Based Access Control (RBAC)

### The Super Admin Role Check Trap
*   **The Bug**: A decorator written as:
    ```python
    if user_role not in allowed_roles and 'super_admin' not in allowed_roles:
        return redirect(url_for('dashboard.index'))
    ```
    If `user_role == 'super_admin'` and an endpoint only specifies `@roles_required('admin')`, both conditions evaluate to `True`, inadvertently blocking the Super Administrator!
*   **The Fix**: Always explicitly exempt the highest administrative tier:
    ```python
    if user_role != 'super_admin' and user_role not in allowed_roles:
        return redirect(url_for('dashboard.index'))
    ```

### Scoped Hierarchical User Administration
*   Franchise Owners (`admin` role) need to manage store managers and staff within their licensed territory without possessing platform-wide administrative powers.
*   Enforced rules in `routes/admin.py`:
    1.  Franchise Owners can only assign roles: `store_manager`, `accountant`, or `staff`.
    2.  Franchise Owners cannot edit Super Admins or other Franchise Owners.
    3.  Store assignments are validated against the current owner's permitted stores: attempting to assign an unauthorized store number is rejected.
    4.  Tracking `created_by` in `user_profiles` allows owners to view team members they created even before store assignments are finalized.

---

## 4. Chart.js & Frontend Visualization Engineering

### Hidden Tab Canvas Initialization Bug
*   **The Issue**: Chart.js canvases located inside tab panels with `display: none` initialize with `0px` height and width. When the user switches to that tab, charts appear squished or fail to render.
*   **Solution**: In `switchTab()`, after activating the tab panel, a delayed tick triggers:
    ```javascript
    setTimeout(() => {
      Object.values(charts).forEach(c => {
        if (c && c.resize) {
          c.resize();
          if (c.update) c.update("none");
        }
      });
    }, 40);
    ```
    This guarantees full-resolution rendering upon tab visibility.

### Multi-Store Benchmark Radar Distortion
*   **The Issue**: In `renderBenchmarkRadarChart`, comparing the user's aggregate revenue ($1,150,000 across 28 stores) directly to a single store's regional average ($41,000) generated a 3,600% spike, breaking the radar polygon scale.
*   **Solution**: Normalize aggregate figures by the number of selected stores (`s.gross_revenue_actual / storeCnt`) before computing the regional benchmark ratio. This ensures the radar comparison is statistically sound whether 1 store or 28 stores are selected.

### ChartDataLabels Plugin Integration
*   To avoid visual clutter while displaying point labels:
    *   Suppress 0 or empty values: `formatter: v => v > 0 ? formatCompactCurrency(v) : ""`
    *   Add layout padding (`layout: { padding: { top: 25 } }`) to prevent labels on tall bars from being clipped by the canvas bounding box.

---

## 5. CSS Stacking Context & Stacking Order

### The Backdrop-Filter Stacking Context Collision
*   **The Issue**: The store multi-select dropdown menu was rendered behind the Gross Revenue KPI card.
*   **Root Cause**:
    1.  `.kpi-card` had `position: relative`, placing it in a positioned stacking context.
    2.  `backdrop-filter: blur(...)` on glass cards creates an isolated stacking context in Chromium and WebKit.
    3.  The toolbar (`.control-bar`) had default `position: static`, so all child elements overflowing out of the toolbar were layered underneath positioned elements lower in the DOM.
*   **Solution**:
    1.  Set `.control-bar { position: relative; z-index: 900; }`.
    2.  Set `.store-multiselect-wrapper { position: relative; z-index: 920; }`.
    3.  Set `#store-dropdown-menu { position: absolute; z-index: 9999 !important; background: rgba(15, 23, 42, 0.98); }`.
    This guarantees that the dropdown menu floats on top of all cards, navigation bars, and charts across every browser.
