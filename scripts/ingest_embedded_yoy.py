import os
import sys
import openpyxl
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

sys.path.insert(0, BASE_DIR)
from config import supabase
from ingest_scorecard import normalize_store_name, extract_store_num, clean_num

EXCEL_PATH = os.path.join(BASE_DIR, "Franchise Scorecard - Nov 26 EOD 11-15-26.xlsx")

# Configuration for extracting embedded YoY (2025) data from 2026 sheets
YOY_CONFIGS = [
    {
        "source_sheet": "Sept 26",
        "target_period_label": "Sept 2025",
        "header_row_idx": 7, # 0-indexed (row 8)
        "start_row_idx": 8,  # 0-indexed (row 9)
        "store_num_idx": 0,
        "store_name_idx": 1,
        "cols": {
            "rev": 20,       # YoY Total Gross Revenue
            "sales": 19,     # YoY Total Sales
            "traffic": 7,    # Total Traffic YoY
            "act_new": 51,   # Total New Activation
            "act_mig": 57,   # Migrations
            "cpo_u": 76,     # YoY CPO Units
            "cpo_r": 78,     # YoY CPO Rev
            "acc_u": 93,     # YoY Accessory Volume
            "acc_r": 94,     # YOY Accessory Revenue
            "bundle": 100,   # YoY Protection Bundle
            "rep_oow_u": 112,# YoY OOW # Repairs
            "rep_oow_r": 113,# YoY OOW Revenue
            "rep_ins_u": 124,# YoY Insurance Volume
            "rep_ins_r": 125 # YoY Insurance Revenue
        }
    },
    {
        "source_sheet": "Oct 26",
        "target_period_label": "Oct 2025",
        "header_row_idx": 4, # 0-indexed (row 5)
        "start_row_idx": 5,  # 0-indexed (row 6)
        "store_num_idx": 2,
        "store_name_idx": 3,
        "cols": {
            "rev": 22,       # YoY Total GroRev
            "sales": 21,     # YoY Total Sales
            "traffic": 9,    # Traffic YoY
            "act_new": 53,   # New Act YoY
            "act_mig": 59,   # Migrations
            "cpo_u": 72,     # YoY CPO Units
            "cpo_r": 74,     # YoY CPO Rev
            "acc_u": 92,     # YoY Accessory Volume
            "acc_r": 93,     # YOY Accessory Revenue
            "bundle": 99,    # YoY Protection Bundle
            "rep_oow_u": 108,# YoY WI # Repairs
            "rep_oow_r": 109,# YoY WI Revenue
            "rep_ins_u": 119,# YoY Insurance Volume
            "rep_ins_r": 120 # YoY Insurance Revenue
        }
    },
    {
        "source_sheet": "Nov 26 MTD",
        "target_period_label": "Nov 25",
        "header_row_idx": 4, # 0-indexed (row 5)
        "start_row_idx": 5,  # 0-indexed (row 6)
        "store_num_idx": 0,
        "store_name_idx": 1,
        "cols": {
            "rev": 24,       # YoY Total GroRev
            "sales": 23,     # YoY Sales Vol
            "traffic": 9,    # Traffic Vol YoY
            "act_new": 68,   # New Act YoY
            "act_mig": 78,   # Total Mig YoY
            "cpo_u": 108,    # YoY CPO Units
            "cpo_r": 110,    # YoY CPO Rev
            "acc_u": 128,    # YoY Acc Vol
            "acc_r": 129,    # YOY Acc Rev
            "bundle": 136,   # YoY Protection Bundle
            "rep_oow_u": 148,# YoY WI # Repairs
            "rep_oow_r": 149,# YoY WI Revenue
            "rep_ins_u": 162,# Part/Ins Vol YoY
            "rep_ins_r": 163 # Part/Ins Rev YoY
        }
    }
]

