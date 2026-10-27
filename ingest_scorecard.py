import openpyxl
import os
import sys
import json
import argparse
import re
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

def normalize_store_name(s):
    """Normalizes store names for robust matching across spreadsheets with typos or varied formats."""
    if not s:
        return ""
    s = str(s).lower()
    s = re.sub(r'\(.*?\)', '', s)  # strip (Oct 17), (326), etc.
    s = s.replace('mobile klinik', '').replace('frchs-', '').replace('franchise', '').strip()
    s = re.sub(r'[^a-z0-9]', '', s)  # remove spaces, punctuation
    # Common corporate aliases and typos in Excel sheets
    if 'boardwalk' in s and 'kitchener' in s:
        return 'kitchener'
    if s == 'lansdowne':
        return 'landsdowne'
    if s == 'wem':
        return 'westedmontonmall'
    if s == 'kp':
        return 'kildonanplace'
    return s

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

def extract_store_num(val):
    """Extracts integer store number from ints, floats (826.0), pure digits ('333'), or corporate prefix codes ('F3333', 'F3326', 'F8824')."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip()
    if not s:
        return None
    # Strip leading corporate/franchise letter if present
    if s[0].upper() in ['F', 'C']:
        s = s[1:]
    if '.' in s:
        try:
            s = str(int(float(s)))
        except ValueError:
            pass
    if s.isdigit():
        # Handle 4-digit codes where first two digits are repeated region prefix (e.g. 3333 -> 333, 3326 -> 326, 8824 -> 824)
        if len(s) == 4 and s[0] == s[1]:
            return int(s[1:])
        return int(s)
    return None

def normalize_region(prov_or_region):
    """Maps provinces (ON, BC, AB, MB, QB) or tier codes (W1, Ex) to strictly 'EAST' or 'WEST'."""
    if not prov_or_region:
        return 'WEST'
    s = str(prov_or_region).strip().upper()
    if s in ['EAST', 'WEST']:
        return s
    if s.startswith('W'):
        return 'WEST'
    if s.startswith('E'):
        return 'EAST'
    if s in ['BC', 'AB', 'SK', 'MB', 'YT', 'NT', 'NU']:
        return 'WEST'
    if s in ['ON', 'QC', 'QB', 'NB', 'NS', 'PE', 'PEI', 'NL']:
        return 'EAST'
    return 'WEST'

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
        return [], None, None, None

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
        store_num = extract_store_num(store_val)
        store_name = str(r[store_c + 1]).strip() if (store_c + 1) < len(r) and r[store_c + 1] is not None else ""

        # Skip rows with no store info or summary rows
        if not store_num and not store_name:
            continue
        if store_name.lower() in ["total", "corporate", "franchise", "average", "none", "#ref!"]:
            continue

        raw_reg = r[store_c + 2] if (store_c + 2) < len(r) else None
        region = normalize_region(raw_reg)

        record = {
            "store_number": store_num,
            "raw_store_val": store_val,
            "store_name": store_name,
            "region": region,
            "sheet": sheet_name,
            "period_type": period_type,
            "kpis": {},
            "extended": {}
        }

        # Helper to search header (searches pure row 8 metric_row, then composite col_headers)
        def get_val(*pattern_lists, forbidden=None):
            forbidden = forbidden or []
            # 1. First search metric_row directly
            for group in pattern_lists:
                if isinstance(group, str):
                    group = [group]
                for col_idx, m_val in enumerate(metric_row):
                    if m_val is not None:
                        m_str = str(m_val).strip().lower()
                        if all(k.lower() in m_str for k in group):
                            if not any(f.lower() in m_str for f in forbidden):
                                if col_idx < len(r) and r[col_idx] is not None:
                                    return r[col_idx]
            # 2. Search composite col_headers
            for group in pattern_lists:
                if isinstance(group, str):
                    group = [group]
                for col_idx, h in col_headers.items():
                    if all(k.lower() in h for k in group):
                        if not any(f.lower() in h for f in forbidden):
                            if col_idx < len(r) and r[col_idx] is not None:
                                return r[col_idx]
            return None

        # Canonical metric extraction
        record["kpis"]["gross_revenue_actual"] = clean_num(get_val(
            ["total gross revenue mtd"],
            ["gross revenue mtd"],
            ["all revenue", "mtd", "gross revenue"],
            ["gross revenue"],
            forbidden=["projected", "mom total", "yoy total", "mom rev", "yoy rev", "%"]
        ))
        record["kpis"]["gross_revenue_projected"] = clean_num(get_val(
            ["projected total gross revenue"],
            ["projected gross revenue"],
            ["projected", "gross revenue"]
        ))
        record["kpis"]["gross_revenue_mom_delta"] = clean_num(get_val(
            ["mom rev delta"],
            ["mom", "rev delta"],
            ["mom total gross revenue"]
        ))
        record["kpis"]["gross_revenue_yoy_delta"] = clean_num(get_val(
            ["yoy revenue delta"],
            ["yoy", "revenue delta"],
            ["yoy total gross revenue"]
        ))
        record["kpis"]["sales_volume"] = int(clean_num(get_val(
            ["total sales"],
            ["all revenue", "mtd", "total sales"],
            forbidden=["projected", "mom", "yoy", "accessory", "volume %"]
        )))
        record["kpis"]["asp"] = clean_num(get_val(
            ["asp"],
            ["all revenue", "mtd", "asp"],
            forbidden=["mom", "yoy", "oow", "repair"]
        ))
        record["kpis"]["daily_avg_revenue"] = clean_num(get_val(
            ["avg daily $"],
            ["avg daily rev"],
            ["all revenue", "mtd", "avg daily $"]
        ))

        # Activations
        record["kpis"]["activations_total"] = int(clean_num(get_val(
            ["total activation trans mtd"],
            ["total activation transactions mtd"],
            ["all activations", "mtd", "total activation transactions"],
            ["total activation"],
            forbidden=["projected", "mom", "yoy", "%", "attach"]
        )))
        record["kpis"]["activations_new"] = int(clean_num(get_val(
            ["total new activation mtd"],
            ["all activations", "mtd", "total new activation"],
            ["total new activation"],
            forbidden=["projected", "mom", "yoy"]
        )))
        record["kpis"]["activations_renewals"] = int(clean_num(get_val(
            ["renuals"],
            ["renewals"],
            ["all activations", "mtd", "renuals"],
            forbidden=["mom", "yoy", "smb", "new"]
        )))
        record["kpis"]["activations_migrations"] = int(clean_num(get_val(
            ["migrations"],
            ["all activations", "mtd", "migrations"],
            forbidden=["mom", "yoy"]
        )))
        record["kpis"]["activations_telus_post"] = int(clean_num(get_val(
            ["tpost"],
            ["telus post"],
            ["all activations", "telus post"],
            forbidden=["mom", "yoy"]
        )))
        record["kpis"]["activations_koodo_post"] = int(clean_num(get_val(
            ["kpost"],
            ["koodo post"],
            ["all activations", "koodo post"],
            forbidden=["mom", "yoy"]
        )))
        record["kpis"]["activations_koodo_pre"] = int(clean_num(get_val(
            ["pre paid"],
            ["pre-paid"],
            ["koodo pre"],
            ["all activations", "koodo pre"],
            forbidden=["mom", "yoy"]
        )))

        # CPO Hardware
        record["kpis"]["cpo_units_actual"] = int(clean_num(get_val(
            ["all cpo units mtd"],
            ["cpo", "mtd", "all cpo units"],
            ["all cpo units"],
            forbidden=["projected", "mom", "yoy"]
        )))
        record["kpis"]["cpo_units_projected"] = int(clean_num(get_val(
            ["projected all cpo units"],
            ["cpo", "projected all cpo units"]
        )))
        record["kpis"]["cpo_revenue_actual"] = clean_num(get_val(
            ["all cpo rev mtd"],
            ["cpo", "mtd", "all cpo rev"],
            ["all cpo rev"],
            forbidden=["projected", "mom", "yoy"]
        ))
        record["kpis"]["cpo_attach_activations_count"] = int(clean_num(get_val(
            ["# of activations attached to cpo sales mtd"],
            ["cpo", "mtd", "# of activations attached to c"],
            forbidden=["projected", "mom", "yoy"]
        )))
        record["kpis"]["cpo_attach_activations_pct"] = clean_num(get_val(
            ["% of activation attach to cpo mtd"],
            ["cpo", "mtd", "% of activation attach to cpo"],
            forbidden=["projected", "mom", "yoy"]
        ))
        record["kpis"]["cpo_avg_sale"] = clean_num(get_val(
            ["avg cpo sale"],
            ["cpo", "avg cpo sale"]
        ))
        record["kpis"]["trade_in_units"] = int(clean_num(get_val(
            ["cpo trade-ins mtd"],
            ["trade-ins", "cpo trade-ins mtd"],
            forbidden=["projected", "mom", "yoy"]
        )))

        # Technical Services & Repairs
        record["kpis"]["repairs_oow_volume"] = int(clean_num(get_val(
            ["total oow repairs"],
            ["oow repair", "total oow repairs"],
            forbidden=["projected", "mom", "yoy"]
        )))
        record["kpis"]["repairs_oow_revenue"] = clean_num(get_val(
            ["total oow revenue"],
            ["oow repair", "total oow revenue"],
            forbidden=["projected", "mom", "yoy"]
        ))
        record["kpis"]["repairs_oow_daily_avg"] = clean_num(get_val(
            ["oow repair/day"],
            ["oow repair", "oow repair/day"]
        ))
        record["kpis"]["repair_attach_activations_count"] = int(clean_num(get_val(
            ["# of activations attached to oow repair sales mtd"],
            ["# of activations attached to oow repair"],
            forbidden=["projected", "mom", "yoy"]
        )))
        record["kpis"]["repair_attach_activations_pct"] = clean_num(get_val(
            ["% of activation attach to oow repair mtd"],
            ["% of activation attach to oow repair"],
            forbidden=["projected", "mom", "yoy"]
        ))
        record["kpis"]["repairs_insurance_volume"] = int(clean_num(get_val(
            ["total insurance repairs mtd"],
            ["total insurance repairs"],
            ["insurance repair", "total insurance repairs"],
            forbidden=["projected", "mom", "yoy"]
        )))
        record["kpis"]["repairs_insurance_revenue"] = clean_num(get_val(
            ["total insurance rev mtd"],
            ["total insurance rev"],
            ["insurance repair", "total insurance rev"],
            forbidden=["projected", "mom", "yoy"]
        ))

        # Retail & Accessories
        record["kpis"]["accessories_volume"] = int(clean_num(get_val(
            ["total # accessory volume"],
            ["total accessory volume"],
            forbidden=["projected", "mom", "yoy"]
        )))
        record["kpis"]["accessories_revenue"] = clean_num(get_val(
            ["total accessory revenue mtd"],
            ["total accessory revenue"],
            forbidden=["projected", "mom", "yoy"]
        ))
        record["kpis"]["accessory_attach_oow_repair_pct"] = clean_num(get_val(
            ["accessory attach % on oow repair"],
            forbidden=["projected", "mom", "yoy"]
        ))
        record["kpis"]["protection_bundles_volume"] = int(clean_num(get_val(
            ["protection bundle mtd"],
            forbidden=["projected", "mom", "yoy"]
        )))

        # Traffic & Funnel
        record["kpis"]["foot_traffic_total"] = int(clean_num(get_val(
            ["total traffic mtd"],
            forbidden=["projected", "mom", "yoy"]
        )))
        record["kpis"]["foot_traffic_daily_avg"] = clean_num(get_val(
            ["avg daily traffic"],
            forbidden=["projected", "mom", "yoy"]
        ))
        record["kpis"]["foot_traffic_7day_ma"] = clean_num(get_val(
            ["traffic 7day ma"]
        ))
        record["kpis"]["tickets_opened_7day_ma"] = clean_num(get_val(
            ["ticket opened 7day ma"]
        ))
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
            # Correct typo in Excel file: 2026-12-XX should be 2025-12-XX
            if d.year == 2026 and d.month == 12:
                d = date(2025, 12, d.day)
            date_cols.append((c_idx, d))
        elif isinstance(val, str) and ("2025" in val or "2026" in val):
            try:
                d = datetime.strptime(val[:10], "%Y-%m-%d").date()
                if d.year == 2026 and d.month == 12:
                    d = date(2025, 12, d.day)
                date_cols.append((c_idx, d))
            except Exception:
                pass

    records = []
    for r in ws.iter_rows(min_row=header_r + 1, values_only=True):
        if not any(v is not None for v in r):
            continue
        store_val = r[store_c] if store_c < len(r) else None
        store_num = extract_store_num(store_val)
        if store_num is None:
            continue

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
    wow_sheets = {"WOW Activation", "WOW CPO Volume", "WOW WI Repair Volume", "WOW Traffic"}
    # Dynamically discover all monthly scorecard sheets (ignoring weekly WOW sheets, Cover, etc.)
    monthly_sheets = [s for s in wb.sheetnames if s.strip() not in wow_sheets and not s.strip().startswith("Cover") and not s.strip().startswith("Outdoor") and not s.strip().startswith("Koodo")]
    print(f"Dynamically discovered {len(monthly_sheets)} monthly scorecard sheet(s): {monthly_sheets}")

    for s_name in monthly_sheets:
        if s_name in wb.sheetnames:
            print(f"Parsing monthly sheet: {s_name}...")
            records, p_start, p_end, p_type = parse_monthly_sheet(wb[s_name], s_name)
            if records:
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

    # 1. Fetch locations map with name indexing for human-error resilience
    loc_resp = supabase.table("locations").select("id, store_number, name, short_name, region").execute()
    locations_list = loc_resp.data

    num_to_loc = {row["store_number"]: row for row in locations_list}
    name_to_loc = {}
    for row in locations_list:
        n1 = normalize_store_name(row["name"])
        n2 = normalize_store_name(row.get("short_name"))
        if n1:
            name_to_loc[n1] = row
        if n2:
            name_to_loc[n2] = row
    print(f"Mapped {len(locations_list)} locations ({len(name_to_loc)} name aliases) in Supabase.")

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
            raw_name = r["store_name"]
            raw_num = r["store_number"]
            norm_n = normalize_store_name(raw_name)

            matched_loc = None
            # 1. Primary: Match by canonical location name (protects against Excel column copy-paste row shifts)
            if norm_n and norm_n in name_to_loc:
                matched_loc = name_to_loc[norm_n]
                if raw_num and raw_num != matched_loc["store_number"]:
                    print(f"  [RECONCILED] Sheet '{s_name}' row '{raw_name}': Excel has code '{r.get('raw_store_val')}' (#{raw_num}), but canonical store is #{matched_loc['store_number']}. Reconciled by Location Name!")
            # 2. Secondary: Match by store number if name didn't match
            elif raw_num and raw_num in num_to_loc:
                matched_loc = num_to_loc[raw_num]

            # 3. Auto-provision if completely new store
            if not matched_loc:
                try:
                    clean_name = raw_name.split("(")[0].strip() or f"Store {raw_num}"
                    new_num = raw_num or 999
                    new_loc = supabase.table("locations").insert({
                        "store_number": new_num,
                        "name": f"Mobile Klinik {clean_name}",
                        "short_name": clean_name,
                        "region": normalize_region(r.get("region")),
                        "store_type": "franchise",
                        "is_active": True
                    }).execute()
                    if new_loc.data:
                        matched_loc = new_loc.data[0]
                        num_to_loc[matched_loc["store_number"]] = matched_loc
                        name_to_loc[normalize_store_name(matched_loc["name"])] = matched_loc
                        name_to_loc[normalize_store_name(clean_name)] = matched_loc
                        print(f"  [AUTO-PROVISION] Added new store #{new_num} - {clean_name} ({normalize_region(r.get('region'))})")
                except Exception as e:
                    print(f"  [WARN] Failed to auto-provision store '{raw_name}' (#{raw_num}): {e}")

            if not matched_loc:
                continue

            loc_id = matched_loc["id"]
            item = dict(r["kpis"])
            item["location_id"] = loc_id
            item["period_id"] = period_id

            # Fallback: If monthly sheet omitted traffic (e.g. Jan 26 sensor outage), sum available weekly traffic
            if item.get("foot_traffic_total", 0) == 0:
                w_traffic_sum = 0
                for w in all_weekly:
                    if w["store_number"] == matched_loc["store_number"] and w["metric_type"] == "traffic":
                        w_date = str(w["week_end_date"])
                        if str(p_info["start_date"]) <= w_date <= str(p_info["end_date"]):
                            w_traffic_sum += int(w["value"] or 0)
                if w_traffic_sum > 0:
                    item["foot_traffic_total"] = w_traffic_sum
                    p_days = (p_info["end_date"] - p_info["start_date"]).days + 1
                    item["foot_traffic_daily_avg"] = round(w_traffic_sum / max(1, p_days), 1)
                    tot_sales = item["activations_total"] + item["cpo_units_actual"] + item["repairs_oow_volume"]
                    item["conversion_rate_pct"] = round((tot_sales / w_traffic_sum) * 100.0, 2)

            kpi_payload.append(item)
        
        if kpi_payload:
            supabase.table("monthly_kpis").upsert(kpi_payload, on_conflict="location_id,period_id").execute()
            print(f"Upserted {len(kpi_payload)} rows into monthly_kpis for {s_name}.")

    # 3. Upsert weekly KPIs (deduplicated by composite key)
    weekly_dict = {}
    for w in all_weekly:
        loc_obj = num_to_loc.get(w["store_number"])
        if not loc_obj:
            continue
        loc_id = loc_obj["id"]
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
