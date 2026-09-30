# Franchise Scorecard & KPIs — Session Handoff

**Project**: Mobile Klinik Franchise Scorecard & Multi-Tenant Operations Dashboard  
**Repository**: [https://github.com/mrvenom1989-code/Franchise-Scorecard-KPIs-.git](https://github.com/mrvenom1989-code/Franchise-Scorecard-KPIs-.git)  
**Database**: Dedicated Supabase PostgreSQL Instance: `https://amjzomlovbuwjneqnumv.supabase.co`  
**Local Port**: `5001`  
**Date**: October 1, 2026  

---

## 1. Project Overview & Objectives

The **Franchise Scorecard & KPIs** platform transitions Mobile Klinik's legacy, static Excel-based reporting (`directives/dashboard_generator.md`) into a production-grade, multi-tenant web application.

Key capabilities delivered:
*   **Role-Based Access Control (RBAC)**: Enforces strict data isolation between Super Administrators (corporate oversight), Franchise Owners (multi-store regional view), Store Managers (single or assigned store operations), and Staff/Accountants.
*   **Automated Ingestion (ETL Engine)**: Dynamic extraction, normalization, deduplication, and upserting of multi-sheet Excel scorecards (`.xlsx`) into Supabase PostgreSQL.
*   **Interactive Operations Dashboard**: High-density 7-tab interface featuring real-time KPI summaries, Chart.js visualizations with point datalabels, multi-store checkbox filtering, sensor outage handling, dynamic metric visibility toggles, and CSV data export.
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
    *   `routes/auth.py`: Session authentication, password verification via Supabase Auth, and `@roles_required` decorator.
    *   `routes/dashboard.py`: Dashboard layout controller passing session context, periods, and permitted stores.
    *   `routes/api.py`: Secured REST endpoints (`/api/scorecard-data`, `/api/weekly-trend`, `/api/export-csv`) with multi-store ID parsing and access validation.
    *   `routes/admin.py`: Team member management, user editing (`/admin/users/edit`), scorecard uploads, and store reassignment.
*   **Layer 3 (Deterministic Execution Tools)**:
    *   `ingest_scorecard.py`: Openpyxl-based ETL engine. Handles weekly traffic fallbacks, Excel date typo corrections, and dynamic monthly sheet discovery.
    *   `create_user.py`: CLI and helper module for creating, updating, and reassigning store permissions via Supabase Auth Admin API and `user_profiles`.
    *   `schema.sql`: Complete DDL and seed script containing table definitions, RLS policies, PostgreSQL triggers, and 40 pre-seeded stores.

---

## 3. Database Schema & Supabase Setup

All tables are active and operational on Supabase (`https://amjzomlovbuwjneqnumv.supabase.co`):

1.  **`locations`**:
    *   40 pre-seeded stores (28 franchise stores + 12 corporate outdoor benchmark locations).
    *   Columns: `id` (UUID), `store_number` (INT, Unique), `name`, `short_name`, `region` (`WEST`, `EAST`), `store_type` (`franchise`, `corporate`), `is_active`.
2.  **`user_profiles`**:
    *   Columns: `id` (UUID, references `auth.users`), `full_name`, `email`, `role` (`super_admin`, `admin`, `store_manager`, `accountant`, `staff`), `organization_name`, `created_by`, `is_active`.
3.  **`user_location_access`**:
    *   Many-to-many relationship linking `user_id` $\rightarrow$ `location_id`.
4.  **`scorecard_periods`**:
    *   Normalized accounting periods: `Jan 26 MTD`, `Dec 2025`, `Nov 25`, `Oct 2025`, `Sept 2025`.
5.  **`monthly_kpis`**:
    *   Composite unique constraint: `(location_id, period_id)`.
    *   Contains 30+ financial & operational metrics (Gross revenue, ASP, activations split, CPO sales & attach rates, repairs OOW/insurance, foot traffic, conversion rates).
6.  **`weekly_kpis`**:
    *   High-frequency time series with composite constraint: `(location_id, week_end_date, metric_type)`.
    *   Covers `activation`, `cpo`, `repair`, and `traffic` metrics with WoW delta tracking.

---

## 4. Test Credentials & Pre-Provisioned Accounts

Three pre-configured test accounts are active in Supabase Auth and ready for validation:

| Role | Email | Password | Access Scope |
| :--- | :--- | :--- | :--- |
| **Super Admin** | `admin@mobileklinik.ca` | `AdminPassword2026!` | All 40 Network Locations & Full Admin Portal |
| **Franchise Owner** | `franchise.west@mobileklinik.ca` | `OwnerPassword2026!` | 8 West Stores (`333, 334, 326, 824, 825, 336, 335, 328`) |
| **Store Manager** | `manager.countryhills@mobileklinik.ca` | `ManagerPassword2026!` | Store #333 (Mobile Klinik Country Hills) |

---

## 5. Summary of Recent Improvements & Hardening

*   **Chart.js Data Point Labels**: Integrated `chartjs-plugin-datalabels` across Revenue Mix, Activations Donut, Repairs Donut, Benchmark Bar, Weekly Trends (4 lines), and Radar charts with compact formatting (`$Xk`, percentages, units) and zero suppression.
*   **Store Multi-Select Checkbox Dropdown**: Built custom floating dropdown in the dashboard toolbar with real-time substring search, "All"/"Clear" quick buttons, store number pills, and serialized comma-separated ID support.
*   **Conversion Funnel Outage Resolution**: Diagnosed and resolved the root cause of the "0" conversion rate in `Jan 26 MTD` by building an automated weekly traffic fallback in `ingest_scorecard.py` (recovering 3,111 door visits) and adding outage detection badges in `dashboard.js`.
*   **Comprehensive User Editing**: Added an Actions column with an interactive **Edit** modal in `/admin/users` allowing administrators to modify user names, roles, account status (active/suspended), password resets, and store mappings.
*   **Store Search Filter in Modals**: Added real-time store search filtering in both Provision and Edit user modals.
*   **CSS Stacking Context Hardening**: Fixed dropdown clipping by elevating `.control-bar` to `z-index: 900` and `#store-dropdown-menu` to `z-index: 9999 !important`.
*   **Asset Cache Busting**: Configured `?v=1.2` query versions on static CSS and JS assets in base templates.

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

### Verification Checklist:
1. Log in as Super Admin (`admin@mobileklinik.ca` / `AdminPassword2026!`).
2. Test the Multi-Select Location dropdown (search, check/uncheck stores, verify chart updates).
3. Switch period to `Dec 2025` and `Jan 26 MTD` to inspect the Store Conversion Funnel.
4. Navigate to `/admin/users` and test:
   * Provisioning a new user with store search.
   * Editing an existing user's display name, role, or store assignment.
   * Testing password reset.

---

## 7. Production Deployment Checklist (Vercel)

1.  **Git Repository**: Connected to `https://github.com/mrvenom1989-code/Franchise-Scorecard-KPIs-.git` (branch: `main`).
2.  **Vercel Configuration**: Pre-configured with `vercel.json` routing all requests to `app.py`.
3.  **Environment Variables to set in Vercel Project Settings**:
    *   `SUPABASE_URL`: `https://amjzomlovbuwjneqnumv.supabase.co`
    *   `SUPABASE_KEY`: Service role secret key (from `.env`)
    *   `FLASK_SECRET_KEY`: `mk_scorecard_super_secret_2026_k9`
4.  **Application Isolation**: The dedicated Supabase instance guarantees 100% database isolation from Reputation Guardian.
