"""
Backfill January 2026 Foot Traffic and Conversion Rates.

Root Cause:
Corporate omitted the Traffic section entirely from the 'Jan 26' sheet in
'Updated Franchise Scorecard - Oct MTD EOD - 10-25-26.xlsx' due to Week 2 sensor error.
However, sheet 'Feb 26' Column 7 ('Total Traffic MOM') contains the finalized
January 2026 foot traffic data store-by-store (33,556 total network visits).

This script reads Feb 26 Col 7, maps to locations, and updates monthly_kpis in Supabase:
- foot_traffic_total
- foot_traffic_daily_avg
- conversion_rate_pct
"""

import os
from pathlib import Path
import openpyxl
from dotenv import load_dotenv
from supabase import create_client

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
EXCEL_PATH = BASE_DIR / "Updated Franchise Scorecard - Oct MTD EOD - 10-25-26.xlsx"

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env")

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

def run_backfill():
    print(f"Loading workbook from {EXCEL_PATH}...")
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True, read_only=True)
    if 'Feb 26' not in wb.sheetnames:
        raise ValueError("Sheet 'Feb 26' not found in workbook")
    
    ws = wb['Feb 26']
    locations = {loc['store_number']: loc['id'] for loc in sb.table('locations').select('id, store_number').execute().data}
    
    p_resp = sb.table('scorecard_periods').select('id').eq('label', 'Jan 26').execute()
    if not p_resp.data:
        raise ValueError("Period 'Jan 26' not found in scorecard_periods")
    jan26_period_id = p_resp.data[0]['id']

    existing_rows = sb.table('monthly_kpis').select('id, location_id, sales_volume').eq('period_id', jan26_period_id).execute().data
    existing_by_loc = {r['location_id']: r for r in existing_rows}

    updated_count = 0
    total_traffic_sum = 0
    for r in ws.iter_rows(min_row=9, max_row=60, values_only=True):
        st_val = r[1]
        traffic_mom = r[6]  # Col 7 is Total Traffic MOM (Jan 26 traffic)
        if st_val is not None and traffic_mom is not None:
            try:
                st_num = int(float(st_val))
                trf = int(round(float(traffic_mom)))
                if st_num in locations:
                    lid = locations[st_num]
                    if lid in existing_by_loc:
                        kpi_id = existing_by_loc[lid]['id']
                        vol = existing_by_loc[lid].get('sales_volume') or 0
                        conv = round((vol / trf * 100), 2) if trf > 0 else 0.0
                        daily_avg = round(trf / 31.0, 2)
                        sb.table('monthly_kpis').update({
                            'foot_traffic_total': trf,
                            'foot_traffic_daily_avg': daily_avg,
                            'conversion_rate_pct': conv
                        }).eq('id', kpi_id).execute()
                        updated_count += 1
                        total_traffic_sum += trf
            except Exception as e:
                print(f"  [ERROR] Store {st_val}: {e}")

    print(f"Successfully backfilled Jan 26 foot traffic for {updated_count} stores.")
    print(f"Total network traffic recorded: {total_traffic_sum:,} visits.")

if __name__ == "__main__":
    run_backfill()
