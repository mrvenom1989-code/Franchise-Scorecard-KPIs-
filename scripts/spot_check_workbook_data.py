"""
Deterministic Spot-Check Script:
Compares random sample of stores across multiple periods in
'Updated Franchise Scorecard - Oct MTD EOD - 10-25-26.xlsx'
against records in Supabase PostgreSQL (monthly_kpis).
"""

import os
import random
from pathlib import Path
import openpyxl
from dotenv import load_dotenv
from supabase import create_client

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
EXCEL_PATH = BASE_DIR / "Updated Franchise Scorecard - Oct MTD EOD - 10-25-26.xlsx"

sb = create_client(SUPABASE_URL, SUPABASE_KEY)
wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True, read_only=True)

periods = {p['label']: p['id'] for p in sb.table('scorecard_periods').select('id, label').execute().data}
locations = {loc['store_number']: loc for loc in sb.table('locations').select('id, store_number, name').execute().data}

def clean_num(val):
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace('$', '').replace(',', '').replace('%', '').strip()
    try:
        return float(s)
    except ValueError:
        return 0.0

test_sheets = [
    ('Oct 26 MTD', 'Oct 26 MTD'),
    ('Aug 26', 'Aug 26'),
    ('May 26', 'May 26'),
    ('Mar 26', 'Mar 26'),
    ('Dec 2025 ', 'Dec 2025'),
    ('Sept 2025', 'Sept 2025')
]

def run_spot_check():
    total_checked = 0
    total_matched = 0
    discrepancies = []

    for sheet_name, period_label in test_sheets:
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(max_row=70, values_only=True))

        header_r_idx = None
        store_c_idx = None
        for r_idx in range(4, min(10, len(rows))):
            for c_idx, val in enumerate(rows[r_idx]):
                if val and 'store #' in str(val).lower():
                    header_r_idx = r_idx
                    store_c_idx = c_idx
                    break
            if header_r_idx is not None:
                break

        if header_r_idx is None:
            continue

        cat_r = max(0, header_r_idx - 4)
        sub_r = max(0, header_r_idx - 3)
        metric_r = rows[header_r_idx]
        cat_row = rows[cat_r]
        sub_row = rows[sub_r]

        col_map = {}
        curr_cat, curr_sub = "", ""
        for idx in range(len(metric_r)):
            if idx < len(cat_row) and cat_row[idx]: curr_cat = str(cat_row[idx]).strip()
            if idx < len(sub_row) and sub_row[idx]: curr_sub = str(sub_row[idx]).strip()
            m = str(metric_r[idx]).strip() if metric_r[idx] else ""
            full = f"{curr_cat}::{curr_sub}::{m}".lower()

            if 'total gross revenue mtd' in m.lower() or ('gross revenue' in m.lower() and 'mtd' in full and 'mom' not in full and 'yoy' not in full):
                if 'revenue' not in col_map: col_map['revenue'] = idx
            if m.lower() == 'total sales' and 'mom' not in full and 'yoy' not in full:
                if 'sales' not in col_map: col_map['sales'] = idx
            if 'total new activations' in m.lower() and 'mom' not in full and 'yoy' not in full:
                col_map['act_new'] = idx
            if m.lower() == 'migrations' and 'mom' not in full and 'yoy' not in full and '%' not in m:
                col_map['act_mig'] = idx
            if 'cpo units' in m.lower() and 'proj' not in m.lower() and 'target' not in m.lower() and 'mom' not in full and 'yoy' not in full:
                if 'cpo_units' not in col_map: col_map['cpo_units'] = idx
            if 'total traffic mtd' in m.lower() and 'mom' not in full and 'yoy' not in full:
                if 'traffic' not in col_map: col_map['traffic'] = idx

        period_id = periods.get(period_label)
        if not period_id:
            continue

        valid_store_rows = []
        for r_idx in range(header_r_idx + 1, len(rows)):
            st_val = rows[r_idx][store_c_idx]
            if st_val is not None:
                try:
                    st_num = int(float(st_val))
                    if st_num in locations:
                        valid_store_rows.append((st_num, rows[r_idx]))
                except (ValueError, TypeError): pass

        if not valid_store_rows:
            continue

        sampled = random.sample(valid_store_rows, min(3, len(valid_store_rows)))
        print(f"\n--- {period_label} ({sheet_name}) ---")
        for st_num, row_data in sampled:
            loc = locations[st_num]
            db_res = sb.table('monthly_kpis').select('*').eq('location_id', loc['id']).eq('period_id', period_id).execute().data
            if not db_res:
                continue
            db_row = db_res[0]

            checks = []
            if 'revenue' in col_map:
                xl_v = clean_num(row_data[col_map['revenue']])
                db_v = float(db_row.get('gross_revenue_actual') or 0.0)
                checks.append(('Revenue', xl_v, db_v, abs(xl_v - db_v) < 1.0))
            if 'sales' in col_map:
                xl_v = clean_num(row_data[col_map['sales']])
                db_v = float(db_row.get('sales_volume') or 0.0)
                checks.append(('Sales', xl_v, db_v, abs(xl_v - db_v) < 1.0))
            if 'act_new' in col_map and 'act_mig' in col_map:
                xl_v = clean_num(row_data[col_map['act_new']]) + clean_num(row_data[col_map['act_mig']])
                db_v = float(db_row.get('activations_total') or 0.0)
                checks.append(('Activations', xl_v, db_v, abs(xl_v - db_v) < 1.0))
            if 'traffic' in col_map:
                xl_v = clean_num(row_data[col_map['traffic']])
                db_v = float(db_row.get('foot_traffic_total') or 0.0)
                checks.append(('Traffic', xl_v, db_v, abs(xl_v - db_v) < 1.0))

            total_checked += len(checks)
            total_matched += sum(1 for c in checks if c[3])
            matched_names = [c[0] for c in checks if c[3]]
            unmatched = [c for c in checks if not c[3]]

            if not unmatched:
                print(f"  Store #{st_num} {loc['name'][:25]}: 100% MATCH ({', '.join(matched_names)})")
            else:
                for name, xl_v, db_v, _ in unmatched:
                    print(f"  [DISCREPANCY] Store #{st_num} {name}: Excel={xl_v} vs DB={db_v}")
                    discrepancies.append((period_label, st_num, name, xl_v, db_v))

    print(f"\nAudit complete: {total_matched}/{total_checked} checks matched ({(total_matched/total_checked*100) if total_checked else 0:.1f}%).")

if __name__ == "__main__":
    run_spot_check()
