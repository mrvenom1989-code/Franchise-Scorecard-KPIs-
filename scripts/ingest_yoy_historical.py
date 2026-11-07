import os
import sys
import openpyxl
from datetime import date
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from config import supabase
from ingest_scorecard import normalize_store_name, extract_store_num, clean_num, normalize_region

EXCEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "Updated Franchise Scorecard - Oct MTD EOD - 10-25-26.xlsx"
)

PERIODS_CONFIG = [
    {
        "sheet": "Jan 26", "label": "Jan 2025", "start_date": "2025-01-01", "end_date": "2025-01-31",
        "store_c": 2, "loc_c": 3, "reg_c": 4, "header_r": 8, "total_r": 7,
        "cols": {
            "rev": 15, "vol": 14, "asp": 16, "act": 44, "cpo_u": 74, "cpo_r": 76,
            "oow_v": 112, "oow_r": 113, "ins_v": 125, "ins_r": 126, "trf": None
        }
    },
    {
        "sheet": "Feb 26", "label": "Feb 2025", "start_date": "2025-02-01", "end_date": "2025-02-28",
        "store_c": 2, "loc_c": 3, "reg_c": 4, "header_r": 8, "total_r": 7,
        "cols": {
            "rev": 21, "vol": 20, "asp": 22, "act": 44, "cpo_u": 68, "cpo_r": 70,
            "oow_v": 107, "oow_r": 108, "ins_v": 120, "ins_r": 121, "trf": 9
        }
    },
    {
        "sheet": "Mar 26", "label": "Mar 2025", "start_date": "2025-03-01", "end_date": "2025-03-31",
        "store_c": 2, "loc_c": 3, "reg_c": 4, "header_r": 8, "total_r": 7,
        "cols": {
            "rev": 21, "vol": 20, "asp": 22, "act": 43, "cpo_u": 66, "cpo_r": 68,
            "oow_v": 105, "oow_r": 106, "ins_v": 118, "ins_r": 119, "trf": 9
        }
    },
    {
        "sheet": "April 26", "label": "April 2025", "start_date": "2025-04-01", "end_date": "2025-04-30",
        "store_c": 4, "loc_c": 5, "reg_c": 6, "header_r": 7, "total_r": 6,
        "cols": {
            "rev": 26, "vol": 25, "asp": 27, "act": 55, "cpo_u": 89, "cpo_r": 91,
            "oow_v": 135, "oow_r": 136, "ins_v": 150, "ins_r": 151, "trf": 12
        }
    },
    {
        "sheet": "May 26", "label": "May 2025", "start_date": "2025-05-01", "end_date": "2025-05-31",
        "store_c": 4, "loc_c": 5, "reg_c": 6, "header_r": 8, "total_r": 7,
        "cols": {
            "rev": 26, "vol": 25, "asp": 27, "act": 57, "cpo_u": 91, "cpo_r": 93,
            "oow_v": 136, "oow_r": 137, "ins_v": 151, "ins_r": 152, "trf": 12
        }
    },
    {
        "sheet": "June 26", "label": "June 2025", "start_date": "2025-06-01", "end_date": "2025-06-30",
        "store_c": 4, "loc_c": 5, "reg_c": 6, "header_r": 8, "total_r": 7,
        "cols": {
            "rev": 26, "vol": 25, "asp": 27, "act": 57, "cpo_u": 91, "cpo_r": 93,
            "oow_v": 136, "oow_r": 137, "ins_v": 151, "ins_r": 152, "trf": 12
        }
    },
    {
        "sheet": "July 26", "label": "July 2025", "start_date": "2025-07-01", "end_date": "2025-07-31",
        "store_c": 4, "loc_c": 5, "reg_c": 6, "header_r": 8, "total_r": 7,
        "cols": {
            "rev": 23, "vol": 22, "asp": 24, "act": 46, "cpo_u": 76, "cpo_r": 78,
            "oow_v": 116, "oow_r": 117, "ins_v": 129, "ins_r": 130, "trf": 11
        }
    },
    {
        "sheet": "Aug 26", "label": "Aug 2025", "start_date": "2025-08-01", "end_date": "2025-08-31",
        "store_c": 4, "loc_c": 5, "reg_c": 6, "header_r": 8, "total_r": 7,
        "cols": {
            "rev": 26, "vol": 25, "asp": 27, "act": 57, "cpo_u": 91, "cpo_r": 93,
            "oow_v": 136, "oow_r": 137, "ins_v": 151, "ins_r": 152, "trf": 12
        }
    }
]

