import openpyxl
import os
import sys
import json
import argparse
from datetime import datetime, date

# Load environment variables if python-dotenv is present
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        load_dotenv()
except ImportError:
    pass

def clean_num(val, default=0.0):
    """Cleans numeric values from Excel cells, converting #DIV/0!, strings, and NaNs to float/int."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return val
    s = str(val).strip().replace("$", "").replace(",", "")
    if s.endswith("%"):
        try:
            return float(s[:-1]) / 100.0
        except ValueError:
            return default
    if s in ["#DIV/0!", "#N/A", "NA", "N/A", "--", "-", "None", ""]:
        return default
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return default

def find_header_row(ws, max_r=12):
    """Finds the header row containing 'MK Store #' or 'Store #'."""
    for r_idx in range(1, max_r + 1):
        row = [cell for cell in next(ws.iter_rows(min_row=r_idx, max_row=r_idx, values_only=True))]
        for c_idx, val in enumerate(row):
            if val is not None:
                s = str(val).strip().lower()
                if "mk store #" in s or s == "store #" or "store id" in s:
                    return r_idx, c_idx
    return None, None

def parse_monthly_sheet(ws, sheet_name):
    """Parses a monthly scorecard sheet (e.g. Jan 26 MTD, Dec 2025)."""
    header_r, store_c = find_header_row(ws)
    if header_r is None:
        print(f"  [WARN] Header not found for sheet {sheet_name}")
        return []

    # Read category row (usually header_r - 4 or header_r - 3)
    cat_r = max(1, header_r - 4)
    cat_row = list(ws.iter_rows(min_row=cat_r, max_row=cat_r, values_only=True))[0]
    sub_r = max(1, header_r - 3)
    sub_row = list(ws.iter_rows(min_row=sub_r, max_row=sub_r, values_only=True))[0]
    metric_row = list(ws.iter_rows(min_row=header_r, max_row=header_r, values_only=True))[0]

    # Map column indexes to composite headers
    col_headers = {}
    curr_cat = ""
    curr_sub = ""
    for idx in range(len(metric_row)):
        if idx < len(cat_row) and cat_row[idx] is not None and str(cat_row[idx]).strip():
            curr_cat = str(cat_row[idx]).strip()
        if idx < len(sub_row) and sub_row[idx] is not None and str(sub_row[idx]).strip():
            curr_sub = str(sub_row[idx]).strip()
        metric = str(metric_row[idx]).strip() if metric_row[idx] is not None else f"col_{idx}"
        col_headers[idx] = f"{curr_cat}::{curr_sub}::{metric}".lower()

    # Determine period start/end dates from rows 2 and 3
    r2 = list(ws.iter_rows(min_row=2, max_row=2, values_only=True))[0]
    r3 = list(ws.iter_rows(min_row=3, max_row=3, values_only=True))[0]
    
    period_start = None
    for cell in r2:
        if isinstance(cell, (datetime, date)):
            period_start = cell.date() if isinstance(cell, datetime) else cell
            break
            
    period_end = None
    for cell in r3:
        if isinstance(cell, (datetime, date)):
            period_end = cell.date() if isinstance(cell, datetime) else cell
            break
            
    if not period_start:
        period_start = date(2026, 1, 1)
    if not period_end:
        import calendar
        last_day = calendar.monthrange(period_start.year, period_start.month)[1]
        period_end = date(period_start.year, period_start.month, last_day)

    period_type = "MTD" if "MTD" in sheet_name.upper() else "FULL_MONTH"

    rows = []
    for r in ws.iter_rows(min_row=header_r + 1, values_only=True):
        if not any(v is not None for v in r):
            continue
        store_val = r[store_c] if store_c < len(r) else None
        if store_val is None or not str(store_val).strip().isdigit():
            continue
        
        store_num = int(str(store_val).strip())
        store_name = str(r[store_c + 1]).strip() if (store_c + 1) < len(r) and r[store_c + 1] is not None else ""
        region = str(r[store_c + 2]).strip() if (store_c + 2) < len(r) and r[store_c + 2] is not None else ""

        record = {
            "store_number": store_num,
            "store_name": store_name,
            "region": region,
            "sheet": sheet_name,
            "period_type": period_type,
            "kpis": {},
            "extended": {}
        }

        # Helper to search header
        def get_val(keywords):
            for col_idx, h in col_headers.items():
                if all(k.lower() in h for k in keywords):
                    if col_idx < len(r):
                        return r[col_idx]
            return None

        # Canonical metric extraction
        record["kpis"]["gross_revenue_actual"] = clean_num(get_val(["all revenue", "mtd", "gross revenue"]))
        record["kpis"]["gross_revenue_projected"] = clean_num(get_val(["all revenue", "projected total gross revenue"]))
        record["kpis"]["gross_revenue_mom_delta"] = clean_num(get_val(["all revenue", "mom", "rev delta"]))
        record["kpis"]["gross_revenue_yoy_delta"] = clean_num(get_val(["all revenue", "yoy", "revenue delta"]))
        record["kpis"]["sales_volume"] = int(clean_num(get_val(["all revenue", "mtd", "total sales"])))
        record["kpis"]["asp"] = clean_num(get_val(["all revenue", "mtd", "asp"]))
        record["kpis"]["daily_avg_revenue"] = clean_num(get_val(["all revenue", "mtd", "avg daily $"]))

        # Activations
        record["kpis"]["activations_total"] = int(clean_num(get_val(["all activations", "mtd", "total activation transactions"])))
        record["kpis"]["activations_new"] = int(clean_num(get_val(["all activations", "mtd", "total new activation"])))
        record["kpis"]["activations_renewals"] = int(clean_num(get_val(["all activations", "mtd", "renuals"])))
        record["kpis"]["activations_migrations"] = int(clean_num(get_val(["all activations", "mtd", "migrations"])))
        record["kpis"]["activations_telus_post"] = int(clean_num(get_val(["all activations", "telus post"])))
        record["kpis"]["activations_koodo_post"] = int(clean_num(get_val(["all activations", "koodo post"])))
        record["kpis"]["activations_koodo_pre"] = int(clean_num(get_val(["all activations", "koodo pre"])))

        # CPO Hardware
        record["kpis"]["cpo_units_actual"] = int(clean_num(get_val(["cpo", "mtd", "all cpo units"])))
        record["kpis"]["cpo_units_projected"] = int(clean_num(get_val(["cpo", "projected all cpo units"])))
        record["kpis"]["cpo_revenue_actual"] = clean_num(get_val(["cpo", "mtd", "all cpo rev"]))
        record["kpis"]["cpo_attach_activations_count"] = int(clean_num(get_val(["cpo", "mtd", "# of activations attached to c"])))
        record["kpis"]["cpo_attach_activations_pct"] = clean_num(get_val(["cpo", "mtd", "% of activation attach to cpo"]))
        record["kpis"]["cpo_avg_sale"] = clean_num(get_val(["cpo", "avg cpo sale"]))
        record["kpis"]["trade_in_units"] = int(clean_num(get_val(["trade-ins", "cpo trade-ins mtd"])))

        # Technical Services & Repairs
        record["kpis"]["repairs_oow_volume"] = int(clean_num(get_val(["oow repair", "total oow repairs"])))
        record["kpis"]["repairs_oow_revenue"] = clean_num(get_val(["oow repair", "total oow revenue"]))
        record["kpis"]["repairs_oow_daily_avg"] = clean_num(get_val(["oow repair", "oow repair/day"]))
        record["kpis"]["repair_attach_activations_count"] = int(clean_num(get_val(["oow repair", "# of activations attached to oow repair"])))
        record["kpis"]["repair_attach_activations_pct"] = clean_num(get_val(["oow repair", "% of activation attach to oow repair"]))
        record["kpis"]["repairs_insurance_volume"] = int(clean_num(get_val(["insurance repair", "total insurance repairs"])))
        record["kpis"]["repairs_insurance_revenue"] = clean_num(get_val(["insurance repair", "total insurance rev"]))

        # Retail & Accessories
        record["kpis"]["accessories_volume"] = int(clean_num(get_val(["accessory sales", "total # accessory volume"])))
        record["kpis"]["accessories_revenue"] = clean_num(get_val(["accessory sales", "total accessory revenue mtd"]))
        record["kpis"]["accessory_attach_oow_repair_pct"] = clean_num(get_val(["accessory sales", "accessory attach % on oow repair"]))
        record["kpis"]["protection_bundles_volume"] = int(clean_num(get_val(["protection bundles", "protection bundle mtd"])))

        # Traffic & Funnel
        record["kpis"]["foot_traffic_total"] = int(clean_num(get_val(["traffic", "total traffic mtd"])))
        record["kpis"]["foot_traffic_daily_avg"] = clean_num(get_val(["traffic", "avg daily traffic"]))
        record["kpis"]["foot_traffic_7day_ma"] = clean_num(get_val(["traffic", "traffic 7day ma"]))
        record["kpis"]["tickets_opened_7day_ma"] = clean_num(get_val(["traffic", "ticket opened 7day ma"]))
        if record["kpis"]["foot_traffic_total"] > 0:
            tot_transactions = record["kpis"]["activations_total"] + record["kpis"]["cpo_units_actual"] + record["kpis"]["repairs_oow_volume"]
            record["kpis"]["conversion_rate_pct"] = round((tot_transactions / record["kpis"]["foot_traffic_total"]) * 100.0, 2)
        else:
            record["kpis"]["conversion_rate_pct"] = 0.0

        rows.append(record)

    return rows, period_start, period_end, period_type

def parse_wow_sheet(ws, sheet_name, metric_type):
    """Parses a weekly tracker sheet (e.g. WOW Activation, WOW CPO Volume)."""
    header_r, store_c = find_header_row(ws)
    if header_r is None:
        return []
    
    header_row = list(ws.iter_rows(min_row=header_r, max_row=header_r, values_only=True))[0]
    
    # Identify date columns
    date_cols = []
    for c_idx, val in enumerate(header_row):
        if isinstance(val, (datetime, date)):
            d = val.date() if isinstance(val, datetime) else val
            date_cols.append((c_idx, d))
        elif isinstance(val, str) and ("2025" in val or "2026" in val):
            try:
                d = datetime.strptime(val[:10], "%Y-%m-%d").date()
                date_cols.append((c_idx, d))
            except Exception:
                pass

    records = []
    for r in ws.iter_rows(min_row=header_r + 1, values_only=True):
        if not any(v is not None for v in r):
            continue
        store_val = r[store_c] if store_c < len(r) else None
        if store_val is None or not str(store_val).strip().isdigit():
            continue
        
        store_num = int(str(store_val).strip())
        for c_idx, dt in date_cols:
            val = clean_num(r[c_idx] if c_idx < len(r) else None)
            delta_val = None
            if (c_idx + 1) < len(r):
                delta_val = clean_num(r[c_idx + 1], default=None)
            
            records.append({
                "store_number": store_num,
                "metric_type": metric_type,
                "week_end_date": str(dt),
                "value": val,
                "wow_delta": delta_val
            })
    return records

def main():
    parser = argparse.ArgumentParser(description="Ingest Franchise Scorecard Excel to Supabase")
    parser.add_argument("--file", default="Franchise Scorecard KPIs  - WoW ending 01-18-26.xlsx", help="Path to Excel scorecard file")
    parser.add_argument("--dry-run", action="store_true", help="Print summary without inserting into database")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"[ERROR] Excel file not found: {args.file}")
        sys.exit(1)

    print(f"Loading Excel file: {args.file}...")
    wb = openpyxl.load_workbook(args.file, data_only=True, read_only=True)
    print(f"Sheets in workbook: {wb.sheetnames}")

    all_monthly = {}
    monthly_sheets = ['Jan 26 MTD', 'Dec 2025 ', 'Nov 25', 'Oct 2025', 'Sept 2025']
    for s_name in monthly_sheets:
        if s_name in wb.sheetnames:
            print(f"Parsing monthly sheet: {s_name}...")
            records, p_start, p_end, p_type = parse_monthly_sheet(wb[s_name], s_name)
            all_monthly[s_name] = {
                "records": records,
                "start_date": p_start,
                "end_date": p_end,
                "period_type": p_type
            }
            print(f"  > Extracted {len(records)} store records ({p_start} to {p_end}).")

    all_weekly = []
    wow_map = {
        "WOW Activation": "activation",
        "WOW CPO Volume": "cpo",
        "WOW WI Repair Volume": "repair",
        "WOW Traffic": "traffic"
    }
    for s_name, m_type in wow_map.items():
        if s_name in wb.sheetnames:
            print(f"Parsing weekly sheet: {s_name} ({m_type})...")
            w_records = parse_wow_sheet(wb[s_name], s_name, m_type)
            all_weekly.extend(w_records)
            print(f"  > Extracted {len(w_records)} weekly points.")

    print("\n==================== INGESTION SUMMARY ====================")
    total_m_records = sum(len(v["records"]) for v in all_monthly.values())
    print(f"Total Monthly Store Records Extracted: {total_m_records}")
    print(f"Total Weekly Data Points Extracted:    {len(all_weekly)}")

    # Sample output
    if "Jan 26 MTD" in all_monthly and all_monthly["Jan 26 MTD"]["records"]:
        sample = all_monthly["Jan 26 MTD"]["records"][0]
        print(f"\nSample Store Record (Store {sample['store_number']} - {sample['store_name']}):")
        print(json.dumps(sample["kpis"], indent=2))

    if args.dry_run or not os.environ.get("SUPABASE_KEY"):
        print("\n[INFO] Running in DRY-RUN mode or SUPABASE_KEY not set. No database writes performed.")
        print("[INFO] To load into Supabase, set SUPABASE_KEY in .env and run without --dry-run.")
        return

    # Database insertion logic using supabase-py
    from supabase import create_client
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    supabase = create_client(supabase_url, supabase_key)

    # 1. Fetch locations map (store_number -> location_id)
    loc_resp = supabase.table("locations").select("id, store_number").execute()
    store_map = {row["store_number"]: row["id"] for row in loc_resp.data}
    print(f"Mapped {len(store_map)} locations in Supabase.")

    # 2. Upsert periods and monthly KPIs
    for s_name, p_info in all_monthly.items():
        records = p_info["records"]
        p_resp = supabase.table("scorecard_periods").upsert({
            "label": s_name.strip(),
            "start_date": str(p_info["start_date"]),
            "end_date": str(p_info["end_date"]),
            "period_type": p_info["period_type"]
        }, on_conflict="label").execute()
        period_id = p_resp.data[0]["id"]

        # Insert KPI rows
        kpi_payload = []
        for r in records:
            loc_id = store_map.get(r["store_number"])
            if not loc_id:
                continue
            item = dict(r["kpis"])
            item["location_id"] = loc_id
            item["period_id"] = period_id
            kpi_payload.append(item)
        
        if kpi_payload:
            supabase.table("monthly_kpis").upsert(kpi_payload, on_conflict="location_id,period_id").execute()
            print(f"Upserted {len(kpi_payload)} rows into monthly_kpis for {s_name}.")

    # 3. Upsert weekly KPIs (deduplicated by composite key)
    weekly_dict = {}
    for w in all_weekly:
        loc_id = store_map.get(w["store_number"])
        if not loc_id:
            continue
        key = (loc_id, w["week_end_date"], w["metric_type"])
        # If duplicate, prefer the one with non-zero or newer value
        if key not in weekly_dict or (weekly_dict[key]["value"] == 0 and w["value"] != 0):
            weekly_dict[key] = {
                "location_id": loc_id,
                "week_end_date": w["week_end_date"],
                "metric_type": w["metric_type"],
                "value": w["value"],
                "wow_delta": w["wow_delta"]
            }

    weekly_payload = list(weekly_dict.values())
    if weekly_payload:
        # Upsert in batches of 100
        for i in range(0, len(weekly_payload), 100):
            batch = weekly_payload[i:i+100]
            supabase.table("weekly_kpis").upsert(batch, on_conflict="location_id,week_end_date,metric_type").execute()
        print(f"Upserted {len(weekly_payload)} unique weekly data points.")

    print("\n[SUCCESS] Ingestion completed successfully!")

if __name__ == "__main__":
    main()
