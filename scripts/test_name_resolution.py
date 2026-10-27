import openpyxl
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])

locations = supabase.table('locations').select('*').execute().data
print(f"Total DB locations: {len(locations)}")

name_map = {}
for loc in locations:
    clean = loc['name'].lower().replace('mobile klinik', '').replace('frchs-', '').strip()
    name_map[clean] = loc
    if loc.get('short_name'):
        name_map[loc['short_name'].lower().strip()] = loc

wb = openpyxl.load_workbook('Updated Franchise Scorecard - Oct MTD EOD - 10-25-26.xlsx', read_only=True, data_only=True)
ws = wb['Sept 26']

rows = list(ws.iter_rows(values_only=True))[8:]
print(f"Total rows in Sept 26: {len(rows)}")

name_matched = 0
code_differed = 0

for r_idx, r in enumerate(rows, start=9):
    if len(r) > 1 and r[0] and r[1]:
        raw_code = str(r[0]).strip()
        raw_name = str(r[1]).strip()
        if raw_name.lower() in ['total', 'corporate', 'average', 'none']:
            continue
        clean_name = raw_name.lower().replace('mobile klinik', '').strip()
        matched_loc = name_map.get(clean_name)
        if matched_loc:
            name_matched += 1
            digits = ''.join(c for c in raw_code if c.isdigit())
            extracted_num = int(digits[-3:]) if len(digits) >= 3 else (int(digits) if digits else None)
            if extracted_num != matched_loc['store_number']:
                code_differed += 1
                print(f"Row {r_idx:2d}: Name='{raw_name}' -> Matched: {matched_loc['name']} (#{matched_loc['store_number']}) | Excel Col A: '{raw_code}' (Extracted #{extracted_num})")

print(f"\nSummary for Sept 26: {name_matched} stores matched by name. {code_differed} stores had wrong/shifted store numbers in Column A!")
