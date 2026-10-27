import os
from dotenv import load_dotenv
from supabase import create_client
import json

load_dotenv()
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])

periods_raw = supabase.table('scorecard_periods').select('*').execute().data
print('Period table columns:', list(periods_raw[0].keys()) if periods_raw else 'Empty')
period_map = {}
for p in periods_raw:
    name = p.get('name') or p.get('label') or p.get('period_key') or f"{p.get('start_date')} - {p.get('end_date')}"
    period_map[p['id']] = name
    print(f"Period: ID={p['id']}, Name={name}, start={p.get('start_date')}, end={p.get('end_date')}")

locs = supabase.table('locations').select('*').in_('store_number', [326, 136, 145]).execute().data
print('\nLocations:')
for l in locs:
    print(f"Store #{l['store_number']}: {l['name']} ({l['region']}) ID: {l['id']}")

for sn in [326, 136, 145]:
    matched = [l for l in locs if l['store_number'] == sn]
    if matched:
        loc_id = matched[0]['id']
        name = matched[0]['name']
        kpis = supabase.table('monthly_kpis').select('*').eq('location_id', loc_id).execute().data
        print(f"\n--- Store {sn}: {name} ({len(kpis)} periods recorded) ---")
        for k in kpis:
            p_name = period_map.get(k['period_id'], k['period_id'])
            rev = k.get('gross_revenue_actual')
            traf = k.get('foot_traffic_total')
            act = k.get('activations_total')
            cpo = k.get('cpo_units_actual')
            rep = k.get('repairs_oow_volume')
            print(f"  [{p_name}] Rev=${rev:,.2f} if rev else None, Traffic={traf}, Act={act}, CPO={cpo}, Rep={rep}".replace("if rev else None", f"(${rev})" if rev is not None else "($0)"))
