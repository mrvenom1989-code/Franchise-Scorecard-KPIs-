import os
import openpyxl
from supabase import create_client
from dotenv import load_dotenv

BASE_DIR = r"C:\Users\aquri\Antigravity\Franchise-Scorecard-KPIs"
load_dotenv(os.path.join(BASE_DIR, ".env"))

sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
wb = openpyxl.load_workbook(os.path.join(BASE_DIR, "Franchise Scorecard - Nov 26 EOD 11-15-26.xlsx"), data_only=True, read_only=True)

periods = {p['label']: p for p in sb.table('scorecard_periods').select('*').execute().data}
locations_list = sb.table('locations').select('*').execute().data
num_to_loc = {l['store_number']: l for l in locations_list if l.get('store_number')}
name_to_loc = {}

def norm_name(s):
    if not s: return ""
    import re
    s = re.sub(r'#\d+', '', str(s))
    s = re.sub(r'F\d+', '', str(s), flags=re.I)
    s = s.replace('Mobile Klinik', '').replace('MK', '')
    s = re.sub(r'\s*\([^)]*\)', '', s)
    s = re.sub(r'[^a-zA-Z0-9]', '', s).lower()
    return s

for l in locations_list:
    n1 = norm_name(l.get('name'))
    n2 = norm_name(l.get('short_name'))
    if n1: name_to_loc[n1] = l
    if n2: name_to_loc[n2] = l

def clean_num(val, default=0.0):
    if val is None: return default
    if isinstance(val, (int, float)): return float(val)
    s = str(val).replace('$', '').replace(',', '').replace('%', '').strip()
    try: return float(s)
    except ValueError: return default

def extract_store_num(val):
    if not val: return None
    import re
    m = re.search(r'\d+', str(val))
    return int(m.group(0)) if m else None

# Sheet -> (target_label, store_col, name_col, start_row, acc_vol_col, acc_rev_col, bundle_col)
CONFIGS = [
    ('Jan 26', 'Jan 2025', 1, 2, 9, 93, 94, 100),
    ('Feb 26', 'Feb 2025', 1, 2, 9, 88, 89, 95),
    ('Mar 26', 'Mar 2025', 1, 2, 9, 86, 87, 93),
    ('April 26', 'April 2025', 3, 4, 8, 112, 113, 120),
    ('May 26', 'May 2025', 3, 4, 9, 113, 114, 121),
    ('June 26', 'June 2025', 3, 4, 9, 113, 114, 121),
    ('July 26', 'July 2025', 3, 4, 9, 97, 98, 104),
    ('Aug 26', 'Aug 2025', 3, 4, 9, 113, 114, 121),
]

total_updated = 0

for s_name, target_label, store_c, name_c, start_r, acc_v_c, acc_r_c, bnd_c in CONFIGS:
    period = periods.get(target_label)
    if not period:
        print(f"Missing period {target_label}")
        continue
    pid = period['id']
    ws = wb[s_name]
    rows = list(ws.iter_rows(values_only=True))

    updates = []
    tot_rev = 0.0
    tot_vol = 0
    tot_bnd = 0

    for r_idx in range(start_r - 1, len(rows)):
        r = rows[r_idx]
        raw_s = r[store_c] if store_c < len(r) else None
        raw_n = r[name_c] if name_c < len(r) else None

        if raw_s is None and raw_n is None: continue
        if str(raw_s).strip().upper() in ['AVG', 'TOTAL', 'SUBTOTAL', 'NONE', '']: continue
        if str(raw_n).strip().upper() in ['AVG', 'TOTAL', 'SUBTOTAL', '']: continue

        st_num = extract_store_num(raw_s)
        st_name = str(raw_n or "").strip()
        n_name = norm_name(st_name)

        loc = None
        if n_name and n_name in name_to_loc:
            loc = name_to_loc[n_name]
        elif st_num and st_num in num_to_loc:
            loc = num_to_loc[st_num]

        if not loc: continue

        acc_v = int(clean_num(r[acc_v_c])) if acc_v_c < len(r) else 0
        acc_r = clean_num(r[acc_r_c]) if acc_r_c < len(r) else 0.0
        bnd = int(clean_num(r[bnd_c])) if bnd_c < len(r) else 0

        tot_rev += acc_r
        tot_vol += acc_v
        tot_bnd += bnd

        updates.append({
            "location_id": loc['id'],
            "period_id": pid,
            "accessories_volume": acc_v,
            "accessories_revenue": round(acc_r, 2),
            "protection_bundles_volume": bnd
        })

    print(f"Sheet '{s_name}' -> '{target_label}': {len(updates)} stores | Acc Rev=${tot_rev:,.2f} | Units={tot_vol} | Bundles={tot_bnd}")

    # Upsert updates into monthly_kpis in batches
    for u in updates:
        existing = sb.table('monthly_kpis').select('id').eq('location_id', u['location_id']).eq('period_id', u['period_id']).execute().data
        if existing:
            sb.table('monthly_kpis').update({
                'accessories_volume': u['accessories_volume'],
                'accessories_revenue': u['accessories_revenue'],
                'protection_bundles_volume': u['protection_bundles_volume']
            }).eq('id', existing[0]['id']).execute()
            total_updated += 1
        else:
            sb.table('monthly_kpis').insert({
                'location_id': u['location_id'],
                'period_id': u['period_id'],
                'gross_revenue_actual': 0.0,
                'sales_volume': 0,
                'accessories_volume': u['accessories_volume'],
                'accessories_revenue': u['accessories_revenue'],
                'protection_bundles_volume': u['protection_bundles_volume']
            }).execute()
            total_updated += 1

print(f"\n[DONE] Successfully backfilled {total_updated} store records across Jan-Aug 2025!")
