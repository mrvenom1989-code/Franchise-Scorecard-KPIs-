# Mobile Klinik Franchise Scorecard & Operations Platform

A modern, multi-tenant operations dashboard and performance analytics engine for Mobile Klinik franchise owners, store managers, and executives.

---

## 1. Architecture & Tech Stack

*   **Database**: Supabase (PostgreSQL) — Project: `https://amjzomlovbuwjneqnumv.supabase.co`
*   **Backend & ETL**: Python 3.12 (`openpyxl`, `supabase-py`, `Flask`)
*   **Frontend**: Modern HTML5 / Vanilla CSS with glassmorphic aesthetic, Chart.js / ApexCharts, and responsive tabbed navigation
*   **Hosting**: Vercel

---

## 2. User Roles & Access Control (RBAC)

1.  **Super Admin**: Platform owner with unrestricted access across all 28 franchise stores + 12 corporate benchmark locations. Manages user provisioning, system settings, and Excel scorecard ingestion.
2.  **Admin (Franchise Owner)**: Multi-store owners who see:
    *   **Consolidated Portfolio View**: Aggregate performance across all their owned locations.
    *   **Store Drill-Down**: Individual store performance metrics.
    *   **Anonymized Benchmarking**: Portfolio vs. Regional/Franchise Network average.
    *   **Staff Delegation**: Can create and assign **Store Managers** strictly for their own stores.
3.  **Store Manager**: Location-level operator locked strictly to their assigned store(s).
4.  **Accountant / Read-Only**: Access to financials and exports without user administration rights.
5.  **Frontline Staff**: Operational unit counts and attach rates with **gross dollar revenue and ASP masked**.

---

## 3. Database Setup

1. Open your [Supabase SQL Editor](https://supabase.com/dashboard/project/amjzomlovbuwjneqnumv/sql).
2. Copy and paste the contents of `schema.sql` and run it.
3. This creates:
   * `locations` (Pre-seeded with all 28 franchise stores and 12 corporate stores)
   * `user_profiles` & `user_location_access`
   * `scorecard_periods`
   * `monthly_kpis`
   * `weekly_kpis`
   * Trigger for automated user profile provisioning

---

## 4. Ingesting Scorecard Data

1. Copy `.env.example` to `.env` and configure your credentials:
   ```env
   SUPABASE_URL=https://amjzomlovbuwjneqnumv.supabase.co
   SUPABASE_KEY=your_service_role_key_here
   FLASK_SECRET_KEY=your_secret_key_here
   ```
2. Test extraction in dry-run mode:
   ```bash
   python ingest_scorecard.py --dry-run
   ```
3. Run the live ingestion into Supabase:
   ```bash
   python ingest_scorecard.py --file "Franchise Scorecard KPIs  - WoW ending 01-18-26.xlsx"
   ```

---

## 5. Reporting Modules & Tabs

*   **Executive Scorecard**: High-level financial KPIs, projected vs actual, MoM/YoY growth, and store leaderboard.
*   **Carrier Activations**: Telus & Koodo breakdown (New, Renewals, Migrations, Postpaid vs Prepaid, Financing).
*   **Hardware & CPO**: Certified Pre-Owned units, revenue, ASP, and **CPO Activation Attach Rate %**.
*   **Service & Repairs**: Out of Warranty (OOW) vs Insurance repairs, daily turnaround, and **Repair-to-Activation Attach Rate %**.
*   **Retail & Accessories**: Accessory revenue, daily sales rate, accessory attach % on repairs, and protection bundles.
*   **Foot Traffic & Funnel**: Door traffic, tickets opened, and conversion rate %.
*   **Store Benchmarking**: Side-by-side radar and comparative multi-bar charts.
