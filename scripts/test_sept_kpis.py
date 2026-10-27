import sys
import openpyxl
sys.path.append('.')
from ingest_scorecard import parse_monthly_sheet

wb = openpyxl.load_workbook('Updated Franchise Scorecard - Oct MTD EOD - 10-25-26.xlsx', read_only=True, data_only=True)
records, p_start, p_end, p_type = parse_monthly_sheet(wb['Sept 26'], 'Sept 26')
print(f"Extracted {len(records)} records for Sept 26 ({p_start} to {p_end})")

for r in records:
    name = r['store_name'].lower()
    if 'lethbridge' in name or 'landsdowne' in name or 'limeridge' in name:
        print(f"\nStore: {r['store_name']} (raw store_num in Col A: {r['store_number']})")
        for k in ['gross_revenue_actual', 'gross_revenue_projected', 'sales_volume', 'foot_traffic_total', 'activations_total', 'cpo_units_actual', 'repairs_oow_volume', 'repairs_oow_revenue']:
            print(f"  {k}: {r['kpis'].get(k)}")
