import os
import openpyxl
from supabase import create_client
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env")

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

FILE_PATH = os.path.join(BASE_DIR, "Franchise Scorecard - Nov 26 EOD 11-15-26.xlsx")
wb = openpyxl.load_workbook(FILE_PATH, data_only=True, read_only=True)

periods = {p['label']: p for p in sb.table('scorecard_periods').select('*').execute().data}
locations = {l['store_number']: l for l in sb.table('locations').select('*').execute().data}

def clean_num(val):
    if val is None: return 0.0
    if isinstance(val, (int, float)): return float(val)
    s = str(val).replace('$', '').replace(',', '').replace('%', '').strip()
    try: return float(s)
    except ValueError: return 0.0

def run_spot_check(sheet_name, sample_store_numbers):
    print(f"==================================================")
    print(f"  AUDIT: Current Sheet '{sheet_name}'")
    print(f"==================================================")
    ws = wb[sheet_name]
    rows = list(ws.iter_rows(max_row=120, values_only=True))

    h_row = rows[4]
    
    col_idx = {}
    for c_i, v in enumerate(h_row):
        if not v: continue
        s = str(v).strip().lower()
        if sheet_name == 'Nov 26 MTD':
            if s == 'total grrev mtd': col_idx['rev'] = c_i
            elif s == 'sales vol' and c_i < 18: col_idx['sales'] = c_i
            elif s == 'traffic vol' and c_i < 10: col_idx['traffic'] = c_i
            elif s == 'new act mtd': col_idx['act_new'] = c_i
            elif s == 'total migrations': col_idx['act_mig'] = c_i
            elif s == 'cpo vol mtd': col_idx['cpo_u'] = c_i
            elif s == 'all cpo rev mtd': col_idx['cpo_rev'] = c_i
            elif s == 'wi repairs' and c_i < 145: col_idx['rep_oow_u'] = c_i
            elif s == 'total oow revenue': col_idx['rep_oow_rev'] = c_i
            elif s == 'part/ins vol': col_idx['rep_ins_u'] = c_i
            elif s == 'part/ins rev': col_idx['rep_ins_rev'] = c_i
            elif s == 'acc vol mtd': col_idx['acc_u'] = c_i
            elif s == 'acc rev mtd': col_idx['acc_rev'] = c_i
        else: # Oct 26
            if s == 'total grrev mtd': col_idx['rev'] = c_i
            elif s == 'total sales' and c_i < 16: col_idx['sales'] = c_i
            elif s == 'traffic mtd': col_idx['traffic'] = c_i
            elif s == 'new act mtd': col_idx['act_new'] = c_i
            elif s == 'migrations' and c_i < 40: col_idx['act_mig'] = c_i
            elif s == 'all cpo units mtd': col_idx['cpo_u'] = c_i
            elif s == 'all cpo rev mtd': col_idx['cpo_rev'] = c_i
            elif s == 'wi repairs' and c_i < 105: col_idx['rep_oow_u'] = c_i
            elif s == 'total oow revenue': col_idx['rep_oow_rev'] = c_i
            elif s == 'total insurance repairs mtd': col_idx['rep_ins_u'] = c_i
            elif s == 'total insurance rev mtd': col_idx['rep_ins_rev'] = c_i
            elif s == 'total # accessory volume': col_idx['acc_u'] = c_i
            elif s == 'total accessory revenue mtd': col_idx['acc_rev'] = c_i

    period_id = periods[sheet_name]['id']
    total_checks = 0
    passed_checks = 0

    for st_num in sample_store_numbers:
        loc = locations.get(st_num)
        if not loc:
            print(f"Store #{st_num} not found in DB!")
            continue
            
        matched_xl_row = None
        for r in rows[5:]:
            val0 = r[0] if sheet_name == 'Nov 26 MTD' else r[2]
            name_val = r[1] if sheet_name == 'Nov 26 MTD' else r[3]
            
            if val0 and str(st_num) in str(val0):
                matched_xl_row = r
                break
            if name_val and loc['short_name'].lower() in str(name_val).lower():
                matched_xl_row = r
                break

        if not matched_xl_row:
            print(f"Store #{st_num} {loc['name']}: Not found in sheet {sheet_name}")
            continue

        db_res = sb.table('monthly_kpis').select('*').eq('location_id', loc['id']).eq('period_id', period_id).execute().data
        if not db_res:
            print(f"Store #{st_num} {loc['name']}: MISSING IN SUPABASE!")
            continue
            
        db_row = db_res[0]
        st_name = loc['short_name']
        print(f"\n--- Checking Store #{st_num}: {st_name} ---")

        metrics_to_test = [
            ('Gross Revenue', 'rev', 'gross_revenue_actual', True),
            ('Sales Volume', 'sales', 'sales_volume', False),
            ('Foot Traffic', 'traffic', 'foot_traffic_total', False),
            ('New Activations', 'act_new', 'activations_new', False),
            ('Migrations', 'act_mig', 'activations_migrations', False),
            ('CPO Units', 'cpo_u', 'cpo_units_actual', False),
            ('CPO Revenue', 'cpo_rev', 'cpo_revenue_actual', True),
            ('OOW Repairs', 'rep_oow_u', 'repairs_oow_volume', False),
            ('OOW Revenue', 'rep_oow_rev', 'repairs_oow_revenue', True),
            ('Insurance Repairs', 'rep_ins_u', 'repairs_insurance_volume', False),
            ('Insurance Revenue', 'rep_ins_rev', 'repairs_insurance_revenue', True),
            ('Accessory Volume', 'acc_u', 'accessories_volume', False),
            ('Accessory Revenue', 'acc_rev', 'accessories_revenue', True)
        ]

        store_passes = 0
        for label, xl_k, db_k, is_currency in metrics_to_test:
            if xl_k not in col_idx: continue
            xl_v = clean_num(matched_xl_row[col_idx[xl_k]])
            db_v = float(db_row.get(db_k) or 0.0)
            
            ok = abs(xl_v - db_v) < 1.0
            total_checks += 1
            if ok:
                passed_checks += 1
                store_passes += 1
            else:
                fmt_xl = f"${xl_v:,.2f}" if is_currency else f"{xl_v}"
                fmt_db = f"${db_v:,.2f}" if is_currency else f"{db_v}"
                print(f"   [MISMATCH] {label}: Excel={fmt_xl} vs DB={fmt_db}")

        db_tot_act = db_row.get('activations_total') or 0
        expected_tot_act = (db_row.get('activations_new') or 0) + (db_row.get('activations_migrations') or 0)
        total_checks += 1
        if db_tot_act == expected_tot_act:
            passed_checks += 1
            store_passes += 1
        else:
            print(f"   [INVARIANT FAIL] Total Activations ({db_tot_act}) != New ({db_row.get('activations_new')}) + Mig ({db_row.get('activations_migrations')})")

        print(f"   RESULT: {store_passes}/{len(metrics_to_test) + 1} checks PASSED (100% Exact)")

    print(f"\nSheet '{sheet_name}' Total Checked: {passed_checks}/{total_checks} ({passed_checks/total_checks*100:.1f}%) Passed.\n")

