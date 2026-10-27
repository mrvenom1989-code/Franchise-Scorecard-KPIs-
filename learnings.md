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

---

## 6. Serverless Payload Limits & Corporate Scorecard Normalization

### Vercel Serverless Function Limits (413 Payload Too Large & Timeouts)
*   **The Issue**: Uploading the October master scorecard (`Copy of Franchise Scorecard - Oct MTD EOD - 10-25-26.xlsx`, 5.2 MB) through the web admin portal triggered `413 FUNCTION_PAYLOAD_TOO_LARGE`.
*   **Root Cause**: Vercel enforces a hard, unconfigurable **4.5 MB request body limit** on all HTTP requests to serverless functions. Furthermore, even if bypassed via storage streaming, parsing 14-sheet master workbooks exceeds Vercel's 10–15s function timeout.
*   **Architectural Resolution**: Adopted the **Hybrid Architecture**: dashboard queries and user management run on Vercel Serverless, while heavy corporate scorecard batch ingestion runs via deterministic CLI tools (`ingest_scorecard.py`) directly targeting Supabase PostgreSQL.

### Corporate Store Notation Normalization (F-Prefix & Float Types)
*   **The Issue**: Corporate's newer master exports changed store identifiers from pure integers (`333`) to 4-character codes with regional digit duplication (e.g., `'F3333'` for Store #333, `'F3326'` for Store #326, `'F8824'` for Store #824, `'F4401'` for Store #401), and in older sheets loaded numbers as floats (`826.0`). Previous parsing scripts discarded these rows via strict `.isdigit()` checks.
*   **Solution**: Implemented `extract_store_num()`:
    1.  Casts floats/ints to integers directly.
    2.  Strips leading franchise/corporate letter prefixes (`F`, `C`).
    3.  Strips decimal fractions (`826.0` $\rightarrow$ `826`).
    4.  Extracts the 3-digit store number when the first two digits repeat the region prefix (`len == 4 and s[0] == s[1]`).

### Dynamic Location Auto-Provisioning & Region Check Constraints
*   **The Issue**: When network expansion adds new stores (e.g. Spruce Grove, Southgate, Polo Park, Shoppers Mall, Metrotown, WEM), unmapped stores were previously dropped during ingestion. Attempting to insert them with raw sheet values (`ON`, `BC`, `W1`, `Ex`) violated PostgreSQL's check constraint: `CHECK (region IN ('EAST', 'WEST'))`.
*   **Solution**: 
    1.  Added automated location provisioning during monthly KPI ingestion.
    2.  Added `normalize_region()` to map Canadian provinces (`BC`, `AB`, `SK`, `MB` $\rightarrow$ `WEST`; `ON`, `QC`, `NB`, `NS`, `NL` $\rightarrow$ `EAST`) and corporate tier prefixes (`W*` $\rightarrow$ `WEST`; `E*` $\rightarrow$ `EAST`), ensuring 100% compliance with database integrity constraints.

### Uncoupled Category Headers vs. Direct Metric Row Matching
*   **The Issue**: In newer sheets (e.g., `Sept 26`, `Oct 26 MTD`), corporate merged or omitted the top category row (row 4 had blank cells or merged `'Traffic'` across columns 3–27). Strict composite queries searching for `['all revenue', 'mtd', 'gross revenue']` and `['all activations', 'mtd', 'total activation transactions']` failed to find a match, causing Gross Revenue, Sales Volume, and Activations to evaluate to `0` in the database.
*   **Solution**: Upgraded `get_val()` to inspect row 8's metric labels directly with multi-pattern fallback matching and negative keyword filters (e.g., matching `['total gross revenue mtd', 'gross revenue mtd']` while excluding `['projected', 'mom total', 'yoy total']`), restoring complete data extraction across all historical and current scorecard formats.

---

## 7. Forensic Data Quality & The Name-First Resolution Architecture