def run_embedded_yoy_ingestion():
    print("=" * 65)
    print("INGESTING EMBEDDED 2025 YoY HISTORICAL BASELINE")
    print("=" * 65)

    # 1. Fetch periods and locations
    periods = {p['label']: p for p in supabase.table('scorecard_periods').select('*').execute().data}
    locations_list = supabase.table('locations').select('*').execute().data
    num_to_loc = {l['store_number']: l for l in locations_list if l.get('store_number')}
    name_to_loc = {}
    for l in locations_list:
        n1 = normalize_store_name(l.get('name'))
        n2 = normalize_store_name(l.get('short_name'))
        if n1: name_to_loc[n1] = l
        if n2: name_to_loc[n2] = l

    print(f"Loaded {len(locations_list)} locations and {len(periods)} periods from Supabase.\n")

    print(f"Loading workbook: {EXCEL_PATH}...")
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True, read_only=True)

    total_upserted = 0

    for cfg in YOY_CONFIGS:
        sheet_name = cfg["source_sheet"]
        target_label = cfg["target_period_label"]
        period = periods.get(target_label)
        if not period:
            print(f"[ERROR] Target period '{target_label}' not found in database!")
            continue

        target_period_id = period['id']
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        c_map = cfg["cols"]

        print(f"\nProcessing sheet '{sheet_name}' -> target period '{target_label}' ({target_period_id})...")

        records_to_upsert = []
        tot_rev = 0.0

        for r_idx in range(cfg["start_row_idx"], len(rows)):
            r = rows[r_idx]
            raw_s = r[cfg["store_num_idx"]]
            raw_n = r[cfg["store_name_idx"]]

            if raw_s is None and raw_n is None:
                continue
            if str(raw_s).strip().upper() in ['AVG', 'TOTAL', 'SUBTOTAL', 'NONE', '', 'DAY #', '# DAYS IN THE MONTH']:
                continue
            if str(raw_n).strip().upper() in ['AVG', 'TOTAL', 'SUBTOTAL', '']:
                continue

            # Identify location
            st_num = extract_store_num(raw_s)
            st_name = str(raw_n or "").strip()
            norm_n = normalize_store_name(st_name)

            loc = None
            if norm_n and norm_n in name_to_loc:
                loc = name_to_loc[norm_n]
            elif st_num and st_num in num_to_loc:
                loc = num_to_loc[st_num]

            if not loc:
                print(f"  [WARN] Store not matched: raw_num={raw_s}, raw_name={raw_n}")
                continue

            # Extract YoY values
            def get_v(col_k, def_v=0.0):
                c_idx = c_map.get(col_k)
                if c_idx is None or c_idx >= len(r):
                    return def_v
                return clean_num(r[c_idx], default=def_v)

            rev = get_v("rev")
            sales = int(get_v("sales", 0))
            traffic = int(get_v("traffic", 0))
            act_new = int(get_v("act_new", 0))
            act_mig = int(get_v("act_mig", 0))
            act_tot = act_new + act_mig
            cpo_u = int(get_v("cpo_u", 0))
            cpo_r = get_v("cpo_r", 0.0)
            acc_u = int(get_v("acc_u", 0))
            acc_r = get_v("acc_r", 0.0)
            bundle = int(get_v("bundle", 0))
            oow_u = int(get_v("rep_oow_u", 0))
            oow_r = get_v("rep_oow_r", 0.0)
            ins_u = int(get_v("rep_ins_u", 0))
            ins_r = get_v("rep_ins_r", 0.0)

            # Skip rows where there is absolutely no YoY data recorded (e.g. all zeros/nulls)
            if rev == 0 and sales == 0 and traffic == 0 and act_tot == 0 and cpo_u == 0:
                continue

            asp = round(rev / sales, 2) if sales > 0 else 0.0
            tot_rev += rev

            record = {
                "location_id": loc["id"],
                "period_id": target_period_id,
                "gross_revenue_actual": round(rev, 2),
                "sales_volume": sales,
                "asp": asp,
                "activations_total": act_tot,
                "activations_new": act_new,
                "activations_migrations": act_mig,
                "activations_telus_post": 0,
                "activations_koodo_post": 0,
                "activations_koodo_pre": 0,
                "activations_renewals": 0,
                "cpo_units_actual": cpo_u,
                "cpo_revenue_actual": round(cpo_r, 2),
                "repairs_oow_volume": oow_u,
                "repairs_oow_revenue": round(oow_r, 2),
                "repairs_insurance_volume": ins_u,
                "repairs_insurance_revenue": round(ins_r, 2),
                "accessories_volume": acc_u,
                "accessories_revenue": round(acc_r, 2),
                "protection_bundles_volume": bundle,
                "foot_traffic_total": traffic,
                "conversion_rate_pct": round((sales / traffic * 100), 2) if traffic > 0 else 0.0
            }
            records_to_upsert.append(record)

        print(f"  Extracted {len(records_to_upsert)} valid store records for {target_label} | Total Revenue: ${tot_rev:,.2f}")

        # Batch upsert in chunks of 50
        BATCH_SIZE = 50
        for i in range(0, len(records_to_upsert), BATCH_SIZE):
            chunk = records_to_upsert[i:i + BATCH_SIZE]
            try:
                ups = supabase.table("monthly_kpis").upsert(
                    chunk,
                    on_conflict="location_id,period_id"
                ).execute()
                total_upserted += len(chunk)
            except Exception as e:
                print(f"  [ERROR] Upserting batch {i//BATCH_SIZE + 1}: {e}")

        print(f"  Successfully upserted {len(records_to_upsert)} records into {target_label}.")

    print("\n" + "=" * 65)
    print(f"ALL EMBEDDED YoY BASELINE DATA INGESTED ({total_upserted} records)")
    print("=" * 65)

if __name__ == "__main__":
    run_embedded_yoy_ingestion()