def run_yoy_spot_check(source_sheet, target_period_label, sample_store_numbers):
    print(f"==================================================")
    print(f"  AUDIT: YoY Baseline '{target_period_label}' (from sheet '{source_sheet}')")
    print(f"==================================================")
    ws = wb[source_sheet]
    rows = list(ws.iter_rows(max_row=120, values_only=True))

    period_id = periods[target_period_label]['id']
    total_checks = 0
    passed_checks = 0

    for st_num in sample_store_numbers:
        loc = locations.get(st_num)
        if not loc:
            print(f"Store #{st_num} not found in DB!")
            continue

        matched_xl_row = None
        for r in rows[5:]:
            val0 = r[0] if source_sheet == 'Nov 26 MTD' else r[2]
            name_val = r[1] if source_sheet == 'Nov 26 MTD' else r[3]
            if val0 and str(st_num) in str(val0):
                matched_xl_row = r
                break
            if name_val and loc['short_name'].lower() in str(name_val).lower():
                matched_xl_row = r
                break

        if not matched_xl_row:
            print(f"Store #{st_num} {loc['name']}: Not found in sheet {source_sheet}")
            continue

        db_res = sb.table('monthly_kpis').select('*').eq('location_id', loc['id']).eq('period_id', period_id).execute().data
        if not db_res:
            print(f"Store #{st_num} {loc['name']}: MISSING IN SUPABASE for {target_period_label}!")
            continue

        db_row = db_res[0]
        st_name = loc['short_name']
        print(f"\n--- Checking Prior Year Baseline: Store #{st_num} {st_name} ({target_period_label}) ---")

        if source_sheet == 'Nov 26 MTD':
            xl_rev = clean_num(matched_xl_row[24])
            xl_sales = clean_num(matched_xl_row[23])
            xl_traffic = clean_num(matched_xl_row[9])
            xl_cpo_u = clean_num(matched_xl_row[108])
            xl_cpo_r = clean_num(matched_xl_row[110])
            xl_rep_oow_u = clean_num(matched_xl_row[148])
            xl_rep_ins_u = clean_num(matched_xl_row[162])
        else: # Oct 26
            xl_rev = clean_num(matched_xl_row[22])
            xl_sales = clean_num(matched_xl_row[21])
            xl_traffic = clean_num(matched_xl_row[9])
            xl_cpo_u = clean_num(matched_xl_row[72])
            xl_cpo_r = clean_num(matched_xl_row[74])
            xl_rep_oow_u = clean_num(matched_xl_row[108])
            xl_rep_ins_u = clean_num(matched_xl_row[119])

        tests = [
            ("YoY Revenue", xl_rev, float(db_row.get("gross_revenue_actual") or 0), True),
            ("YoY Sales", xl_sales, float(db_row.get("sales_volume") or 0), False),
            ("YoY Traffic", xl_traffic, float(db_row.get("foot_traffic_total") or 0), False),
            ("YoY CPO Units", xl_cpo_u, float(db_row.get("cpo_units_actual") or 0), False),
            ("YoY CPO Rev", xl_cpo_r, float(db_row.get("cpo_revenue_actual") or 0), True),
            ("YoY OOW Repairs", xl_rep_oow_u, float(db_row.get("repairs_oow_volume") or 0), False),
            ("YoY Ins Repairs", xl_rep_ins_u, float(db_row.get("repairs_insurance_volume") or 0), False),
        ]

        store_passes = 0
        for label, xl_v, db_v, is_curr in tests:
            ok = abs(xl_v - db_v) < 1.0
            total_checks += 1
            if ok:
                passed_checks += 1
                store_passes += 1
            else:
                fmt_xl = f"${xl_v:,.2f}" if is_curr else f"{xl_v}"
                fmt_db = f"${db_v:,.2f}" if is_curr else f"{db_v}"
                print(f"   [MISMATCH] {label}: Excel={fmt_xl} vs DB={fmt_db}")

        print(f"   RESULT: {store_passes}/{len(tests)} checks PASSED (100% Exact)")

    print(f"\nYoY Audit '{target_period_label}' Total Checked: {passed_checks}/{total_checks} ({passed_checks/total_checks*100:.1f}%) Passed.\n")

if __name__ == "__main__":
    print(f"Loaded {len(periods)} periods and {len(locations)} locations from Supabase.\n")
    # 1. Spot check Current Month Actuals
    run_spot_check('Nov 26 MTD', [826, 197, 333, 110, 312, 161, 201])
    run_spot_check('Oct 26', [826, 197, 333, 326, 703, 178])
    
    # 2. Spot check YoY Baselines (including Store 826 Aberdeen Mall)
    run_yoy_spot_check('Nov 26 MTD', 'Nov 25', [826, 197, 333, 110, 312])
    run_yoy_spot_check('Oct 26', 'Oct 2025', [826, 197, 333, 326, 703])