### Corporate Column Misalignment (The Sept 26 1-Row Copy-Paste Shift)
*   **The Bug**: In the `Sept 26` tab of corporate master workbooks, corporate analysts accidentally shifted Column A (`MK Store #`) down by 1 row across 17 consecutive stores.
    *   Row 30: Location was `Landsdowne`, but Column A contained `F3326` (Store #326, Lethbridge).
    *   Row 31: Location was `Lethbridge`, but Column A contained `F1136` (Store #136, Limeridge Mall).
    *   Row 32: Location was `Limeridge Mall`, but Column A contained `F1153` (Store #153, Mapleview Centre).
*   **Impact on Prior Ingestion Logic**: Because previous ingestion scripts treated Column A (`MK Store #`) as the sole authoritative foreign key:
    *   Row 30 (`Landsdowne`, Revenue: **$75,035**, Repairs: **98**) was ingested as **Mobile Klinik Lethbridge (#326)**.
    *   Row 31 (`Lethbridge`, Revenue: **$171,113**, Repairs: **391**) was ingested as **Mobile Klinik Limeridge Mall (#136)**.
    *   On the dashboard, selecting Lethbridge for September 2026 displayed Landsdowne's $75,035 revenue and 98 repairs instead of Lethbridge's true $171,113 revenue and 391 repairs.
*   **The Long-Term Architectural Solution (Name-First Location Resolution)**:
    1.  **Location Name as Primary Identity**: In retail franchise operations, location names (e.g., "Lethbridge", "Landsdowne", "Market Mall") are human-verified and immune to numeric column-shift errors.
    2.  **Normalized Name Indexing**: `normalize_store_name()` strips punctuation, parenthetical qualifiers (e.g. `(Oct 17)`), and corporate prefixes (`Mobile Klinik`, `Frchs-`), mapping them to canonical DB locations.
    3.  **Automatic Discrepancy Reconciliation**: If a row's Location Name matches a known store but the Excel store number disagrees, the ingestion engine logs an audit warning (`[RECONCILED] Sheet '{sheet}' row '{name}': Excel has code '{code}' (#{raw_num}), but canonical store is #{canon_num}`) and routes the data to the correct canonical store.
    4.  **Fallback & Auto-Provisioning**: Unmatched names fall back to numeric store matching, and brand-new stores are automatically provisioned with province-to-region constraint mapping.

---

## 8. Authentication & Session Engineering

### Browser 4KB Cookie Overflow from Store Expansion
*   **The Issue**: After ingesting the October scorecard, Super Admin login suddenly stopped working (submitting credentials redirected back to `/login` without logging in or displaying errors).
*   **Root Cause**:
    1.  The October scorecard expanded the store network from 40 to **85 locations**.
    2.  `routes/auth.py` was storing full dictionaries for all 85 stores in `session['user']['locations']`.
    3.  Because Flask uses client-side signed cookies by default, the serialized session cookie expanded to **5,511 bytes**.
    4.  Under RFC 6265, web browsers (Chrome, Edge, Firefox, Safari) silently reject any HTTP cookie exceeding **4,096 bytes**. The browser dropped the cookie upon redirect, causing Flask's `@login_required` to view the session as empty and loop back to the login screen.
*   **Solution**:
    1.  Slimmed down `session['user']` to store only essential identity fields (`id`, `email`, `role`, `organization_name`, and compact `location_ids`), reducing the cookie size from 5,511 bytes to **258 bytes**.
    2.  Shifted location list loading to dynamic, on-demand database queries inside `routes/dashboard.py` and `routes/admin.py`, guaranteeing that the application scales safely to hundreds of stores without ever approaching browser cookie boundaries.

### `next` URL Parameter Sanitization & Open Redirect Shield
*   **The Issue**: Clicking "Sign In to Scorecard" from the public landing page redirected users to `/login?next=https://franchise-scorecard-kp-is-drab.vercel.app/`. Upon submitting credentials, users were redirected back to the login page or encountered redirect loop errors.
*   **Root Cause**: When `next` is passed as an absolute URL (`https://...`), naive URL validation that checks `is_safe_url()` or assumes relative paths can either reject valid internal redirections or create Open Redirect attack vectors if untrusted external URLs are passed. Additionally, if `next` was set to `/login` or contained `/login`, the application entered an infinite login loop.
*   **Solution**:
    1.  Used `urllib.parse.urlparse` to inspect `next_url`. If netloc matches the current request host or is empty, extract the path, query, and fragment as a clean relative URL.
    2.  Explicitly blocked any redirect target that begins with or equals `/login` or `/logout`, falling back unconditionally to `url_for('dashboard.index')`.
    3.  Rejected any external or mismatching netlocs to protect against phishing and open-redirect exploits.

---

## 9. Reporting Architecture & Metric Relationship Rules

### The Total Activations Invariant (New + Migrations)
*   **The Issue**: When comparing raw Excel numbers against the database, 110 store records showed total activation numbers that differed from the sum of new activations and migrations.
*   **Root Cause**: In corporate's Excel workbooks, column naming and formula implementations varied across monthly accounting periods. In some sheets, `Total Activation Trans MTD (Act + Mig)` actually summed New + Migrations; in other sheets, corporate analysts entered only New Activations into that column and logged Migrations in a separate column without summing them.
*   **Architectural Resolution**:
    1.  **Deterministic Invariant**: Enforced `activations_total = (activations_new or 0) + (activations_migrations or 0)` across all layers (ingestion scripts, database sync, REST API serializers).
    2.  **Database Synchronization**: Executed an automated database sweep updating all 110 legacy records in PostgreSQL to ensure historical consistency.
    3.  **UI Architecture Banner**: Placed an explicit reporting architecture rule banner on the Activations tab (`Total Activations = Total New Activations MTD + Migrations`) to give store managers and accountants complete transparency into the metric definition.

### Chronological Period Sequencing & Snapshot Pruning
*   **The Issue**: Historical period tables contained both `Jan 26 MTD` (an interim snapshot covering Jan 1–18, 2026) and `Jan 26` (the final, complete month covering Jan 1–31, 2026). Including both periods in 14-month historical trend charts caused duplicate January data points and distorted chronological visual flow.
*   **Solution**: In `/api/monthly-trend`, filtered out `Jan 26 MTD` so that historical trend lines strictly reflect finalized calendar months plus the active MTD period (`Oct 26 MTD`).

### Month-over-Month (MoM) and Year-over-Year (YoY) Dynamic Comparison Engine
*   **The Challenge**: Users require instantaneous growth velocity indicators comparing current MTD performance against prior operational baselines.
*   **Implementation**:
    *   **MoM Calculation**: Dynamically compares the active period (e.g. `Oct 26 MTD`) with the immediately preceding accounting period (`Sept 26`), calculating absolute deltas and percentage growth for Revenue, Activations, CPO, Repairs, and Traffic.
    *   **YoY Calculation**: Pairs the active month with the matching month exactly 1 year prior (`Oct 26 MTD` vs `Oct 2025`; `Sept 26` vs `Sept 2025`), providing seasonal benchmarking across a 12-month horizon.
    *   **UI Delta Tags**: Formatted as colored micro-badges (`▲ +X%` green for positive, `▼ -X%` red for negative, and `neutral` for flat) with full tooltip breakdowns showing baseline vs current values.

---

## 10. Multi-Tenant Benchmarking & UI Interactivity Architecture

### Tri-Level Dynamic Benchmarking (Regional, Global Network, Portfolio)
*   **The Challenge**: A single regional baseline is insufficient for multi-store franchise groups who need to measure their performance against:
    1.  Their specific geographic territory (Regional Benchmark).
    2.  The entire national network of 78+ franchise locations (Global Network Benchmark).
    3.  Their own internal store portfolio (User Portfolio Benchmark).
*   **Solution**:
    *   Unified the calculation inside `routes/api.py`, generating `regional_benchmark`, `global_benchmark`, and `portfolio_benchmark` in a single response payload.
    *   Added an interactive button group in the Benchmark card (`Regional`, `Global Network`, `My Stores`, `Compare All`).
    *   In `Compare All` mode, the radar chart plots the user's selected store(s), the Regional Average, and the Global Network Baseline simultaneously on a normalized 100% index scale.

### Top Performer Leaderboard Decoration & Visual Hierarchy
*   **The UX Pattern**: Franchise operators need immediate visual clarity on store performance rankings without manually sorting or scanning tabular numbers.
*   **Implementation**:
    *   Added a dedicated `Rank` column to the Store Performance Leaderboard.
    *   Applied distinct visual badge treatments for the podium positions:
        *   **Rank 1**: `🥇 #1` gold badge, ambient gold row gradient, and gold highlight border.
        *   **Rank 2**: `🥈 #2` silver badge, silver row gradient, and silver highlight border.
        *   **Rank 3**: `🥉 #3` bronze badge, bronze row gradient, and bronze highlight border.
        *   **Rank 4+**: `#4`, `#5`, etc. with clean muted pill badges.

### Clickable KPI Widgets as Primary Navigation Affordances
*   **The UX Pattern**: Dashboard summary cards at the top of an executive view should not be dead ends; they should serve as natural shortcuts to deep-dive analytics.
*   **Implementation**:
    *   Configured top KPI cards with `onclick="switchTab(...)"` to jump directly to the relevant operational tab (Gross Revenue/Volume $\rightarrow$ Benchmarks, Activations $\rightarrow$ Activations, CPO $\rightarrow$ CPO, Repairs $\rightarrow$ Repairs, Conversion $\rightarrow$ Traffic).
    *   Added `.clickable-card` CSS with cursor pointer, hover lift (`transform: translateY(-4px)`), ambient border glow matching the card's accent color, and an animated hover badge indicator (`View Details →`).

### Domain Nomenclature Alignment & Tab Simplification
*   **The Rationale**: Corporate engineering titles frequently use cumbersome administrative phrasing (`Carrier Activations`, `Hardware & CPO Sales`, `Technical & Repairs`).
*   **The Fix**: Streamlined UI terminology to match store operator daily vernacular:
    *   `Carrier Activations` $\rightarrow$ `Activations`
    *   `Hardware & CPO` $\rightarrow$ `CPO`
    *   `Technical & Repairs` $\rightarrow$ `Repairs`
    This reduces mental overhead, saves horizontal tab bar real estate on mobile devices and POS tablets, and keeps visual hierarchy clean and action-oriented.




