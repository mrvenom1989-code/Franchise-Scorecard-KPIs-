# Franchise Scorecard & KPIs — Session Handoff

**Project**: Mobile Klinik Franchise Scorecard & Multi-Tenant Operations Dashboard  
**Repository**: [https://github.com/mrvenom1989-code/Franchise-Scorecard-KPIs-.git](https://github.com/mrvenom1989-code/Franchise-Scorecard-KPIs-.git)  
**Database**: Dedicated Supabase PostgreSQL Instance: `https://amjzomlovbuwjneqnumv.supabase.co`  
**Local Port**: `5001`  
**Date**: October 28, 2026  

---

## 1. Project Overview & Objectives

The **Franchise Scorecard & KPIs** platform transitions Mobile Klinik's legacy, static Excel-based reporting (`directives/dashboard_generator.md`) into a production-grade, multi-tenant web application.

Key capabilities delivered:
*   **Role-Based Access Control (RBAC)**: Enforces strict data isolation between Super Administrators (corporate oversight), Franchise Owners (multi-store regional view), Store Managers (single or assigned store operations), and Staff/Accountants.
*   **Automated Ingestion (ETL Engine)**: Dynamic extraction, normalization, deduplication, and upserting of multi-sheet Excel scorecards (`.xlsx`) into Supabase PostgreSQL with Name-First location resolution.
*   **Interactive Operations Dashboard**: High-density 7-tab interface featuring real-time KPI summaries, monthly historical trend charts, YoY and MoM comparative analytics, multi-benchmark selectors, top-performer leaderboard decorations, clickable navigation cards, dynamic metric visibility toggles, and CSV data export.
*   **Team & Store Administration Portal**: Comprehensive user provisioning, role editing, account suspension/activation, password resets, and search-filterable store location assignment.

---

## 2. System Architecture & Components

The application adheres strictly to the **3-Layer Architecture** defined in `AGENTS.md`:

```
               [ Layer 1: Directives (SOPs) ]
            directives/dashboard_generator.md
                          │
                          ▼
            [ Layer 2: Orchestration & Web API ]
     app.py ── routes/auth.py ── routes/dashboard.py
     routes/api.py ── routes/admin.py ── config.py
                          │
                          ▼
             [ Layer 3: Deterministic Execution ]
     ingest_scorecard.py ── create_user.py ── schema.sql
                          │
                          ▼
      [ Database: Supabase PostgreSQL (amjzomlovbuwjneqnumv) ]
```

### Components Breakdown:
*   **Layer 1 (Directives)**:
    *   [directives/dashboard_generator.md](file:///c:/Users/aquri/Antigravity/directives/dashboard_generator.md): Full standard operating procedure covering schema design, RBAC hierarchy, ETL rules, and reporting layout.
*   **Layer 2 (Flask Web App & REST API)**:
    *   `app.py`: WSGI entry point configured for local debugging and serverless Vercel deployment.
    *   `routes/auth.py`: Session authentication, password verification via Supabase Auth, compact session serialization (<300 bytes), redirect sanitization, and `@roles_required` decorator.
    *   `routes/dashboard.py`: Dashboard layout controller passing session context, periods, and permitted stores.
    *   `routes/api.py`: Secured REST endpoints (`/api/scorecard-data`, `/api/monthly-trend`, `/api/weekly-trend`, `/api/export-csv`) with multi-store ID parsing, access validation, multi-benchmark calculations, and MoM/YoY growth delta analysis.
    *   `routes/admin.py`: Team member management, user editing (`/admin/users/edit`), scorecard uploads, and store reassignment.
*   **Layer 3 (Deterministic Execution Tools)**:
    *   `ingest_scorecard.py`: Openpyxl-based ETL engine. Handles weekly traffic fallbacks, Excel date typo corrections, Name-First location resolution, and the Total Activations = New + Migrations rule.
    *   `create_user.py`: CLI and helper module for creating, updating, and reassigning store permissions via Supabase Auth Admin API and `user_profiles`.
    *   `schema.sql`: Complete DDL and seed script containing table definitions, RLS policies, PostgreSQL triggers, and pre-seeded stores.

---

## 3. Database Schema & Supabase Setup

All tables are active and operational on Supabase (`https://amjzomlovbuwjneqnumv.supabase.co`):

1.  **`locations`**:
    *   **85 active stores** in the franchise network (expanded dynamically from 40).
    *   Columns: `id` (UUID), `store_number` (INT, Unique), `name`, `short_name`, `region` (`WEST`, `EAST`), `store_type` (`franchise`, `corporate`), `is_active`.
2.  **`user_profiles`**:
    *   Columns: `id` (UUID, references `auth.users`), `full_name`, `email`, `role` (`super_admin`, `admin`, `store_manager`, `accountant`, `staff`), `organization_name`, `created_by`, `is_active`.
3.  **`user_location_access`**:
    *   Many-to-many relationship linking `user_id` $\rightarrow$ `location_id`.
4.  **`scorecard_periods`**:
    *   **15 normalized accounting periods**: `Oct 26 MTD` (Oct 1–25, 2026), `Sept 26`, `Aug 26`, `July 26`, `June 26`, `May 26`, `April 26`, `Mar 26`, `Feb 26`, `Jan 26`, `Jan 26 MTD`, `Dec 2025`, `Nov 25`, `Oct 2025`, `Sept 2025`.
5.  **`monthly_kpis`**:
    *   **528 total monthly KPI records** loaded across all franchise network locations.
    *   Composite unique constraint: `(location_id, period_id)`.
    *   Total Activations rule strictly enforced: `activations_total = activations_new + activations_migrations`.
    *   Contains 30+ financial & operational metrics (Gross revenue, ASP, activations split, CPO sales & attach rates, repairs OOW/insurance, foot traffic, conversion rates).
6.  **`weekly_kpis`**:
    *   High-frequency time series with composite constraint: `(location_id, week_end_date, metric_type)`.
    *   Covers `activation`, `cpo`, `repair`, and `traffic` metrics with WoW delta tracking.

---

## 4. Test Credentials & Pre-Provisioned Accounts

Three pre-configured test accounts are active in Supabase Auth and ready for validation:

| Role | Email | Password | Access Scope |
| :--- | :--- | :--- | :--- |
| **Super Admin** | `admin@mobileklinik.ca` | `AdminPassword2026!` | All 85 Network Locations & Full Admin Portal |
| **Franchise Owner** | `franchise.west@mobileklinik.ca` | `OwnerPassword2026!` | 8 West Stores (`333, 334, 326, 824, 825, 336, 335, 328`) |
| **Store Manager** | `manager.countryhills@mobileklinik.ca` | `ManagerPassword2026!` | Store #333 (Mobile Klinik Country Hills) |

---

## 5. Summary of Recent Improvements & Hardening

*   **Total Activations Architecture Rule**: Codified `Total Activations = Total New Activations MTD + Migrations` across the entire application stack:
    *   Updated `ingest_scorecard.py` to calculate `activations_total` deterministically.
    *   Synchronized 110 legacy rows in PostgreSQL that suffered from corporate formula discrepancies.
    *   Enforced in `routes/api.py` summary, store rows, benchmarks, and monthly trend aggregations.
    *   Added dedicated architecture banner in the Activations tab and updated Executive card subtext (`New: X | Migrations: Y`).
*   **Activations Tab 6 Dedicated KPI Cards**: Replaced old cards with a 6-card grid for:
    1. Total New Activation MTD (`kpi-act-new`)
    2. Telus Postpaid (`kpi-act-telus-post`)
    3. Koodo Postpaid (`kpi-act-koodo-post`)
    4. Pre Paid (`kpi-act-koodo-pre`)
    5. Renuals (`kpi-act-renewals`)
    6. Migrations (`kpi-act-migrations`)
    Plus a contract distribution breakdown doughnut chart (New Starts vs Renewals vs Migrations).
*   **Elimination of Weekly Graphs & Addition of 14-Month Historical Monthly Trends with YoY & MoM Analytics**:
    *   Removed weekly graphs across all tabs (`chart-weekly-activations`, `chart-weekly-cpo`, `chart-weekly-repairs`, `chart-weekly-traffic`).
    *   Added `/api/monthly-trend` endpoint delivering 14 continuous chronological accounting periods (`Sept 2025` to `Oct 26 MTD`).
    *   Built automatic MoM (vs immediately preceding month) and YoY (vs same month last year) delta engine with percentage growth tags.
    *   Added 4 interactive historical charts: Monthly Activations Trend (stacked New + Migrations with Total line), CPO Units & Revenue Trend (dual-axis), Repairs Historical Trend (stacked OOW + Insurance with Revenue line), and Foot Traffic & Conversion Rate Trend (dual-axis).
*   **Executive Pulse Multi-Benchmark Selector**:
    *   Updated `routes/api.py` to calculate `regional_benchmark`, `global_benchmark`, and `portfolio_benchmark` in one unified payload.
    *   Added an interactive button group in the Benchmark card header allowing users to toggle between **Regional**, **Global Network**, **My Stores**, and **Compare All** (plots Selected Store vs Regional Average vs Global Network baseline simultaneously).
*   **Store Performance Leaderboard: Top 3 Highlighting**:
    *   Added dedicated `Rank` column.
    *   Rank 1: `🥇 #1` gold badge, ambient gold row gradient, and gold highlight border.
    *   Rank 2: `🥈 #2` silver badge, silver row gradient, and silver highlight border.
    *   Rank 3: `🥉 #3` bronze badge, bronze row gradient, and bronze highlight border.
*   **Clickable KPI Widgets with Redirection**:
    *   Converted Executive Pulse KPI cards into clickable navigation targets redirecting users to their respective detail tabs (`Gross Revenue` & `Volume` $\rightarrow$ Benchmarks, `Activations` $\rightarrow$ Activations, `CPO` $\rightarrow$ CPO, `Repairs` $\rightarrow$ Repairs, `Conversion` $\rightarrow$ Traffic).
    *   Added `.clickable-card` CSS with hover lift (`translateY(-4px)`), ambient glow matching card accent color, and an animated hover badge indicator (`View Details →`).
*   **Admin Login 4KB Cookie Overflow Fix**:
    *   Diagnosed and resolved the admin login redirect loop on Vercel caused by RFC 6265 4KB cookie limits when the store network expanded to 85 stores.
    *   Slimmed down `session['user']` from 5,511 bytes to 258 bytes by querying store metadata dynamically from PostgreSQL.
    *   Added open redirect prevention and `/login` loop protection in `routes/auth.py`.
*   **Navigation Tabs Streamlined**: Renamed core navigation tabs and KPI modal chips per operational standards:
    *   `Carrier Activations` $\rightarrow$ `Activations`
    *   `Hardware & CPO` $\rightarrow$ `CPO`
    *   `Technical & Repairs` $\rightarrow$ `Repairs`
*   **Forensic Data Ingestion & Name-First Resolution Architecture**: Resolved corporate's human data-entry error in `Sept 26` (where Column A store numbers were shifted down 1 row across 17 stores, causing Lethbridge to show Landsdowne's $75,035 revenue). Built `normalize_store_name()` and a Name-First Location Resolution engine that automatically detects and reconciles store code column misalignments in Excel files, restoring Lethbridge to its true $171,113 revenue and $63,616 OOW repair revenue.
*   **Comprehensive Year-on-Year (YoY) Visualizations & Interactive View Switcher**:
    *   **Executive Pulse Growth Velocity Matrix**: Added a dedicated 6-card comparative performance section to the Executive Pulse tab showing real-time MoM (vs `Sept 26`) and YoY (vs `Oct 2025`) growth deltas for Gross Revenue (+117.9% YoY), Total Activations (+319.1% YoY), CPO Units (+154.5% YoY), Total Repairs (+88.4% YoY), Foot Traffic (+209.0% YoY), and Conversion Rate.
    *   **Prior Year (YoY Baseline) Dataset**: Plotted an amber dashed baseline directly on all chronological monthly charts (Revenue, Activations, CPO, Repairs, Traffic), connecting matching historical periods from 2025.
    *   **Interactive View Switcher**: Added `[14-Mo Trend]` vs `[YoY (2025 vs 2026)]` toggle buttons on every historical chart. In YoY mode, the chart plots 2025 vs 2026 side-by-side across calendar months (Jan–Dec) with hover tooltips displaying seasonal growth percentages.
    *   **Executive Monthly Revenue Trend Chart**: Added an interactive 2025 vs 2026 historical revenue chart to the Executive Pulse dashboard.
*   **Asset Cache Busting**: Configured `?v=1.5` query versions on static CSS and JS assets in base and dashboard templates.
*   **High-Visibility Chart Engine & Clean 14-Mo Trend Architecture**:
    *   Removed disconnected 2-point floating prior-year line in 14-Mo view; corporate tracking began in Sept 2025.
    *   Implemented executive glassmorphic pill badge data labels (`backgroundColor: "rgba(15, 23, 42, 0.95)"`, `borderColor: "..."`, `font: { weight: "800", size: 11 }`) preventing numbers from washing out.
    *   Brightened X-axis ticks to `#e2e8f0` (font-weight 600) and card subtitles to `#cbd5e1`.
    *   Overhauled Activations color scheme to Indigo (`#6366f1`), Sky Cyan (`#0ea5e9`), and Glowing Amber Gold (`#f59e0b`, 3.5px line).

---

## 6. How to Run & Validate Locally

```powershell
# 1. Navigate to project directory
cd c:\Users\aquri\Antigravity\Franchise-Scorecard-KPIs

# 2. Verify environment configuration (.env)
# Ensure SUPABASE_URL and SUPABASE_KEY are present

# 3. Start local development server
python app.py
```
Server runs at `http://127.0.0.1:5001`.

### Comprehensive Verification Checklist:
1. **Authentication & Session**:
   * Log in as Super Admin (`admin@mobileklinik.ca` / `AdminPassword2026!`).
   * Verify session cookie remains compact (~258 bytes) and does not trigger RFC 6265 browser overflow.
   * Verify `/login?next=...` sanitization prevents redirect loops and open redirect vulnerabilities.
2. **Clickable KPI Widgets**:
   * Click on each top KPI card in Executive Pulse (Gross Revenue, Sales Volume, Activations, CPO, Repairs, Conversion Rate).
   * Verify smooth hover elevation (`translateY(-4px)`), ambient glow, animated `View Details →` badge, and immediate redirection to the corresponding operational tab.
3. **Total Activations Architecture Rule**:
   * Navigate to the **Activations** tab.
   * Verify the architecture banner: `Total Activations = Total New Activations MTD + Migrations`.
   * Verify that the 6 KPI cards accurately reflect the database:
     * `Total New Activation MTD` (`kpi-act-new`)
     * `Telus Postpaid` (`kpi-act-telus-post`)
     * `Koodo Postpaid` (`kpi-act-koodo-post`)
     * `Pre Paid` (`kpi-act-koodo-pre`)
     * `Renuals` (`kpi-act-renewals`)
     * `Migrations` (`kpi-act-migrations`)
   * Verify contract mix donut breakdown (New Starts vs Renewals vs Migrations).
4. **14-Month Continuous Historical Monthly Trends & MoM/YoY Deltas**:
   * Inspect the 4 historical monthly trend charts across Activations, CPO, Repairs, and Traffic.
   * Verify continuous chronological sequence across 14 accounting periods (`Sept 2025` to `Oct 26 MTD`) with interim snapshot pruning (`Jan 26 MTD` omitted).
   * Verify dynamic MoM (vs preceding month) and YoY (vs same month prior year) delta tags with colored micro-badges (`▲` green, `▼` red).
5. **Executive Pulse Multi-Benchmark Selector**:
   * On the Executive Pulse tab, toggle the Benchmark Selector between:
     * `Regional Benchmark`
     * `Global Network Benchmark` (all 78+ franchise stores)
     * `My Stores` (user-owned portfolio)
     * `Compare All` (simultaneous multi-overlay radar view)
6. **Store Performance Leaderboard**:
   * Verify the dedicated `Rank` column.
   * Verify gold podium styling for `🥇 #1` (ambient gold gradient and border).
   * Verify silver podium styling for `🥈 #2` (ambient silver gradient and border).
   * Verify bronze podium styling for `🥉 #3` (ambient bronze gradient and border).
7. **Team & Location Administration**:
   * Navigate to `/admin/users`.
   * Test provisioning a new user with store search filtering.
   * Test editing an existing user's display name, role, active status, or store mapping.
   * Test direct password reset via Supabase Admin API.

---

## 7. Production Deployment Checklist (Vercel)

1.  **Git Repository**: Connected to `https://github.com/mrvenom1989-code/Franchise-Scorecard-KPIs-.git` (branch: `main`).
2.  **Vercel Configuration**: Pre-configured with `vercel.json` routing all requests to `app.py`.
3.  **Environment Variables in Vercel Project Settings**:
    *   `SUPABASE_URL`: `https://amjzomlovbuwjneqnumv.supabase.co`
    *   `SUPABASE_KEY`: Service role secret key (from `.env`)
    *   `FLASK_SECRET_KEY`: `mk_scorecard_super_secret_2026_k9`
4.  **Application Isolation**: The dedicated Supabase instance guarantees 100% database isolation from Reputation Guardian.
5.  **Live Production URL**: `https://franchise-scorecard-kp-is-drab.vercel.app/`

---

## 8. Deployment & Synchronization Status

| Component | Status | Details |
| :--- | :--- | :--- |
| **Git Remote** | Synced | `https://github.com/mrvenom1989-code/Franchise-Scorecard-KPIs-.git` (`main` @ `4d83eaf`) |
| **Vercel Production** | Live | `https://franchise-scorecard-kp-is-drab.vercel.app/` (HTTP 200 OK, `v=1.5`) |
| **Supabase PostgreSQL** | Active | `amjzomlovbuwjneqnumv.supabase.co` (85 locations, 528 monthly KPIs, 15 periods) |
| **Total Activations Rule** | Active | Enforced in ETL, database (110 rows synced), REST API, and frontend |
| **Tab Nomenclature** | Active | `Activations`, `CPO`, `Repairs` deployed across templates and controllers |
| **Chart Visibility & Labels** | Active | Glassmorphic pill badge data labels, bright `#e2e8f0` ticks, tri-tone palettes |
| **YoY Timeline Architecture**| Active | Clean 14-Mo trend + side-by-side YoY (2025 vs 2026) mode with tracking badge |

---

## 9. Recent Enhancements: YoY Timeline & High-Legibility Visualization

1. **Clarification on Historical Data Availability**:
   * Direct verification of corporate source workbook `Updated Franchise Scorecard - Oct MTD EOD - 10-25-26.xlsx` confirmed that corporate began franchise network tracking in **September 2025**. Months Jan–Aug 2025 were never recorded by corporate.
   * Consequently, prior-year comparisons only exist for matching months Sept & Oct.
   * Removed the disconnected 2-point floating yellow baseline from the continuous 14-month view to eliminate user confusion (which looked like broken or missing data for Jan–Aug 2026).
   * Exact YoY growth is surfaced in hover tooltips (`YoY Growth vs Sept 2025: +411.3%`, `YoY Growth vs Oct 2025: +149.4%`) and top-right header badges.
   * Dedicated side-by-side annual comparison is available via the `[YoY (2025 vs 2026)]` switcher button.
   * Added an informational note badge under all charts explaining corporate historical tracking origins.

2. **High-Visibility Badge Pill Data Labels**:
   * Overhauled all data labels into executive pill badges with solid dark backdrops (`rgba(15, 23, 42, 0.95)`), 1.5px colored borders matching each metric, 11px bold typography, and padding.
   * Numbers never blend into dark backgrounds, lines, or bars.
   * Brightened all X-axis ticks to `#e2e8f0` (Slate 200, weight 600) and card subtitles to `#cbd5e1`.
   * Upgraded Activations color palette: New Activations (Indigo Blue `#6366f1`), Migrations (Sky Cyan `#0ea5e9`), Total Activations Line (Glowing Amber Gold `#f59e0b`, 3.5px line width with white/gold points).