def run_ingestion():
    print("=" * 60)
    print("INGESTING HISTORICAL 2025 DATA (Jan 2025 - Aug 2025)")
    print("=" * 60)

    # 1. Fetch existing locations & periods from Supabase
    loc_resp = supabase.table("locations").select("id, store_number, name, short_name, region").execute()
    locations_list = loc_resp.data or []
    num_to_loc = {row["store_number"]: row for row in locations_list}
    name_to_loc = {}
    for row in locations_list:
        n1 = normalize_store_name(row["name"])
        n2 = normalize_store_name(row.get("short_name"))
        if n1:
            name_to_loc[n1] = row
        if n2:
            name_to_loc[n2] = row
    print(f"Loaded {len(locations_list)} existing locations from Supabase.")

    # 2. Ensure 2025 periods exist in scorecard_periods
    period_resp = supabase.table("scorecard_periods").select("id, label, start_date, end_date").execute()
    existing_periods = {p["label"]: p for p in (period_resp.data or [])}
    
    period_map = {}
    for pcfg in PERIODS_CONFIG:
        lbl = pcfg["label"]
        if lbl in existing_periods:
            period_map[lbl] = existing_periods[lbl]["id"]
            print(f"  Period '{lbl}' already exists (id: {period_map[lbl]})")
        else:
            ins = supabase.table("scorecard_periods").insert({
                "label": lbl,
                "start_date": pcfg["start_date"],
                "end_date": pcfg["end_date"],
                "period_type": "FULL_MONTH"
            }).execute()
            if ins.data:
                period_map[lbl] = ins.data[0]["id"]
                print(f"  [CREATED] Period '{lbl}' ({pcfg['start_date']} to {pcfg['end_date']}) id: {period_map[lbl]}")
            else:
                print(f"  [ERROR] Failed to create period '{lbl}'")

    # 3. Load Excel workbook
    print(f"\nLoading Excel file: {EXCEL_PATH}...")
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)

    total_inserted = 0

    # 4. Iterate over each period config and extract store records
    for pcfg in PERIODS_CONFIG:
        sname = pcfg["sheet"]
        lbl = pcfg["label"]
        pid = period_map.get(lbl)
        if not pid:
            print(f"[SKIP] Missing period id for {lbl}")
            continue

        ws = wb[sname]
        c_map = pcfg["cols"]
        header_r = pcfg["header_r"]
        store_c = pcfg["store_c"]
        loc_c = pcfg["loc_c"]
        reg_c = pcfg.get("reg_c", loc_c + 1)

        records_to_upsert = []
        tot_rev = 0.0

        for r in range(header_r + 1, ws.max_row + 1):
            s_val = ws.cell(r, store_c).value
            l_val = ws.cell(r, loc_c).value
            reg_val = ws.cell(r, reg_c).value if reg_c else None

            if s_val is None and l_val is None:
                continue
            if str(s_val).strip().upper() in ['AVG', 'TOTAL', 'SUBTOTAL', 'NONE', '']:
                continue

            raw_num = extract_store_num(s_val)
            raw_name = str(l_val or "").strip()
            norm_n = normalize_store_name(raw_name)

            # Match location
            matched_loc = None
            if norm_n and norm_n in name_to_loc:
                matched_loc = name_to_loc[norm_n]
            elif raw_num and raw_num in num_to_loc:
                matched_loc = num_to_loc[raw_num]

            # Auto-provision if needed
            if not matched_loc and (norm_n or raw_num):
                try:
                    clean_name = raw_name.split("(")[0].strip() or f"Store {raw_num}"
                    new_num = raw_num or 999
                    new_loc = supabase.table("locations").insert({
                        "store_number": new_num,
                        "name": f"Mobile Klinik {clean_name}",
                        "short_name": clean_name,
                        "region": normalize_region(reg_val),
                        "store_type": "franchise",
                        "is_active": True
                    }).execute()
                    if new_loc.data:
                        matched_loc = new_loc.data[0]
                        num_to_loc[matched_loc["store_number"]] = matched_loc
                        name_to_loc[normalize_store_name(matched_loc["name"])] = matched_loc
                        name_to_loc[normalize_store_name(clean_name)] = matched_loc
                        print(f"    [AUTO-PROVISION] Store #{new_num} - {clean_name}")
                except Exception as e:
                    print(f"    [WARN] Auto-provision failed for {raw_name} (#{raw_num}): {e}")

            if not matched_loc:
                continue

            def get_val(c_idx, def_val=0.0):
                if c_idx is None:
                    return def_val
                return clean_num(ws.cell(r, c_idx).value, default=def_val)

            rev = get_val(c_map["rev"])
            vol = int(get_val(c_map["vol"], 0))
            asp = get_val(c_map["asp"], 0.0)
            act = int(get_val(c_map["act"], 0))
            cpo_u = int(get_val(c_map["cpo_u"], 0))
            cpo_r = get_val(c_map["cpo_r"], 0.0)
            oow_v = int(get_val(c_map["oow_v"], 0))
            oow_r = get_val(c_map["oow_r"], 0.0)
            ins_v = int(get_val(c_map["ins_v"], 0))
            ins_r = get_val(c_map["ins_r"], 0.0)
            trf = int(get_val(c_map["trf"], 0))

            tot_rev += rev

            records_to_upsert.append({
                "location_id": matched_loc["id"],
                "period_id": pid,
                "gross_revenue_actual": round(rev, 2),
                "sales_volume": vol,
                "asp": round(asp, 2) if asp else (round(rev / vol, 2) if vol > 0 else 0.0),
                "activations_total": act,
                "activations_new": act,
                "activations_migrations": 0,
                "activations_telus_post": 0,
                "activations_koodo_post": 0,
                "activations_koodo_pre": 0,
                "activations_renewals": 0,
                "cpo_units_actual": cpo_u,
                "cpo_revenue_actual": round(cpo_r, 2),
                "repairs_oow_volume": oow_v,
                "repairs_oow_revenue": round(oow_r, 2),
                "repairs_insurance_volume": ins_v,
                "repairs_insurance_revenue": round(ins_r, 2),
                "accessories_volume": 0,
                "accessories_revenue": 0.0,
                "protection_bundles_volume": 0,
                "foot_traffic_total": trf
            })

        # Batch upsert into Supabase
        if records_to_upsert:
            try:
                ups_res = supabase.table("monthly_kpis").upsert(
                    records_to_upsert,
                    on_conflict="location_id,period_id"
                ).execute()
                count = len(ups_res.data or records_to_upsert)
                total_inserted += count
                print(f"[{lbl:10}] Successfully upserted {count:2d} store records | Total Rev: ${tot_rev:11,.2f}")
            except Exception as e:
                print(f"[{lbl:10}] ERROR upserting into monthly_kpis: {e}")

    print("\n" + "=" * 60)
    print(f"INGESTION COMPLETE: {total_inserted} total records upserted across 8 periods!")
    print("=" * 60)

if __name__ == "__main__":
    run_ingestion()
